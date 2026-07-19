# TerraMind Paper Diagrams

## Fig. 1 · TerraMind System Architecture (Five Layers)

```mermaid
flowchart TB
    subgraph L1["① Frontend Layer · React 19.0 + Mapbox GL JS 3.6"]
        UI["Natural-Language Query Field<br/>+ Map Coordinate Selection<br/>React Markdown 9.0 · Source Panel"]
    end

    subgraph L2["② Backend & Orchestration Layer · FastAPI 0.115 + LangGraph 0.2"]
        ORCH["Stateful Agent State-Machine<br/>LangChain 0.3 prompt chains<br/>Auth · Rate Limit (30 req/min) · Trace Store"]
    end

    subgraph L3["③ Retrieval & Knowledge Layer · ChromaDB 0.6"]
        VDB[("Unified GeoJSON Embeddings<br/>Nomic Embed Text v1.5 · 768-d<br/>Metadata Filter · cosine k=5..10")]
    end

    subgraph L4["④ External Intelligence & Analysis Layer"]
        OWM["OpenWeatherMap API"]
        MBX["Mapbox Tilequery / Directions"]
        GEM["GEM PGA Raster (Rasterio)"]
        IFI["Indian Flood Inventory (GeoPandas)"]
    end

    subgraph L5["⑤ LLM Inference Endpoint"]
        LLM["gpt-oss:120b (cloud-served)<br/>via Ollama 0.4"]
    end

    UI <-->|HTTPS REST| ORCH
    ORCH <-->|embed + cosine search| VDB
    ORCH <-->|live HTTP| OWM
    ORCH <-->|live HTTP| MBX
    ORCH <-->|pixel lookup| GEM
    ORCH <-->|point-in-polygon| IFI
    ORCH <-->|structured prompt| LLM

    style L1 fill:#eaf2fb,stroke:#2c6fbb
    style L2 fill:#eef7e6,stroke:#7ab648
    style L3 fill:#fdf1e3,stroke:#f0a04b
    style L4 fill:#f3eaf7,stroke:#9b59b6
    style L5 fill:#e9edf5,stroke:#34495e
```

---

## Fig. 2 · Dataset Construction and Knowledge-Base Pipeline

```mermaid
flowchart LR
    A["14 × Location CSV<br/>Theme–Description pairs<br/>Basanti · Canning · Gosaba · Hingalganj …"]
    B["Merge (pandas)<br/>+ File_Index provenance"]
    C["DMS → Decimal<br/>dms_to_decimal()<br/>GeoDataFrame · EPSG:4326"]
    D["Weather Enrichment<br/>OpenWeatherMap<br/>current · 365-day · 16-day forecast<br/>day-major restructure"]
    E["Multi-Hazard Risk Index<br/>Heat · Humidity · Wind · Flood<br/>Seismic (GEM PGA) · IFI Flood<br/>5-level ordinal"]
    F["Unified GeoJSON<br/>risk_index.py · null purge"]
    G[("ChromaDB 0.6<br/>chunk per Theme–Description<br/>Nomic 768-d embeddings<br/>+ metadata")]

    A --> B --> C --> D --> E --> F --> G
    style A fill:#eaf2fb,stroke:#2c6fbb
    style G fill:#fdf1e3,stroke:#f0a04b
    style E fill:#f3eaf7,stroke:#9b59b6
```

---

## Fig. 3 · LangGraph Agentic Workflow — State Machine

```mermaid
flowchart TD
    Q(["User Query + Coordinates"]) --> QU["Query Understanding Agent<br/>classify intent · extract coords"]
    QU -->|land / multi-hazard| RA["Retrieval Agent<br/>ChromaDB k=5..10 · metadata filter<br/>compute RQPQ score"]
    QU -->|real-time data| GA["Geospatial Analysis Agent<br/>Weather · Road · Flood · Seismic"]
    QU -->|both| RA
    QU -->|both| GA

    RA --> RS["Response Synthesis Agent<br/>context aggregation · evidence fusion<br/>gpt-oss:120b grounded generation"]
    GA --> RS

    RS --> VA{"Validation Agent<br/>① RQPQ ≥ threshold?<br/>② LLM-as-judge grade ≥ pass?"}
    VA -->|fail · retry < 2| RA
    VA -->|pass| AA["Attribution Agent<br/>per-chunk citation records<br/>API endpoint + timestamp"]
    AA --> OUT(["Validated Answer<br/>+ Source Attribution JSON"])

    VA -. "retry exhausted (max 2)" .-> AA

    style VA fill:#fdf1e3,stroke:#f0a04b
    style AA fill:#eef7e6,stroke:#7ab648
    style OUT fill:#eaf2fb,stroke:#2c6fbb
```
