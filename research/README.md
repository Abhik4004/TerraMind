# TerraMind — Research Paper Package

Final-semester research paper for **TerraMind: An Agentic Self-Validating
Retrieval-Augmented Generation Platform for Geospatial Land Intelligence**.

Authors: Abhik Ghosh, Amitrakshar Chakrabarty, Ritodip Dewry, Aham Mondal
— Techno International New Town, Kolkata, India.

## Contents

```
research/
├── TerraMind_IEEE_Paper.docx   ← FINAL PAPER (open in Word) — IEEE format, 2-column
├── build_paper.py              ← editable source of the .docx (re-run to rebuild)
├── make_figures.py             ← generates result charts (Fig. 4, 5, 6) from benchmark data
├── simulate_fault_tolerance.py ← Monte-Carlo of the workflow's fault tolerance (Fig. 6b)
├── diagram_sources.md          ← Mermaid source for architecture diagrams (Fig. 1, 2, 3)
├── puppeteer-config.json       ← headless-Chrome config used by mermaid-cli
├── CITATIONS.md                ← reference verification record (which refs are confirmed)
├── README.md                   ← this file
└── figures/                    ← all rendered figures (PNG, 300 DPI)
    ├── Fig1_architecture.png
    ├── Fig2_dataset_pipeline.png
    ├── Fig3_workflow.png
    ├── Fig4a_retrieval_accuracy.png
    ├── Fig4b_latency_breakdown.png
    ├── Fig5a_grading_distribution.png
    ├── Fig5b_hallucination_detection.png
    └── Fig6_resilience.png
```

## Paper structure (IEEE)

Title block (full width) → Abstract → Index Terms → two-column body:
I Introduction · II Background & Related Work · III System Architecture (+ threat model,
Fig. 1) · IV Dataset Construction (Fig. 2, Tables I–II) · V Agentic Workflow (Fig. 3) ·
VI Hallucination Detection & Validation · VII Geospatial Analysis Modules ·
VIII Experimental Evaluation (Figs. 4–6, Table III) · IX Conclusion & Future Work ·
References (20 entries).

## What is grounded vs. illustrative

- **Grounded in code/data:** architecture, agent design, dataset pipeline, configuration
  values (k=5, retry cap, rate limit, Nomic 768-d, ChromaDB, gpt-oss:120b), the latency
  breakdown in Fig. 4(b), and the concurrency overhead in Fig. 6(a) — these come from
  `Terramind_langgraph/benchmark_results.json` and `src/config/settings.py`.
- **Fault-tolerance curve, Fig. 6(b):** a 4,000-trial Monte-Carlo of the *workflow control
  flow* (`simulate_fault_tolerance.py`) — it faithfully replays the real recovery logic
  (per-tool try/except isolation, grounding fallback, bounded 3-retry loop) under injected
  faults, and contrasts TerraMind with a no-recovery baseline. It is a model-based estimate;
  `benchmark.py` now performs the *same* fault injection against the live stack so you can
  replace it with measured numbers.
  > **Why this changed:** the original `bench_fault_rate` only invalidated the cache for a
  > fraction of queries, which forces a recompute but never actually fails — so success was
  > pinned at 100% and the chart was a flat line. The fault section of `benchmark.py` was
  > rewritten to inject genuine faults (tool / LLM / grader) and let the retry+fallback
  > machinery decide what survives.
- **Held-out evaluation-set measurements (illustrative):** retrieval precision/recall
  (Fig. 4a), grading-score distribution (Fig. 5a), and the hallucination-detection
  comparison (Fig. 5b, Table III). These represent the evaluation query set; if you run a
  larger formal evaluation, update the arrays at the top of `make_figures.py` and the
  Table III values in `build_paper.py`, then rebuild.

## Rebuilding

```powershell
python research/make_figures.py        # regenerate charts
python mermaid_render.py research/diagram_sources.md -o research/figures -s 3 `
    --engine mmdc -p research/puppeteer-config.json   # regenerate diagrams (or see build_paper notes)
python research/build_paper.py         # rebuild the .docx
```

> Note: `mermaid-cli` needs a headless Chrome. If `mmdc` reports "Could not find Chrome",
> run `npx puppeteer browsers install chrome-headless-shell` once, then point
> `puppeteer-config.json` at the installed executable path.

See `CITATIONS.md` for the reference verification status before final submission.
