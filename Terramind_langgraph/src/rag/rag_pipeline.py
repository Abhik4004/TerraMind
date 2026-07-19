import os
import json
import math
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from src.config.llm_provider import get_embeddings
from langchain_core.documents import Document
from src.config.settings import settings


# ── Geo helpers ───────────────────────────────────────────────────────────────
def _iter_coord_pairs(coords):
    """Recursively yield [lon, lat] pairs from any GeoJSON coordinates array."""
    if isinstance(coords, (list, tuple)):
        if (
            len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            yield coords[0], coords[1]
        else:
            for c in coords:
                yield from _iter_coord_pairs(c)


def geometry_centroid(geometry: dict) -> Optional[Tuple[float, float]]:
    """
    Return an approximate (lat, lon) centroid for a GeoJSON geometry.
    Works for Point, Polygon, MultiPolygon, LineString, etc. by averaging
    all vertices — accurate enough for radius-based bounds filtering.
    """
    if not geometry:
        return None
    pairs = list(_iter_coord_pairs(geometry.get("coordinates")))
    if not pairs:
        return None
    lon = sum(p[0] for p in pairs) / len(pairs)
    lat = sum(p[1] for p in pairs) / len(pairs)
    # Basic sanity: valid lat/lon ranges
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return (lat, lon)
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points, in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def _doc_centroid(doc: Document) -> Optional[Tuple[float, float]]:
    """
    Centroid for a retrieved document. Prefers centroid stored in metadata
    (added at ingestion); falls back to parsing the geometry out of the
    document's JSON content so geo-filtering also works on older vector
    stores built before centroid metadata existed.
    """
    md = doc.metadata or {}
    lat, lon = md.get("centroid_lat"), md.get("centroid_lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return (lat, lon)
    try:
        feature = json.loads(doc.page_content)
        if isinstance(feature, dict):
            return geometry_centroid(feature.get("geometry"))
    except (json.JSONDecodeError, TypeError):
        pass
    return None

class RAGCONFIG:
    """Configuration for RAG pipeline"""
    data_path = str(settings.DATA_DIR)
    chunk_size = settings.CHUNK_SIZE
    collection_name = settings.COLLECTION_NAME
    persist_vector_store_directory = str(settings.VECTOR_DIR)
    embedding_function = get_embeddings()
    MAX_CHARS = settings.MAX_CHARS

class RAGPipeline:
    """RAG Pipeline for ingesting and retrieving geospatial documents"""

    def __init__(self, config: RAGCONFIG):
        self.config = config
        # Memory management: one long-lived Chroma client per pipeline instead
        # of constructing a new client (and its SQLite handles) on every query.
        self._vs = None

    def _vector_store(self):
        if self._vs is None:
            self._vs = Chroma(
                collection_name=self.config.collection_name,
                persist_directory=self.config.persist_vector_store_directory,
                embedding_function=self.config.embedding_function,
            )
        return self._vs

    def ingestion_vs(self):
        """
        Ingest GeoJSON files into the vector store.

        This method:
        1. Reads all .geojson files from the data directory
        2. Processes each feature in the FeatureCollection
        3. Truncates content if it exceeds MAX_CHARS
        4. Creates Document objects with metadata
        5. Stores them in Chroma vector store
        """
        data_dir = Path(self.config.data_path)
        all_chunks = []
        MAX_CHARS = self.config.MAX_CHARS

        print(f"Loading GeoJSON files from: {data_dir}")

        # Process each GeoJSON file
        for geojson_file in data_dir.glob("*.geojson"):
            print(f"Processing: {geojson_file.name}")

            with open(geojson_file, "r", encoding="utf-8") as f:
                geojson = json.load(f)

            if geojson.get("type") == "FeatureCollection":
                features = geojson.get("features", [])

                for idx, feature in enumerate(features):
                    content = json.dumps(feature, ensure_ascii=False)

                    # Truncate if needed
                    if len(content) > MAX_CHARS:
                        # Keep geometry and essential properties
                        simplified = {
                            "type": feature.get("type"),
                            "geometry": feature.get("geometry"),
                            "properties": feature.get("properties", {})
                        }
                        content = json.dumps(simplified, ensure_ascii=False)[:MAX_CHARS]

                    metadata = {
                        "source": geojson_file.name,
                        "feature_id": idx,
                        "feature_type": feature.get("type", "unknown")
                    }
                    # Store centroid so retrieval can filter by geographic bounds.
                    centroid = geometry_centroid(feature.get("geometry"))
                    if centroid:
                        metadata["centroid_lat"] = centroid[0]
                        metadata["centroid_lon"] = centroid[1]

                    doc = Document(page_content=content, metadata=metadata)
                    all_chunks.append(doc)
            else:
                # Handle single feature or other GeoJSON types
                content = json.dumps(geojson, ensure_ascii=False)[:MAX_CHARS]
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": geojson_file.name,
                        "feature_type": geojson.get("type", "unknown")
                    }
                )
                all_chunks.append(doc)

        print(f"Total chunks created: {len(all_chunks)}")

        # Create vector store
        print("Creating Chroma vector store...")
        vector_store = Chroma.from_documents(
            documents=all_chunks,
            collection_name=self.config.collection_name,
            persist_directory=self.config.persist_vector_store_directory,
            embedding=self.config.embedding_function
        )

        print(f"Vector store created successfully at: {self.config.persist_vector_store_directory}")
        return vector_store

    def vector_store_exists(self) -> bool:
        """
        Check if the vector store exists.

        Returns:
            True if vector store exists, False otherwise
        """
        persist_dir = Path(self.config.persist_vector_store_directory)
        chroma_db = persist_dir / "chroma.sqlite3"

        if not chroma_db.exists():
            return False

        # Additional check: verify the collection exists in the database
        try:
            vector_store = Chroma(
                collection_name=self.config.collection_name,
                persist_directory=self.config.persist_vector_store_directory,
                embedding_function=self.config.embedding_function
            )
            # Try to get count - will fail if collection doesn't exist
            count = vector_store._collection.count()
            return count > 0
        except Exception as e:
            print(f"Vector store check failed: {e}")
            return False

    def ensure_vector_store(self):
        """
        Ensure vector store exists, create if it doesn't.
        Result is memoized: the existence check (which opens a fresh Chroma
        client) runs once per process, not once per query.
        """
        if getattr(self, "_vs_ready", False):
            return
        if not self.vector_store_exists():
            print("[INFO] Vector store not found. Creating new vector store...")
            self.ingestion_vs()
            print("[INFO] Vector store created successfully!")
        self._vs_ready = True

    def retreival_vs(self, question: str, k: int = None,
                     coordinates: dict = None, radius_km: float = None):
        """
        Retrieve relevant documents from the vector store.
        Auto-creates vector store if it doesn't exist.

        Args:
            question: The query string
            k: Number of documents to retrieve (default from settings)
            coordinates: Optional {'latitude', 'longitude'} of the query point.
                When provided (and geo-bounds enabled), documents whose centroid
                is farther than ``radius_km`` are discarded so answers stay
                relevant to the selected location.
            radius_km: Override for the geo-bounds radius (default from settings).

        Returns:
            Dictionary with 'documents' and 'question' keys
        """
        if k is None:
            k = settings.RETRIEVAL_K

        # Ensure vector store exists before retrieval
        self.ensure_vector_store()

        qlat = (coordinates or {}).get("latitude")
        qlon = (coordinates or {}).get("longitude")
        geo_enabled = (
            settings.GEO_BOUNDS_ENABLED
            and qlat is not None
            and qlon is not None
        )

        # Over-fetch when geo-filtering so we still end up with ~k nearby docs.
        fetch_k = settings.RETRIEVAL_FETCH_K if geo_enabled else k

        print(f"Retrieving documents for query: {question[:100]}...")

        retriever = self._vector_store().as_retriever(search_kwargs={"k": fetch_k})

        documents = retriever.invoke(question)
        print(f"Retrieved {len(documents)} candidate documents")

        if geo_enabled:
            radius = radius_km if radius_km is not None else settings.GEO_BOUNDS_RADIUS_KM
            kept = []
            located = []  # (distance, doc) for every doc with a centroid
            dropped = 0
            for doc in documents:
                centroid = _doc_centroid(doc)
                if centroid is None:
                    # No locatable geometry — can't attribute it to a wrong
                    # place, so keep it (likely general/non-geographic content).
                    kept.append(doc)
                    continue
                dist = haversine_km(qlat, qlon, centroid[0], centroid[1])
                located.append((dist, doc))
                if dist <= radius:
                    doc.metadata["geo_distance_km"] = round(dist, 1)
                    kept.append(doc)
                else:
                    dropped += 1

            # Nearest fallback: a tight radius (e.g. 20 km for soil) can empty
            # the result set in sparse areas. Answer from the nearest points,
            # explicitly distance-tagged, rather than from nothing.
            if not kept and located:
                located.sort(key=lambda t: t[0])
                for dist, doc in located[: settings.GEO_BOUNDS_NEAREST_FALLBACK]:
                    doc.metadata["geo_distance_km"] = round(dist, 1)
                    doc.metadata["geo_fallback"] = True
                    kept.append(doc)
                print(
                    f"Geo-bounds: nothing within {radius}km — nearest-fallback "
                    f"kept {len(kept)} (closest {located[0][0]:.1f}km)"
                )

            documents = kept[:k]
            print(
                f"Geo-bounds: kept {len(documents)} within {radius}km of "
                f"({qlat:.4f}, {qlon:.4f}); dropped {dropped} out-of-bounds"
            )
        else:
            documents = documents[:k]

        print(f"Returning {len(documents)} documents")

        return {
            "documents": documents,
            "question": question
        }

    def get_vector_store(self):
        """
        Get the existing vector store instance.

        Returns:
            Chroma vector store instance
        """
        return self._vector_store()

    def similarity_search(self, query: str, k: int = None):
        """
        Perform similarity search on the vector store.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of Document objects
        """
        if k is None:
            k = settings.RETRIEVAL_K

        vector_store = self.get_vector_store()
        results = vector_store.similarity_search(query, k=k)

        return results

    def similarity_search_with_score(self, query: str, k: int = None):
        """
        Perform similarity search with relevance scores.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of tuples (Document, score)
        """
        if k is None:
            k = settings.RETRIEVAL_K

        vector_store = self.get_vector_store()
        results = vector_store.similarity_search_with_score(query, k=k)

        return results


# Test function
if __name__ == "__main__":
    # Initialize pipeline
    pip = RAGPipeline(RAGCONFIG)

    # Test ingestion (uncomment if you want to rebuild the vector store)
    # pip.ingestion_vs()

    # Test retrieval
    res = pip.retreival_vs("What is the best location for tea gardening?")

    print("\n" + "="*80)
    print("RETRIEVAL TEST")
    print("="*80)
    print(f"\nQuery: {res['question']}")
    print(f"\nNumber of documents retrieved: {len(res['documents'])}")
    print(f"\nFirst document preview:")
    print(res['documents'][0].page_content[:500])
    print("\n" + "="*80)