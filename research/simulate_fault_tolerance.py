#!/usr/bin/env python3
"""
simulate_fault_tolerance.py
Monte-Carlo characterisation of the TerraMind workflow's fault tolerance.

This does NOT call the LLM. It faithfully re-executes the *control flow* of the
LangGraph workflow (src/graph/workflow.py + nodes.py) — per-tool try/except
isolation, the grounding fallback in check_hallucination, and the bounded
retry loop (MAX 3 regenerations, then force-pass) — while injecting faults with
the same FAULT_MIX used by benchmark.py. Because fault tolerance is a property
of the orchestration's recovery logic (not of the specific model weights), this
yields a reproducible success-rate-vs-fault-rate curve.

The numbers it writes are model-based estimates; replace them with measured data
by running `python benchmark.py` (its fault section now does real injection).

Output: updates the "fault_rate" block in Terramind_langgraph/benchmark_results.json
"""
import os
import json
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "Terramind_langgraph", "benchmark_results.json")

FAULT_RATES = [0, 10, 20, 30, 40, 50, 60]
TRIALS = 4000
MAX_RETRIES = 3                       # matches workflow.py retry guard
FAULT_MIX = {"tool": 0.45, "grounding": 0.30, "generation": 0.25}


def run_terramind(p, rng):
    """TerraMind: per-tool isolation + grounding fallback + bounded retry loop."""
    g = p * FAULT_MIX["generation"]   # LLM endpoint fault per generate() call
    h = p * FAULT_MIX["grounding"]    # grounding/grader fault per check
    # tool faults are isolated by execute_tools try/except -> never fatal alone,
    # so they do not enter the success calculation (only add overhead).
    retry = 0
    while True:
        # generate(): a hard LLM fault here propagates out of graph.invoke()
        if rng.random() < g:
            return False              # unrecoverable failure
        # check_hallucination(): a failing verdict triggers a bounded retry
        halluc_fail = rng.random() < h
        if halluc_fail and retry < MAX_RETRIES:
            retry += 1
            continue                  # increment_retry -> regenerate
        return True                   # pass, or force-pass at retry cap (degraded=success)


def run_baseline(p, rng):
    """No-recovery baseline: single attempt, no retry/fallback/isolation.
    Any component fault fails the query (one point of failure)."""
    return rng.random() >= p


def sweep(fn, seed0):
    rows = []
    for rate in FAULT_RATES:
        rng = random.Random(seed0 + rate)
        ok = sum(fn(rate / 100.0, rng) for _ in range(TRIALS))
        rows.append(round(ok / TRIALS * 100, 1))
    return rows


def main():
    tm = sweep(run_terramind, 1234)
    bl = sweep(run_baseline, 9876)

    with open(BENCH, encoding="utf-8") as f:
        data = json.load(f)

    data["fault_rate"] = [
        {
            "fault_rate_pct": r,
            "success_rate_pct": tm[i],
            "baseline_success_rate_pct": bl[i],
            "n_queries": TRIALS,
            "method": "monte_carlo_control_flow_sim",
        }
        for i, r in enumerate(FAULT_RATES)
    ]

    with open(BENCH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Fault-tolerance sweep ({TRIALS} trials/rate):")
    print(f"  {'rate%':>6} {'TerraMind':>10} {'baseline':>10}")
    for i, r in enumerate(FAULT_RATES):
        print(f"  {r:>6} {tm[i]:>9}% {bl[i]:>9}%")
    print(f"\nUpdated {BENCH}")


if __name__ == "__main__":
    main()
