# Fig. 1 · System Overview

---

## Fig. 1(a) · TerraMind Platform Architecture

```mermaid
graph TD
    subgraph Frontend["Frontend · React 19 + Mapbox GL · port 5173"]
        UI["Chat & Map Interface"]
    end

    subgraph Backend["Backend · FastAPI + Socket.IO · port 8000"]
        API["REST API · Auth · Rate Limiter"]
    end

    subgraph Orchestration["LangGraph Orchestration"]
        RAG["Self-RAG Workflow\n11-node DAG"]
    end

    subgraph LLM["Local Inference · Ollama · port 11434"]
        Model["LLM · gpt-oss:120b-cloud"]
        Embed["Embeddings · nomic-embed-text"]
    end

    subgraph Data["Data & Storage"]
        Vector[("ChromaDB\nVector Store")]
        Auth[("MongoDB Atlas\nUser Auth")]
        Cache[("3-Tier File Cache\nResponse · Embedding · Tool")]
        GeoFiles["GeoJSON Files\n14 files · 3.6 MB"]
    end

    subgraph External["External APIs"]
        OWM["OpenWeatherMap"]
        OSM["Overpass · OpenStreetMap"]
    end

    UI -->|HTTP + WebSocket| API
    API --> RAG
    RAG --> Model
    RAG --> Embed
    Embed --> Vector
    RAG --> Vector
    RAG --> OWM
    RAG --> OSM
    RAG --> Cache
    API --> Auth
    GeoFiles -->|ingest + embed| Vector
```

---

## Fig. 1(b) · Multi-User Geospatial Query Flow

```mermaid
graph TD
    A["👤 User\nEnter query + coordinates"]
    B["Frontend\nChat & Map UI"]
    C["Backend\nAuth check · Rate limit"]
    D{"Cache Hit?\nSHA-256 key"}
    E["Return Cached Answer"]
    F["Parse Query\n& Extract Coordinates"]
    G["Select Tools\n(LLM-driven)"]
    H["ChromaDB\nVector Search · k=5"]
    I["External APIs\nWeather · Roads · Pollution"]
    J["Grade Document\nRelevance"]
    K["Generate Answer\n(LLM)"]
    L{"Hallucination\nCheck"}
    M{"Answer\nComplete?"}
    N["Format Answer\n+ Source Attribution"]
    O["Store in Cache"]
    P["Frontend\nRender answer + map"]

    A --> B
    B -->|"POST /query"| C
    C --> D
    D -->|"HIT"| E
    D -->|"MISS"| F
    E --> P
    F --> G
    G --> H
    G --> I
    H --> J
    I --> J
    J --> K
    K --> L
    L -->|"fail · retry < 3"| K
    L -->|"pass"| M
    M -->|"incomplete · retry < 3"| K
    M -->|"complete"| N
    N --> O
    O --> P

    style E fill:#1c4a2e,stroke:#2ecc71,color:#fff
    style L fill:#4a3800,stroke:#f39c12,color:#fff
    style M fill:#4a3800,stroke:#f39c12,color:#fff
    style N fill:#1c4a2e,stroke:#2ecc71,color:#fff
```

---

## Fig. 1(c) · Threat Model — Hallucinated Response Risk

```mermaid
graph TD
    Q["User Query\n(natural language)"]

    Q --> P["Coordinate Parser"]
    P -->|"invalid / swapped coords"| W1["⚠ Coord Error\nAuto-corrected with warning"]
    P -->|valid| R["ChromaDB Retrieval\nk=5 nearest chunks"]

    R -->|low relevance| W2["⚠ Weak Grounding\nIrrelevant documents pass through"]
    R -->|relevant| G["LLM Generator"]
    W2 --> G

    G --> H{"Hallucination\nGrader"}
    H -->|"score < threshold\nretry < 3"| G
    H -->|"score < threshold\nretry ≥ 3"| W3["⚠ Unverified Output\nForced pass — risk of fabrication"]
    H -->|pass| A{"Answer\nGrader"}

    A -->|"incomplete\nretry < 3"| G
    A -->|"incomplete\nretry ≥ 3"| W4["⚠ Partial Answer\nForced pass — may miss key data"]
    A -->|complete| F["✅ Final Answer\n+ Source Attribution"]

    W3 --> F
    W4 --> F

    style W1 fill:#7a1c1c,stroke:#e74c3c,color:#fff
    style W2 fill:#7a1c1c,stroke:#e74c3c,color:#fff
    style W3 fill:#7a1c1c,stroke:#e74c3c,color:#fff
    style W4 fill:#7a1c1c,stroke:#e74c3c,color:#fff
    style F  fill:#1c4a2e,stroke:#2ecc71,color:#fff
```
