# Fig. 2 · Agent Architecture

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
graph TD
    subgraph Auth["① Auth & Routing"]
        T1["Authenticate User\n~2s"]
        T2["Rate-limit Check\n~1s"]
        T3["Input Validation\n~1s"]
        T1 --> T2 --> T3
    end

    subgraph CacheCheck["② Cache"]
        T4["Cache Lookup\n~1s"]
    end

    subgraph Planning["③ Planning"]
        T5["Parse Query & Coords\n~3s"]
        T6["Select Tools\n~2s"]
        T5 --> T6
    end

    subgraph Retrieval["④ Parallel Retrieval"]
        T7["Vector Search · ChromaDB\n~4s"]
        T8["Call Weather API\n~3s"]
        T9["Call Roads API\n~3s"]
    end

    subgraph Grading["⑤ Grading"]
        T10["Grade Document Relevance\n~2s"]
    end

    subgraph Gen1["⑥ Generation · Iteration 1"]
        T11["Generate Draft Answer\n~5s"]
        T12["Hallucination Check\n~2s"]
        T13["Completeness Check\n~2s"]
        T11 --> T12 --> T13
    end

    subgraph Gen2["⑦ Generation · Iteration 2 (retry)"]
        T14["Regenerate Answer\n~4s"]
        T15["Hallucination Check\n~2s"]
        T16["Completeness Check\n~2s"]
        T14 --> T15 --> T16
    end

    subgraph Output["⑧ Output"]
        T17["Format & Cite Sources\n~2s"]
        T18["Write to Cache\n~1s"]
        T19["Stream Response\n~2s"]
        T17 --> T18 --> T19
    end

    T3  --> T4
    T4  --> T5
    T6  --> T7
    T6  --> T8
    T6  --> T9
    T7  --> T10
    T8  --> T10
    T9  --> T10
    T10 --> T11
    T13 -->|"fail · retry"| T14
    T13 -->|"pass"| T17
    T16 --> T17

    style T11 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T12 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T13 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T14 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T15 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T16 fill:#4a1c00,stroke:#e67e22,color:#fff
    style T19 fill:#1c4a2e,stroke:#2ecc71,color:#fff
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

    style Decide    fill:#4a3800,stroke:#f39c12,color:#fff
    style Adapt     fill:#4a1c1c,stroke:#e74c3c,color:#fff
    style Respond   fill:#1c4a2e,stroke:#2ecc71,color:#fff
    style Output    fill:#1c4a2e,stroke:#2ecc71,color:#fff
    style LLM       fill:#1a1a3e,stroke:#3498db,color:#fff
    style Memory    fill:#2d132c,stroke:#9b59b6,color:#fff
    style Knowledge fill:#1c3144,stroke:#007cbf,color:#fff
```
