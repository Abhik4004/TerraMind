# src/utils/source_tracker.py
from typing import List, Dict, Any
from datetime import datetime
import json

class SourceTracker:
    """
    Tracks and formats sources used in generating answers.
    Maintains attribution for documents, tools, and data sources.
    """

    def __init__(self):
        self.sources = []

    def add_document_source(
            self,
            document: str,
            metadata: Dict[str, Any] = None,
            relevance_score: float = None
    ):
        """
        Add a document as a source.

        Args:
            document: Document content or identifier
            metadata: Document metadata (source file, feature_id, etc.)
            relevance_score: Relevance score if available
        """
        source = {
            "type": "document",
            "content_preview": document[:200] + "..." if len(document) > 200 else document,
            "metadata": metadata or {},
            "relevance_score": relevance_score,
            "timestamp": datetime.now().isoformat()
        }
        self.sources.append(source)

    def add_tool_source(
            self,
            tool_name: str,
            tool_input: Dict[str, Any],
            tool_output: Any,
            success: bool = True
    ):
        """
        Add a tool execution as a source.

        Args:
            tool_name: Name of the tool
            tool_input: Input parameters to the tool
            tool_output: Output from the tool
            success: Whether the tool execution was successful
        """
        source = {
            "type": "tool",
            "tool_name": tool_name,
            "input": tool_input,
            "output_preview": str(tool_output)[:200] if tool_output else "No output",
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        self.sources.append(source)

    def add_cache_source(self, cache_key: str, cache_type: str = "response"):
        """
        Add a cache hit as a source.

        Args:
            cache_key: Cache key used
            cache_type: Type of cache (response, embedding, tool)
        """
        source = {
            "type": "cache",
            "cache_type": cache_type,
            "cache_key": cache_key[:16] + "...",
            "timestamp": datetime.now().isoformat()
        }
        self.sources.append(source)

    def add_vector_search_source(
            self,
            query: str,
            num_results: int,
            search_type: str = "similarity"
    ):
        """
        Add vector search as a source.

        Args:
            query: Search query
            num_results: Number of results retrieved
            search_type: Type of search performed
        """
        source = {
            "type": "vector_search",
            "query": query,
            "num_results": num_results,
            "search_type": search_type,
            "timestamp": datetime.now().isoformat()
        }
        self.sources.append(source)

    def get_sources(self) -> List[Dict[str, Any]]:
        """Get all tracked sources."""
        return self.sources

    def get_sources_by_type(self, source_type: str) -> List[Dict[str, Any]]:
        """Get sources filtered by type."""
        return [s for s in self.sources if s.get("type") == source_type]

    def format_sources_for_display(self) -> str:
        """
        Format sources for display in the final answer.

        Returns:
            Formatted string with source information
        """
        if not self.sources:
            return "\n**Sources:** No sources available"

        output = "\n**Sources Used:**\n"

        # Group by type
        doc_sources = self.get_sources_by_type("document")
        tool_sources = self.get_sources_by_type("tool")
        cache_sources = self.get_sources_by_type("cache")
        vector_sources = self.get_sources_by_type("vector_search")

        # Format document sources
        if doc_sources:
            output += "\n📄 **Documents:**\n"
            for idx, source in enumerate(doc_sources, 1):
                metadata = source.get("metadata", {})
                source_file = metadata.get("source", "Unknown")
                feature_id = metadata.get("feature_id", "N/A")
                relevance = source.get("relevance_score")

                output += f"  {idx}. Source: {source_file}"
                if feature_id != "N/A":
                    output += f" (Feature #{feature_id})"
                if relevance:
                    output += f" - Relevance: {relevance:.2f}"
                output += "\n"

        # Format tool sources
        if tool_sources:
            output += "\n**Tools Executed:**\n"
            for idx, source in enumerate(tool_sources, 1):
                tool_name = source.get("tool_name")
                success = "[OK]" if source.get("success") else "[FAIL]"
                output += f"  {idx}. {success} {tool_name}\n"

        # Format vector search
        if vector_sources:
            output += "\n**Vector Searches:**\n"
            for idx, source in enumerate(vector_sources, 1):
                query = source.get("query", "")[:50]
                num_results = source.get("num_results", 0)
                output += f"  {idx}. Query: \"{query}...\" ({num_results} results)\n"

        # Format cache hits
        if cache_sources:
            output += "\n💾 **Cache Hits:**\n"
            for idx, source in enumerate(cache_sources, 1):
                cache_type = source.get("cache_type", "unknown")
                output += f"  {idx}. {cache_type.capitalize()} cache\n"

        # Summary
        output += f"\n**Total Sources:** {len(self.sources)} ({len(doc_sources)} docs, {len(tool_sources)} tools, {len(cache_sources)} cached)\n"

        return output

    def format_sources_json(self) -> str:
        """Format sources as JSON string."""
        return json.dumps(self.sources, indent=2)

    def clear(self):
        """Clear all tracked sources."""
        self.sources = []

    def merge(self, other_tracker: 'SourceTracker'):
        """
        Merge sources from another tracker.

        Args:
            other_tracker: Another SourceTracker instance
        """
        self.sources.extend(other_tracker.get_sources())


def create_source_tracker() -> SourceTracker:
    """Factory function to create a new source tracker."""
    return SourceTracker()


# Test function
if __name__ == "__main__":
    print("Testing Source Tracker")
    print("="*80)

    tracker = SourceTracker()

    # Add various sources
    tracker.add_document_source(
        "Alluvial soil with pH 6.5, suitable for tea cultivation...",
        metadata={"source": "kolkata_soil_data.geojson", "feature_id": 123},
        relevance_score=0.92
    )

    tracker.add_tool_source(
        "get_weather_data",
        {"lat": 22.5726, "lon": 88.3639},
        {"temperature": 28, "humidity": 75},
        success=True
    )

    tracker.add_vector_search_source(
        "What is the best location for tea gardening?",
        num_results=5
    )

    tracker.add_cache_source("abc123def456", "response")

    # Display formatted sources
    print(tracker.format_sources_for_display())

    print("\n" + "="*80)