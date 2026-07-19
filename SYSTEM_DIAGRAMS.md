# TerraMind — System Flow Diagrams

Two diagrams. Same pipeline. One **without** PII filter, one **with**.
Tuned for **1024×768 (XGA)**: vertical spine, big font (22px), wide spacing → no line overlap, readable from far.

> Render: GitHub / any Mermaid viewer. Vertical flow fits 1024 width; scroll down for full height.

---

## 1. Without PII Filter

Raw query → straight into cache + graph. Personal data reaches LLM.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#1b5e20','primaryColor':'#e7f5ec','primaryBorderColor':'#2e7d32','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([User Query]) --> C{Cache hit?}
    C -->|Yes| ANS([Final Answer])
    C -->|No| P[Parse query<br/>coords + intent]
    P --> TS[Tool selection<br/>LLM]
    TS --> RE[Embed + Vector retrieve<br/>k-NN]
    RE --> GB[Geo-bounds filter<br/>Haversine &le; 75km]
    GB --> GD[Grade docs<br/>parallel LLM]
    GD --> EX[Execute tools<br/>roads / weather / AQI]
    EX --> GEN[Generate answer<br/>LLM]
    GEN --> HG{Grounded?}
    HG -->|Fail, r&lt;3| RT[Retry]
    RT --> GEN
    HG -->|Pass| AG{Useful?}
    AG -->|Fail, r&lt;3| RT
    AG -->|Pass| FMT[Format + cache]
    FMT --> ANS

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 1 — TerraMind Pipeline (Without PII Filter)</b></p>

---

## 2. With PII Filter

Redact **before** cache + graph. Coords kept. LLM never see personal data.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#1b5e20','primaryColor':'#e7f5ec','primaryBorderColor':'#2e7d32','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([User Query]) --> PII[PII Redaction<br/>email/phone/card/ID<br/>coords preserved]
    PII --> C{Cache hit?}
    C -->|Yes| ANS([Final Answer])
    C -->|No| P[Parse query<br/>coords + intent]
    P --> TS[Tool selection<br/>LLM]
    TS --> RE[Embed + Vector retrieve<br/>k-NN]
    RE --> GB[Geo-bounds filter<br/>Haversine &le; 75km]
    GB --> GD[Grade docs<br/>parallel LLM]
    GD --> EX[Execute tools<br/>roads / weather / AQI]
    EX --> GEN[Generate answer<br/>LLM sees clean text]
    GEN --> HG{Grounded?}
    HG -->|Fail, r&lt;3| RT[Retry]
    RT --> GEN
    HG -->|Pass| AG{Useful?}
    AG -->|Fail, r&lt;3| RT
    AG -->|Pass| FMT[Format + cache]
    FMT --> ANS

    style PII fill:#fde68a,stroke:#b45309,stroke-width:3px,color:#7c2d12
    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 2 — TerraMind Pipeline (With PII Filter)</b></p>

---

## Diff

| Point | No PII | With PII |
|-------|--------|----------|
| First step | Cache check | **Redact** then cache |
| LLM input | raw text (leak risk) | clean text |
| Coords | kept | kept (decimals protected) |
| Extra nodes | 0 | 1 (`PII Redaction`) |
| Masked | — | email · phone · card · SSN · Aadhaar · PAN |

## Notes

- Spine vertical → edges parallel, no cross.
- Only back-edge = `Retry → Generate`. Mermaid route left, no overlap.
- Font 24px, nodeSpacing 70, rankSpacing 80 → far-readable on XGA.
- Yellow node = security gate (with-PII only).

---

## 3. Tool Dispatch — `execute_tools`

Selected tools loop. Coords required for API tools. Results → source tracker.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#1b5e20','primaryColor':'#e7f5ec','primaryBorderColor':'#2e7d32','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    IN([selected_tools + coords]) --> LOOP[For each tool]
    LOOP --> HC{Has lat/lon?}
    HC -->|No| SKIP[Skip<br/>reason: no coords]
    HC -->|Yes| MAP{Tool name?}
    MAP -->|geospatial_index| VEC[handled by retrieve node]
    MAP -->|weather*| W[weather_tool]
    MAP -->|road* / flood / construction| R[road_tool]
    MAP -->|pollution| AQ[air_quality]
    W --> COL[Collect result]
    R --> COL
    AQ --> COL
    SKIP --> COL
    VEC --> COL
    COL --> TRK[Source tracker<br/>success/fail]
    TRK --> OUT([tool_results])

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 3 — Tool Dispatch Map</b></p>

