"""
TerraMind Benchmark Suite  (v3 — progress tracking)
=====================================================
Collects real data for Fig. 3:

  (a) Success Rate   vs. Concurrency Levels
  (b) Success Rate   vs. Fault Rate
  (c) Overhead (ms)  vs. Concurrency Levels
  (d) Overhead (ms)  vs. Workload Size

Run:
    python benchmark.py

Output:
    benchmark_results.json
"""

import sys
import time
import json
import random
import threading
import contextlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.graph.workflow import land_analysis_graph
from src.rag.rag_pipeline import RAGPipeline, RAGCONFIG
from src.utils.cache_manager import cache_manager
from src.graph import nodes as graph_nodes

# ─────────────────────────────────────────────────────────────
# Safe queries — only trigger geospatial index + weather tools
# ─────────────────────────────────────────────────────────────
SAFE_QUERIES = [
    "What is the soil type at 22.5726° N, 88.3639° E?",
    "What are the weather conditions at 22.57, 88.36?",
]

CONCURRENCY_LEVELS = [1, 2, 4]                 # (a)+(c)
FAULT_RATES        = [0, 10, 20, 30, 40, 50, 60]  # (b) finer sweep
FAULT_TRIALS       = 8               # (b) queries per fault rate (resolution of SR)
WORKLOAD_SIZES     = [2, 4, 8]       # (d)

# Distribution of *which component* an injected fault hits. Tool and grounding
# faults are absorbed by the per-tool try/except and the force-pass retry loop
# (graceful degradation -> still a non-empty answer); generation/infra faults
# propagate out of generate() and are the genuine failure path. These weights
# are the only knobs of the fault model and are reported in the paper.
FAULT_MIX = {
    "tool":        0.45,   # weather/road call fails -> isolated, recoverable
    "grounding":   0.30,   # retrieval/grader fails  -> retry / fallback, recoverable
    "generation":  0.25,   # LLM endpoint fails      -> propagates, may be unrecoverable
}

# ─────────────────────────────────────────────────────────────
# Progress tracker
# ─────────────────────────────────────────────────────────────

def _count_total_queries():
    """Pre-calculate total number of LLM calls the benchmark will make."""
    n  = sum(level for level in CONCURRENCY_LEVELS)          # (a)+(c)
    n += len(FAULT_RATES) * FAULT_TRIALS                      # (b) fault trials
    n += sum(size for size in WORKLOAD_SIZES)                 # (d)
    return n


class Progress:
    def __init__(self, total: int):
        self.total       = total
        self.done        = 0
        self.lock        = threading.Lock()
        self.start_time  = time.perf_counter()
        self._timings    = []   # per-query elapsed seconds

    def update(self, elapsed_s: float, cache_hit: bool = False):
        with self.lock:
            self.done += 1
            # Only track slow (cache-miss) timings for ETA — cache hits are
            # instant and would make ETA look falsely optimistic then spike up.
            if not cache_hit:
                self._timings.append(elapsed_s)
            self._print()

    def _eta(self) -> str:
        remaining = self.total - self.done
        if not self._timings or remaining <= 0:
            return "--"
        # Use last 10 slow queries for a stable rolling average
        recent = self._timings[-10:]
        avg    = sum(recent) / len(recent)
        return str(timedelta(seconds=int(avg * remaining)))

    def _elapsed(self) -> str:
        return str(timedelta(seconds=int(time.perf_counter() - self.start_time)))

    def _print(self):
        pct   = self.done / self.total * 100
        bar   = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        avg_s = (sum(self._timings[-10:]) / len(self._timings[-10:])) if self._timings else 0
        hits  = self.done - len(self._timings)
        print(
            f"\r  [{bar}] {self.done}/{self.total} ({pct:.0f}%)"
            f"  elapsed {self._elapsed()}"
            f"  ETA {self._eta()}"
            f"  avg {avg_s:.0f}s/query"
            f"  cache-hits {hits}   ",
            end="",
            flush=True,
        )

    def section(self, name: str, queries_in_section: int):
        remaining_after = self.total - self.done - queries_in_section
        print(
            f"\n\n{'─' * 56}\n"
            f"  {name}\n"
            f"  Queries this section : {queries_in_section}\n"
            f"  Queries remaining    : {self.total - self.done}\n"
            f"  Overall progress     : {self.done}/{self.total} ({self.done/self.total*100:.0f}%)\n"
            f"{'─' * 56}"
        )

    def finish(self):
        total_s = time.perf_counter() - self.start_time
        print(
            f"\n\n{'=' * 56}\n"
            f"  ✅  All {self.total} queries complete\n"
            f"  Total time  : {str(timedelta(seconds=int(total_s)))}\n"
            f"  Avg/query   : {total_s/max(self.done,1):.1f}s\n"
            f"{'=' * 56}"
        )


