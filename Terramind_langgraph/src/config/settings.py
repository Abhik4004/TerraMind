import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Configuration settings for the Land Analysis system"""

    # Paths — resolve relative to this file, not the CWD
    BASE_DIR = Path(__file__).parent.parent.parent  # Terramind_langgraph/
    SRC_DIR = BASE_DIR / "src"
    DATA_DIR = SRC_DIR / "data"
    VECTOR_DIR = SRC_DIR / "vector"
    CACHE_DIR = BASE_DIR / "cache"

    # RAG Configuration
    COLLECTION_NAME = "terramind-rag-chroma"
    CHUNK_SIZE = 50
    MAX_CHARS = 1500

    # Model Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss:120b-cloud")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

    # Retrieval Configuration
    RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "5"))
    RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.7"))
    # How many candidates to pull before geo-filtering down to RETRIEVAL_K.
    RETRIEVAL_FETCH_K = int(os.getenv("RETRIEVAL_FETCH_K", "20"))

    # Geo-bounds Configuration — keep retrieved documents near the query point
    # so answers don't describe an entirely different region.
    GEO_BOUNDS_ENABLED = os.getenv("GEO_BOUNDS_ENABLED", "true").lower() == "true"
    GEO_BOUNDS_RADIUS_KM = float(os.getenv("GEO_BOUNDS_RADIUS_KM", "75"))
    # Per-domain radii: soil varies at km scale, weather is regional.
    GEO_BOUNDS_RADIUS_SOIL_KM = float(os.getenv("GEO_BOUNDS_RADIUS_SOIL_KM", "20"))
    GEO_BOUNDS_RADIUS_RISK_KM = float(os.getenv("GEO_BOUNDS_RADIUS_RISK_KM", "50"))
    # When the tight radius empties the result set, keep the N nearest docs
    # instead of answering from nothing.
    GEO_BOUNDS_NEAREST_FALLBACK = int(os.getenv("GEO_BOUNDS_NEAREST_FALLBACK", "3"))

    # Cache Configuration
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
    ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "")

    # LLM / embedding provider — "ollama" (local, dev) or "groq"/"fastembed"
    # (remote LLM + local CPU embeddings, fits a 1 GB EC2 free-tier box).
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
    EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "ollama").lower()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    FASTEMBED_MODEL = os.getenv("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")

    # Memory Management
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "500"))
    MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))
    LLM_HISTORY_MESSAGES = int(os.getenv("LLM_HISTORY_MESSAGES", "6"))
    SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
    CACHE_SWEEP_INTERVAL_MIN = int(os.getenv("CACHE_SWEEP_INTERVAL_MIN", "60"))

    # Tool Configuration
    MAX_TOOL_RETRIES = int(os.getenv("MAX_TOOL_RETRIES", "3"))
    TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "30"))

    # Self-RAG Configuration
    MAX_GENERATION_RETRIES = int(os.getenv("MAX_GENERATION_RETRIES", "3"))
    HALLUCINATION_CHECK_ENABLED = os.getenv("HALLUCINATION_CHECK_ENABLED", "true").lower() == "true"
    ANSWER_CHECK_ENABLED = os.getenv("ANSWER_CHECK_ENABLED", "true").lower() == "true"

    # External APIs — all keyless / open-source:
    #   Weather + air quality: Open-Meteo (https://open-meteo.com)
    #   Roads: Overpass / OpenStreetMap (https://overpass-api.de)
    # No API keys required.

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    RATE_LIMIT_STREAM_PER_MINUTE = int(os.getenv("RATE_LIMIT_STREAM_PER_MINUTE", "20"))

    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def display_settings(cls):
        """Display current settings"""
        print("\n" + "="*80)
        print("SYSTEM SETTINGS")
        print("="*80)
        print(f"LLM Model: {cls.LLM_MODEL}")
        print(f"Embedding Model: {cls.EMBEDDING_MODEL}")
        print(f"Retrieval K: {cls.RETRIEVAL_K}")
        print(f"Cache Enabled: {cls.ENABLE_CACHE}")
        print(f"Cache TTL: {cls.CACHE_TTL_HOURS} hours")
        print(f"Max Retries: {cls.MAX_GENERATION_RETRIES}")
        print("="*80 + "\n")

settings = Settings()
settings.create_directories()