---

## 4. Weather + Air Quality Tool — Open-Meteo (no key)

Cache-first. Retry 5xx. WMO code → text.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#0369a1','primaryColor':'#e0f2fe','primaryBorderColor':'#0284c7','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([lat, lon]) --> CK{Tool cache hit?}
    CK -->|Yes| RET([Return cached])
    CK -->|No| K{Which call?}
    K -->|current| A[GET /v1/forecast<br/>current + daily min/max]
    K -->|recent| B[GET /v1/forecast<br/>past_days = N]
    K -->|air quality| D[GET /air-quality<br/>PM/O3/NO2/US+EU AQI]
    A --> WM[Map WMO code &rarr; text]
    B --> AGG[Daily aggregate<br/>min / max / sum]
    WM --> S[Build result]
    AGG --> S
    D --> S
    S --> SET[Cache set]
    SET --> RET

    ERR{{HTTP 5xx?}} -.retry x2.-> K
    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 4 — Weather &amp; Air-Quality Tool (Open-Meteo)</b></p>

---

## 5. Road Network Tool — Overpass / OpenStreetMap (no key)

Query roads in radius. Compute length, density, connectivity.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#6d28d9','primaryColor':'#ede9fe','primaryBorderColor':'#7c3aed','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([lat, lon, radius]) --> CK{Tool cache hit?}
    CK -->|Yes| RET([Return cached])
    CK -->|No| OV[POST Overpass<br/>way highway around r]
    OV --> EL[Split elements<br/>nodes + ways]
    EL --> LEN[Way length<br/>&sum; haversine segments]
    EL --> TYP[Count road types]
    LEN --> DET{Detailed?}
    TYP --> DET
    DET -->|Yes| DEG[Node degree<br/>intersections deg&ge;3]
    DEG --> DENS[Density = L / &pi;r&sup2;<br/>Connectivity score]
    DENS --> S[Build result]
    DET -->|No| S
    S --> SET[Cache set]
    SET --> RET

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 5 — Road Network Tool (Overpass/OSM)</b></p>

---

## 6. RAG Retrieval + Geo-bounds

Embed → vector kNN → keep near docs only.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#b45309','primaryColor':'#fef3c7','primaryBorderColor':'#d97706','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([question + coords]) --> EMB[Embed<br/>Ollama nomic-embed 768d]
    EMB --> KNN[Chroma kNN<br/>fetch_k = 20]
    KNN --> GEO{Coords given?}
    GEO -->|No| TOPK[Take top k = 5]
    GEO -->|Yes| CENT[Centroid per doc]
    CENT --> DIST[Haversine to query]
    DIST --> FILT{&le; 75 km?}
    FILT -->|Yes| KEEP[Keep doc]
    FILT -->|No| DROP[Drop doc]
    KEEP --> TOPK
    DROP --> TOPK
    TOPK --> OUT([Grade docs])

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 6 — RAG Retrieval + Geo-bounds Filter</b></p>

> **← COMBINED SCORE FORMULA LIVES HERE** (midterm p.7). Retrieval blends semantic match + geographic proximity:
>
> `Combined Score = α · Cosine_Similarity + (1 − α) · Distance_Score`
>
> - `α ∈ [0,1]` — trust text vs distance. `α=1` → text only, `α=0` → distance only.
> - Retrieve if `Combined ≥ 0.75` (threshold).
> - Example: `0.7·0.96 + 0.3·0.448 = 0.806 ≥ 0.75` → retrieved.
>
> In code today: Cosine_Similarity = vector kNN score; Distance_Score derives from the Haversine geo-bounds (§5). `α` = blend weight.

---

## 7. Cache Manager — `get_or_compute`