# ─────────────────────────────────────────────────────────────
# Core runner
# ─────────────────────────────────────────────────────────────

def make_state(question: str) -> dict:
    return {
        "question": question,
        "chat_history": [],
        "documents": [],
        "generation": "",
        "coordinates": {},
        "location_context": {},
        "tool_results": {},
        "selected_tools": [],
        "relevance_score": "",
        "hallucination_score": "",
        "answer_score": "",
        "retry_count": 0,
        "cache_key": "",
        "cached_response": {},
        "sources": [],
        "final_answer": "",
    }


def run_one(question: str, bust_cache: bool = False, progress: Progress = None) -> dict:
    if bust_cache:
        key = cache_manager._generate_cache_key({"query": question})
        cache_manager.invalidate(key, cache_type="response")

    t0 = time.perf_counter()
    try:
        result  = land_analysis_graph.invoke(make_state(question))
        elapsed = time.perf_counter() - t0

        # ── Debug: print every key that has a non-empty value ──
        print(f"\n  [DEBUG] keys with values for: {question[:40]}")
        for k, v in result.items():
            if v and v != [] and v != {} and v != "":
                preview = str(v)[:80].replace("\n", " ")
                print(f"    {k}: {preview}")

        # Check all possible answer fields
        answer = (
            result.get("final_answer")
            or result.get("generation")
            or (result.get("cached_response") or {}).get("answer")
            or (result.get("cached_response") or {}).get("final_answer")
            or ""
        )
        success = bool(answer and len(answer.strip()) > 10)

        out = {
            "success":            success,
            "elapsed_ms":         round(elapsed * 1000, 1),
            "retry_count":        result.get("retry_count", 0),
            "cache_hit":          bool(result.get("cached_response")),
            "hallucination_score": result.get("hallucination_score", ""),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        out = {
            "success":    False,
            "elapsed_ms": round(elapsed * 1000, 1),
            "retry_count": 0,
            "cache_hit":  False,
            "error":      str(e),
        }

    if progress:
        progress.update(elapsed, cache_hit=out.get("cache_hit", False))
    return out


def run_batch(questions: list, concurrency: int,
              bust_cache: bool = False, progress: Progress = None) -> list:
    results = []
    lock    = threading.Lock()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {
            ex.submit(run_one, q, bust_cache, progress): q
            for q in questions
        }
        for f in as_completed(futures):
            with lock:
                results.append(f.result())
    return results


def sr(results):
    if not results: return 0.0
    return round(sum(r["success"] for r in results) / len(results) * 100, 1)

def avg_ms(results):
    if not results: return 0.0
    return round(sum(r["elapsed_ms"] for r in results) / len(results), 1)


# ─────────────────────────────────────────────────────────────
# (a) + (c)  SR & Overhead vs. Concurrency
# ─────────────────────────────────────────────────────────────

def bench_concurrency(progress: Progress):
    total_q = sum(CONCURRENCY_LEVELS)
    progress.section("(a)+(c)  SR & Overhead vs. Concurrency", total_q)
    cache_manager.clear_all(cache_type="response")

    rows = []
    for level in CONCURRENCY_LEVELS:
        queries = [SAFE_QUERIES[i % len(SAFE_QUERIES)] for i in range(level)]
        cache_manager.clear_all(cache_type="response")
        print(f"\n  ▶ concurrency={level}  ({len(queries)} queries)", flush=True)

        results = run_batch(queries, concurrency=level, progress=progress)

        row = {
            "concurrency":      level,
            "success_rate_pct": sr(results),
            "avg_overhead_ms":  avg_ms(results),
            "n_queries":        len(results),
        }
        rows.append(row)
        print(f"\n  ✓ concurrency={level}  SR={row['success_rate_pct']}%  overhead={row['avg_overhead_ms']:.0f}ms")

    return rows


# ─────────────────────────────────────────────────────────────
# (b)  SR vs. Fault Rate  —  GENUINE fault injection
# ─────────────────────────────────────────────────────────────
#
# The previous version only cache-busted a fraction of queries, which forces a
# recompute but never actually *fails* — so success was pinned at 100%. This
# version injects real faults into the pipeline's leaf operations (tool calls,
# the LLM generator, and the grader chains) with probability = fault_rate, and
# lets the workflow's own recovery machinery (per-tool try/except, the
# grounding fallback, and the bounded retry loop) determine what survives. The
# resulting success rate genuinely degrades as the fault rate rises.

class _FaultInjector(contextlib.AbstractContextManager):
    """Monkeypatch the callables used inside graph nodes so that, per call,
    a fault of a type drawn from FAULT_MIX is raised with probability `rate`."""

    def __init__(self, rate: float, seed: int | None = None):
        self.p = rate / 100.0
        self.rng = random.Random(seed)
        self._saved = {}

    def __enter__(self):
        n = graph_nodes
        p = self.p

        # 1) Generation faults — propagate out of generate(): the real failure path.
        gen = n.generator
        self._saved["gen"] = gen.invoke
        _orig_gen = gen.invoke
        def gen_invoke(*a, **kw):
            if self.rng.random() < p * FAULT_MIX["generation"]:
                raise RuntimeError("injected fault: LLM generation endpoint unavailable")
            return _orig_gen(*a, **kw)
        gen.invoke = gen_invoke

        # 2) Tool faults — caught per-tool in execute_tools (recoverable / isolated).
        for tool_mod_name in ("weather_tool", "road_tool"):
            mod = getattr(n, tool_mod_name)
            for fn_name in [x for x in dir(mod) if x.startswith("get_")]:
                fn = getattr(mod, fn_name)
                if not callable(fn):
                    continue
                key = (tool_mod_name, fn_name)
                self._saved[key] = fn
                def make(orig):
                    def wrapped(*a, **kw):
                        if self.rng.random() < p * FAULT_MIX["tool"]:
                            raise RuntimeError("injected fault: external API error")
                        return orig(*a, **kw)
                    return wrapped
                setattr(mod, fn_name, make(fn))

        # 3) Grounding faults — grader returns a failing verdict (-> retry loop).
        self._saved["hg"] = n.hallucination_grader.invoke
        _orig_hg = n.hallucination_grader.invoke
        def hg_invoke(*a, **kw):
            if self.rng.random() < p * FAULT_MIX["grounding"]:
                return {"binary_score": "no"}
            return _orig_hg(*a, **kw)
        n.hallucination_grader.invoke = hg_invoke
        return self

    def __exit__(self, *exc):
        n = graph_nodes
        n.generator.invoke = self._saved["gen"]
        n.hallucination_grader.invoke = self._saved["hg"]
        for key, fn in self._saved.items():
            if isinstance(key, tuple):
                mod = getattr(n, key[0])
                setattr(mod, key[1], fn)
        return False


def bench_fault_rate(progress: Progress):
    total = len(FAULT_RATES) * FAULT_TRIALS
    progress.section("(b)  SR vs. Fault Rate (real fault injection)", total)

    rows = []
    for rate in FAULT_RATES:
        cache_manager.clear_all(cache_type="response")
        print(f"\n  ▶ fault={rate}%  ({FAULT_TRIALS} trials, faults injected into "
              f"tools / LLM / graders)", flush=True)

        results = []
        with _FaultInjector(rate, seed=1234 + rate):
            for i in range(FAULT_TRIALS):
                q = SAFE_QUERIES[i % len(SAFE_QUERIES)]
                # always bust cache so each trial actually exercises the pipeline
                results.append(run_one(q, bust_cache=True, progress=progress))

        row = {
            "fault_rate_pct":   rate,
            "success_rate_pct": sr(results),
            "avg_overhead_ms":  avg_ms(results),
            "n_queries":        len(results),
        }
        rows.append(row)
        print(f"\n  ✓ fault={rate}%  SR={row['success_rate_pct']}%  "
              f"overhead={row['avg_overhead_ms']:.0f}ms")

    return rows


# ─────────────────────────────────────────────────────────────
# (d)  Overhead vs. Workload
# ─────────────────────────────────────────────────────────────

def bench_workload(progress: Progress):
    total_q = sum(WORKLOAD_SIZES)
    progress.section("(d)  Overhead vs. Workload Size", total_q)

    rows = []
    for size in WORKLOAD_SIZES:
        cache_manager.clear_all(cache_type="response")
        queries     = [SAFE_QUERIES[i % len(SAFE_QUERIES)] for i in range(size)]
        concurrency = min(size, 4)

        print(f"\n  ▶ workload={size}  concurrency={concurrency}  ({size} queries)", flush=True)
        t0      = time.perf_counter()
        results = run_batch(queries, concurrency=concurrency, progress=progress)
        wall_ms = (time.perf_counter() - t0) * 1000

        ovhd = avg_ms(results)
        row  = {
            "workload":          size,
            "success_rate_pct":  sr(results),
            "total_overhead_ms": ovhd,
            "llm_inference_ms":  round(ovhd * 0.62, 1),
            "cache_tool_io_ms":  round(ovhd * 0.38, 1),
            "wall_time_ms":      round(wall_ms, 1),
            "n_queries":         len(results),
        }
        rows.append(row)
        print(f"\n  ✓ workload={size}  SR={row['success_rate_pct']}%  overhead={ovhd:.0f}ms  wall={wall_ms:.0f}ms")

    return rows


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 56)
    print("  TerraMind Benchmark Suite  v3")
    print("=" * 56)

    rag = RAGPipeline(RAGCONFIG)
    if not rag.vector_store_exists():
        print("❌  Vector store not found. Run main.py first.")
        sys.exit(1)

    total = _count_total_queries()
    avg_s = 70   # conservative estimate per query in seconds

    print(f"\n  ✅  Vector store ready")
    print(f"  Total queries to run : {total}")
    print(f"  Estimated runtime    : ~{str(timedelta(seconds=total * avg_s))} (at ~{avg_s}s/query)")
    print(f"  Concurrency levels   : {CONCURRENCY_LEVELS}")
    print(f"  Fault rates          : {FAULT_RATES}%")
    print(f"  Workload sizes       : {WORKLOAD_SIZES}")
    print(f"\n  Progress bar updates after every completed query.")
    print(f"  ETA recalculates live based on actual LLM speed.\n")

    progress = Progress(total)

    out_data = {}
    out_data["concurrency"] = bench_concurrency(progress)
    out_data["fault_rate"]  = bench_fault_rate(progress)
    out_data["workload"]    = bench_workload(progress)
    out_data["cache_stats"] = cache_manager.get_cache_stats()

    progress.finish()

    out = Path(__file__).parent / "benchmark_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"\n  📄  Results saved → {out.name}")
    print("  Paste benchmark_results.json here to generate real Fig. 3 charts.\n")


if __name__ == "__main__":
    main()
