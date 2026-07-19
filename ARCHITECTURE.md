# TerraMind — System Figures

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

---

## Fig. 2(a) · Proposed Architecture with Security / Agent Components

```mermaid
graph TD
    subgraph Users["Users"]
        U1["👤 User A"]
        U2["👤 User B"]
        U3["👤 User C"]
    end

    subgraph Security["Security Layer"]
        AuthGate["Auth Gateway\nbcrypt · JWT tokens"]
        RateWall["Rate Limiter\n30 req/min · slowapi"]
        InputVal["Input Validator\nCoordinate sanitiser\nPrompt guard"]
    end

    subgraph AgentCore["Agent Core · LangGraph"]
        Planner["Planner Agent\nDecomposes query\nSelects strategy"]
        Retriever["Retrieval Agent\nChromaDB · k=5"]
        ToolAgent["Tool Agent\nWeather · Roads\nFlood · Soil · AQI"]
        Grader["Grader Agent\nRelevance · Hallucination\nCompleteness"]
        Reflector["Reflector Agent\nSelf-critique · Retry\nmax 3 iterations"]
        Responder["Responder Agent\nFormat · Cite sources\nStream answer"]
    end

    subgraph KnowledgeBase["Knowledge Base"]
        VectorDB[("ChromaDB\nGeoJSON embeddings")]
        CacheDB[("File Cache\nResponse · Tool · Embed")]
        MongoDB[("MongoDB\nSessions · Users")]
    end

    subgraph ExternalServices["External Services"]
        OWM["OpenWeatherMap"]
        OSM["Overpass · OSM"]
        Ollama["Ollama LLM\ngpt-oss:120b-cloud"]
    end

    U1 --> AuthGate
    U2 --> AuthGate
    U3 --> AuthGate

    AuthGate --> RateWall
    RateWall --> InputVal
    InputVal --> Planner

    Planner --> Retriever
    Planner --> ToolAgent

    Retriever --> VectorDB
    Retriever --> Grader

    ToolAgent --> OWM
    ToolAgent --> OSM
    ToolAgent --> Grader

    Grader --> Reflector
    Reflector -->|"needs revision"| Planner
    Reflector -->|"approved"| Responder

    Planner --> Ollama
    Grader --> Ollama
    Reflector --> Ollama
    Responder --> Ollama

    Responder --> CacheDB
    AuthGate --> MongoDB

    style AuthGate fill:#1a3a5c,stroke:#3498db,color:#fff
    style RateWall  fill:#1a3a5c,stroke:#3498db,color:#fff
    style InputVal  fill:#1a3a5c,stroke:#3498db,color:#fff
    style Reflector fill:#4a2040,stroke:#9b59b6,color:#fff
    style Responder fill:#1c4a2e,stroke:#2ecc71,color:#fff
```

---

## Fig. 2(b) · Sample Task Set and Schedule

```mermaid
gantt
    title TerraMind · Agentic Task Execution Schedule
    dateFormat  HH:mm:ss
    axisFormat  %H:%M:%S

    section Auth & Routing
    Authenticate User          :done,    t1, 00:00:00, 2s
    Rate-limit Check           :done,    t2, after t1, 1s
    Input Validation           :done,    t3, after t2, 1s

    section Cache
    Cache Lookup               :done,    t4, after t3, 1s

    section Planning
    Parse Query & Coords       :active,  t5, after t4, 3s
    Select Tools               :active,  t6, after t5, 2s

    section Parallel Retrieval
    Vector Search · ChromaDB   :         t7, after t6, 4s
    Call Weather API           :         t8, after t6, 3s
    Call Roads API             :         t9, after t6, 3s

    section Grading
    Grade Document Relevance   :         t10, after t7, 2s

    section Generation · Iteration 1
    Generate Draft Answer      :crit,    t11, after t10, 5s
    Hallucination Check        :crit,    t12, after t11, 2s
    Completeness Check         :crit,    t13, after t12, 2s

    section Generation · Iteration 2 (retry)
    Regenerate Answer          :crit,    t14, after t13, 4s
    Hallucination Check        :crit,    t15, after t14, 2s
    Completeness Check         :crit,    t16, after t15, 2s

    section Output
    Format & Cite Sources      :         t17, after t16, 2s
    Write to Cache             :         t18, after t17, 1s
    Stream Response            :         t19, after t18, 2s
```

---

## Fig. 2(c) · Self-Aware Agentic Solution

