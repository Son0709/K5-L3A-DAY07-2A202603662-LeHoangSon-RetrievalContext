"""Run the Gemini agent over a benchmark split and store one trace per question.

  python -m rag.run_agent --split dev --name dense-b3000 --tools dense --budget 3000 --out results/agent-dev-dense-b3000

The agent only ever receives the question text; gold evidence and the user-filter field are
never passed. Traces are flushed per question, so a crash keeps earlier results.
Test requires --confirm-final (freeze the configuration on dev first).
"""
import argparse
import json
import time
from pathlib import Path

from .agent import CITE_RULE, SYSTEM, run_agent
from .config import CHUNKS_JSON, QUESTIONS_JSON, ROOT
from .dense import DenseRetriever
from .hybrid import HybridRetriever
from .lexical import BM25Retriever
from .llm import DEFAULT_MODEL, GeminiLLM
from .tools import SearchSession


def build_retrievers(keys: list[str], chunks: list[dict]) -> dict:
    dense = DenseRetriever() if ("dense" in keys or "hybrid" in keys) else None
    bm25 = BM25Retriever(chunks, "uni")
    pool = {"dense": dense, "bm25": bm25, "hybrid": HybridRetriever(dense, bm25) if dense else None}
    return {k: pool[k] for k in keys}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--name", required=True, help="configuration name stored in every trace")
    ap.add_argument("--tools", default="dense", help="comma list of: dense,bm25,hybrid")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--budget", type=int, default=3000, help="context budget in characters")
    ap.add_argument("--max-searches", type=int, default=4)
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--cite-rule", action="store_true", help="append the citation-id rule to the system prompt (A3)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--ids", default="", help="comma list of question ids (default: whole split)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--confirm-final", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="keep non-error traces already in --out and re-run only missing/error questions "
                         "(same configuration required); re-run traces are marked resumed_after_error")
    ap.add_argument("--max-consecutive-errors", type=int, default=3,
                    help="abort the run after this many consecutive provider errors (e.g. exhausted quota)")
    a = ap.parse_args()
    if a.split == "test" and not a.confirm_final:
        raise SystemExit("Refusing to run test without --confirm-final (freeze the config on dev first)")
    keys = [k for k in a.tools.split(",") if k]
    chunks = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))
    qs = [q for q in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8")) if q["split"] == a.split]
    if a.ids:
        want = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in want]
    if a.limit:
        qs = qs[:a.limit]
    retrievers = build_retrievers(keys, chunks)
    llm = GeminiLLM(model=a.model)
    config = {"name": a.name, "model": a.model, "temperature": llm.temperature, "tools": keys,
              "top_k": a.top_k, "budget_chars": a.budget, "max_searches": a.max_searches,
              "max_steps": a.max_steps, "cite_rule": a.cite_rule, "retrieval_index": "day6 lab_B (multilingual-e5-small)"}
    out = a.out if a.out.is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    kept: dict[str, dict] = {}
    errored_before: set[str] = set()
    path = out / "traces.jsonl"
    if a.resume and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                old_t = json.loads(line)
                if old_t["config"] != config:
                    raise SystemExit("--resume requires the identical configuration as the existing traces")
                (errored_before.add(old_t["query_id"]) if old_t["status"] == "error"
                 else kept.__setitem__(old_t["query_id"], old_t))
    todo = [q for q in qs if q["id"] not in kept]
    new_traces: list[dict] = []
    consecutive_errors, aborted = 0, False
    with open(path, "w", encoding="utf-8") as f:
        for t in kept.values():
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
        for q in todo:
            session = SearchSession(retrievers, a.top_k, a.budget, a.max_searches)
            t0 = time.perf_counter()
            r = run_agent(q["question"], llm, session, tool_keys=keys, max_steps=a.max_steps,
                          system=SYSTEM + CITE_RULE if a.cite_rule else SYSTEM)
            t = {"query_id": q["id"], "split": a.split, "answerable": q.get("answerable", True),
                 "qtype": q.get("qtype"), "question": q["question"], "config": config, **r}
            if q["id"] in errored_before:
                t["resumed_after_error"] = True
            new_traces.append(t)
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{q['id']:<4} {r['status']:<8} searches={r['n_searches']} ctx={len(r['context_ids'])} "
                  f"tok={r['usage']['prompt_tokens']}+{r['usage']['output_tokens']} {time.perf_counter() - t0:5.1f}s "
                  f"{r.get('reason', '')}")
            consecutive_errors = consecutive_errors + 1 if r["status"] == "error" else 0
            if consecutive_errors >= a.max_consecutive_errors:
                aborted = True
                print(f"ABORT: {consecutive_errors} consecutive provider errors (quota/outage?). "
                      "Fix the cause, then re-run the same command with --resume.")
                break
    by_id = {t["query_id"]: t for t in [*kept.values(), *new_traces]}
    traces = [by_id[q["id"]] for q in qs if q["id"] in by_id]
    path.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces), encoding="utf-8")
    n = len(traces)
    summary = {"config": config, "n": n, "planned": len(qs), "aborted": aborted,
               "not_run": [q["id"] for q in qs if q["id"] not in by_id],
               "status": {s: sum(t["status"] == s for t in traces) for s in ("answered", "abstain", "error")},
               "tool_use": f"{sum(t['n_searches'] > 0 for t in traces)}/{n}",
               "searches_distribution": {str(k): sum(t["n_searches"] == k for t in traces)
                                         for k in sorted({t["n_searches"] for t in traces})},
               "prompt_tokens": sum(t["usage"]["prompt_tokens"] for t in traces),
               "output_tokens": sum(t["usage"]["output_tokens"] for t in traces),
               "thought_tokens": sum(t["usage"]["thought_tokens"] for t in traces),
               "elapsed_s": round(sum(t["elapsed_s"] for t in traces), 1),
               "retries": sum(len(e.get("retries", [])) for t in traces for e in t["events"] if e["event"] == "llm"),
               "cost_usd": None, "cost_note": "price per token not recorded; fill from the provider's pricing page"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "config"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