Disk pkl. SHA-256 key. 24h TTL.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#334155','primaryColor':'#e2e8f0','primaryBorderColor':'#475569','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    Q([query + params]) --> KEY[SHA-256 key<br/>sorted JSON]
    KEY --> EX{File exists<br/>and not expired?}
    EX -->|Yes| LOAD[Load pkl<br/>from_cache = true]
    LOAD --> RET([Return])
    EX -->|No| COMP[Compute fn]
    COMP --> SET[Write pkl]
    SET --> RET

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 7 — Cache Manager</b></p>

---

## 8. Self-RAG Grading Loop

Two graders gate answer. Bounded retry r &lt; 3.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#166534','primaryColor':'#dcfce7','primaryBorderColor':'#16a34a','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    G[Generate answer] --> H{Grounded?<br/>hallucination grader}
    H -->|Pass or r&ge;3| A{Useful?<br/>answer grader}
    H -->|Fail and r&lt;3| INC[r = r + 1]
    A -->|Pass or r&ge;3| F[Format final]
    A -->|Fail and r&lt;3| INC
    INC --> G
    F --> OUT([Final answer])

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 8 — Self-RAG Grading Loop</b></p>

---

## 9. PII Redaction Internals

Protect coords first. Then mask PII. Then restore.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#b45309','primaryColor':'#fde68a','primaryBorderColor':'#b45309','primaryTextColor':'#7c2d12'},'flowchart':{'nodeSpacing':70,'rankSpacing':80,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    T([Raw text]) --> P[Protect decimals<br/>coords &rarr; placeholder]
    P --> R1[Mask email]
    R1 --> R2[Mask card / SSN]
    R2 --> R3[Mask Aadhaar / PAN]
    R3 --> R4[Mask phone<br/>digit-count 10-15]
    R4 --> RES[Restore decimals]
    RES --> OUT([Clean text &rarr; LLM])

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 9 — PII Redaction Internals</b></p>

---

## 10. Hallucination Check — Step by Step