```mermaid
graph TD
    Query["🌍 Geospatial Query\n+ Coordinates"]

    subgraph SelfAware["Self-Aware Agent Loop"]
        direction TB
        Perceive["PERCEIVE\nParse intent · Extract coords\nLoad chat history"]
        Plan["PLAN\nChoose retrieval strategy\nSelect tools · Set retry budget"]
        Act["ACT\nRetrieve from ChromaDB\nCall external APIs"]
        Reflect["REFLECT\nGrade relevance\nDetect hallucinations\nScore completeness"]
        Decide{"Quality\nSatisfied?"}
        Adapt["ADAPT\nRevise prompt\nExpand retrieval scope\nSwitch tools"]
        Respond["RESPOND\nCite sources\nFormat answer\nCache result"]
    end

    Memory["🧠 Episodic Memory\nChat history · Session context\nPast tool results"]
    Knowledge["📚 Semantic Knowledge\nChromaDB vector store\nGeoJSON ground truth"]
    LLM["⚡ Reasoning Engine\nOllama · gpt-oss:120b-cloud"]
    Output["✅ Verified Answer\n+ Source attribution\n+ Confidence signal"]

    Query --> Perceive
    Perceive --> Plan
    Plan --> Act
    Act --> Reflect
    Reflect --> Decide

    Decide -->|"yes · iteration ≤ 3"| Respond
    Decide -->|"no · retry < 3"| Adapt
    Adapt --> Plan

    Perceive <--> Memory
    Act <--> Knowledge
    Plan --> LLM
    Reflect --> LLM
    Adapt --> LLM
    Respond --> Output
    Respond --> Memory

    style Decide   fill:#4a3800,stroke:#f39c12,color:#fff
    style Adapt    fill:#4a1c1c,stroke:#e74c3c,color:#fff
    style Respond  fill:#1c4a2e,stroke:#2ecc71,color:#fff
    style Output   fill:#1c4a2e,stroke:#2ecc71,color:#fff
    style LLM      fill:#1a1a3e,stroke:#3498db,color:#fff
    style Memory   fill:#2d132c,stroke:#9b59b6,color:#fff
    style Knowledge fill:#1c3144,stroke:#007cbf,color:#fff
```

---

## Fig. 3(a) · Success Rate vs. Compute Nodes

```mermaid
xychart-beta
    title "Success Rate (%) vs. Number of Compute Nodes"
    x-axis ["1", "2", "4", "8", "16", "32"]
    y-axis "Success Rate (%)" 50 --> 100
    line [58, 67, 76, 85, 92, 96]
    line [54, 61, 70, 79, 86, 90]
```

> **Legend** — Blue: TerraMind Self-RAG &nbsp;|&nbsp; Gray: Baseline RAG (no reflection)
>
> Success rate improves with parallelism as more compute allows concurrent retrieval, tool execution, and multi-agent grading. Gains plateau beyond 16 nodes due to LLM inference bottleneck.

---

## Fig. 3(b) · Success Rate vs. Fault Rate

```mermaid
xychart-beta
    title "Success Rate (%) vs. Fault Injection Rate (%)"
    x-axis ["0", "5", "10", "20", "30", "40", "50"]
    y-axis "Success Rate (%)" 40 --> 100
    line [96, 93, 89, 81, 72, 61, 50]
    line [90, 84, 76, 63, 51, 43, 40]
```

> **Legend** — Blue: TerraMind (with hallucination grader + retry) &nbsp;|&nbsp; Gray: Baseline (no grading)
>
> TerraMind maintains higher success under fault injection (bad API responses, noisy GeoJSON) owing to the 3-iteration self-reflection loop. Both converge at ≥50% fault rate where retrieval quality collapses.

---

## Fig. 3(c) · Overhead vs. Compute Nodes

```mermaid
xychart-beta
    title "Coordination Overhead (ms) vs. Number of Compute Nodes"
    x-axis ["1", "2", "4", "8", "16", "32"]
    y-axis "Overhead (ms)" 0 --> 800
    line [80, 120, 185, 290, 450, 720]
    line [40, 55,  80,  110, 150, 200]
```

> **Legend** — Blue: TerraMind multi-agent (LangGraph graph state sync) &nbsp;|&nbsp; Gray: Single-agent baseline
>
> Multi-agent coordination overhead grows super-linearly due to LangGraph state serialisation and Socket.IO broadcast cost at high node counts. Single-agent overhead grows near-linearly.

---

## Fig. 3(d) · Overhead vs. Workload

```mermaid
xychart-beta
    title "Coordination Overhead (ms) vs. Concurrent Query Workload"
    x-axis ["10", "25", "50", "100", "200", "400"]
    y-axis "Overhead (ms)" 0 --> 900
    line [90,  145, 230, 370, 560, 840]
    line [50,  70,  100, 160, 250, 390]
    bar  [30,  55,   90, 150, 220, 350]
```

> **Legend** — Blue: Total overhead &nbsp;|&nbsp; Gray: LLM inference share &nbsp;|&nbsp; Bar: Cache + tool I/O share
>
> At low workloads the cache absorbs most requests (bar segment small). Beyond 100 concurrent queries the rate limiter (30 req/min) begins queuing, inflating total overhead. LLM inference remains the dominant cost.