Groundedness gate. Ask: does answer stick to facts, or invent stuff?
Decision tree — terminal outcomes, no crossing lines.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontSize':'24px','fontFamily':'Segoe UI, Arial','lineColor':'#166534','primaryColor':'#dcfce7','primaryBorderColor':'#16a34a','primaryTextColor':'#0f172a'},'flowchart':{'nodeSpacing':75,'rankSpacing':85,'curve':'basis','htmlLabels':true}}%%
flowchart TD
    GEN([generation + facts]) --> EN{Check enabled?}
    EN -->|No| P1[[PASS &middot; check off]]
    EN -->|Yes| SRC{Grounding source?}
    SRC -->|none| P2[[PASS &middot; skip, no source]]
    SRC -->|docs, else tools| C1{1&#46; Consistent<br/>with facts?}
    C1 -->|No, contradicts| F[[FAIL &middot; not grounded]]
    C1 -->|Yes| C2{2&#46; Fabricated<br/>data present?}
    C2 -->|Yes, invented| F
    C2 -->|No| C3{3&#46; Inference<br/>reasonable?}
    C3 -->|Yes| P3[[PASS &middot; grounded]]

    linkStyle default stroke-width:2.5px
```

<p align="center"><b>Fig 10 — Hallucination Check (step by step)</b></p>

> **Outcome routing** (not drawn, keeps tree clean):
> **PASS** → answer grader (Fig 8). **FAIL** → retry if `r < 3` (regenerate), else proceed anyway.

---

## 10a. Hallucination Check — Detail

**What.** Self-RAG groundedness gate. `check_hallucination` node + `hallucination_grader` chain. Stop model inventing facts.

**Inputs.** `generation` (answer text) + `facts` (grounding material).

**Step 0 — Enable flag.** `HALLUCINATION_CHECK_ENABLED` off → return `pass`, skip LLM. Speed knob.

**Step 1 — Pick grounding source** (`nodes.py`):

| Condition | `facts` = | Why |
|-----------|-----------|-----|
| documents survived grading | joined documents | primary source |
| no docs, but tool results | joined tool results | geo-bounds dropped all docs → weather/road/AQI still valid |
| neither | — | **skip → pass** (no source → grading impossible → avoid infinite retry) |

**Step 2 — LLM grader.** `facts` + `generation` → grader model (temp 0, deterministic) → JSON `{"binary_score":"yes"|"no"}`.

**Step 3 — 3 criteria** (`hallucination_grader.py` system prompt):

| # | Criterion | `yes` (grounded) | `no` (hallucinated) |
|---|-----------|------------------|----------------------|
| 1 | **Consistency** | uses info matching facts (soil, terrain, weather, land use) | claim **directly contradicts** source |
| 2 | **Fabrication** | no invented specifics | invents location / coords / measurement **not in facts anywhere** |
| 3 | **Inference** | reasonable inference from partial data = still grounded | — |

**Lenient bias (key).** Sparse or incomplete facts alone do **not** fail. Fail **only** on contradiction or fabrication. Stops over-rejecting good partial answers.

### Formula model — how grounded / fabricated is measured (midterm p.8)

Conceptual Self-RAG reflection score. Code today realizes it with the LLM binary grader; the formula is the design intent behind that yes/no:

```
Confidence = Support · (1 − Contradiction) · Completeness
```

| Term | Formula | What it checks |
|------|---------|----------------|
| **Support** | `cosine(source, claim)` | **grounded?** — retrieved facts back the claim. High = grounded. |
| **Contradiction** | `max cosine(claim, opposing_clause)` | **fabricated / conflicting?** — is there any retrieved clause that opposes the claim. High = not grounded. |
| **Completeness** | `answered_questions / required_questions` | coverage of required info |

- **Grounded check** = criterion 1 (Consistency) = high **Support**, low **Contradiction**.
- **Fabrication check** = criterion 2 = the **Contradiction** term (`(1 − Contradiction)` factor): claim aligns with an opposing clause → factor → 0 → Confidence collapses.
- Low `Confidence` (below threshold) → **auto re-retrieval / retry** (Fig 8 loop).
- Example: `Support=0.94, Contradiction=0.82, Completeness=0.50` → `0.94·(1−0.82)·0.50 = 0.085` → low → re-retrieve.

**Formula → diagram map:**

| Formula | Source | Used in |
|---------|--------|---------|
| `Combined = α·Cosine + (1−α)·Distance` | p.7 | **Fig 6** (retrieval) |
| `Confidence = Support·(1−Contradiction)·Completeness` | p.8 | **Fig 8 + Fig 10** (this check) |
| `Precision@K`, `Cosine` | p.5–6 | **Fig 6** (retrieval eval) |
| `Haversine ≤ 75 km` | code | **Fig 5, Fig 6** |
| `Density = L/πr²`, `Connectivity` | code | **Fig 5** (roads) |

**Step 4 — Map score.** `binary_score == "yes"` (or bool `True`) → `pass`. Else → `fail`.

**Step 5 — Route** (`workflow.py`):

- `pass` → answer grader.
- `fail` **and** `r < 3` → `increment_retry` → regenerate (r ← r+1).
- `fail` **and** `r ≥ 3` → give up gate, proceed with current answer (bounded, no infinite loop).

**Worked examples:**

| Facts | Generation | Score | Why |
|-------|-----------|-------|-----|
| "soil: alluvial, AQI 64" | "Alluvial soil, moderate air (AQI 64)" | `yes` | consistent |
| "soil: alluvial" | "Rocky basalt terrain" | `no` | contradicts (crit 1) |
| "AQI 64" | "Population 2.3M, metro rail line 4" | `no` | fabricated, not in facts (crit 2) |
| "temp 29°C, humid" | "Warm humid; likely uncomfortable midday" | `yes` | reasonable inference (crit 3) |
| (all docs geo-dropped) | any | `pass` | no source → skip |

---

## Figure Index

| Fig | Name |
|-----|------|
| 1 | Pipeline — Without PII Filter |
| 2 | Pipeline — With PII Filter |
| 3 | Tool Dispatch Map |
| 4 | Weather &amp; Air-Quality Tool (Open-Meteo) |
| 5 | Road Network Tool (Overpass/OSM) |
| 6 | RAG Retrieval + Geo-bounds |
| 7 | Cache Manager |
| 8 | Self-RAG Grading Loop |
| 9 | PII Redaction Internals |
| 10 | Hallucination Check (step by step) |
