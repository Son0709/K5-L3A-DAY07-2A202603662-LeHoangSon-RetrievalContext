"""Retrieval comparison on one split: Hit@1, Evidence Hit@3, MRR, Context Evidence Rate.

Run from the repo root:
  python -m rag.evaluate --split dev --budget 800 --out results/retrieval-dev-b800

Definitions (same for every method, see BENCHMARK.md):
  * An evidence quote is covered by a chunk if the chunk has the same source_id, the quote's
    page lies in [page, page_end] and the whitespace-normalised quote is a substring of the text.
  * Question gold_mode "any": hit if some quote is covered; "all": every quote must be covered
    (by the union of the chunks considered, so multi-chunk evidence is counted).
  * Hit@k uses the top-k ranked chunks; Context Evidence Rate uses the chunks that survive
    context packing under --budget (chars, source header included, whole chunks only).
Only answerable questions are in the denominators. Test needs --confirm-final.
"""
import argparse
import json
import re
import statistics
import time
from pathlib import Path

from .config import CHUNKS_JSON, QUESTIONS_JSON, ROOT
from .dense import DenseRetriever
from .hybrid import HybridRetriever
from .lexical import BM25Retriever


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def covered(chunk: dict, g: dict) -> bool:
    lo, hi = chunk["page"], chunk["metadata"].get("page_end", chunk["page"])
    return (chunk["source_id"] == g["source_id"] and lo <= g["page"] <= hi
            and squash(g["evidence"]) in squash(chunk["text"]))


def satisfied(q: dict, chunks: list[dict]) -> bool:
    flags = [any(covered(c, g) for c in chunks) for g in q["gold"]]
    return all(flags) if q.get("gold_mode") == "all" else any(flags)


def pack_context(results: list[dict], budget: int) -> list[dict]:
    """Same rule as starter/baseline.py: keep whole chunks in rank order while within budget."""
    kept, blocks = [], []
    for c in results:
        block = f"[{c['id']} | {c['source']} | page {c['page']}]\n{c['text']}"
        if len("\n\n".join(blocks + [block])) <= budget:
            blocks.append(block)
            kept.append(c)
    return kept


def evaluate(retriever, questions: list[dict], budget: int, use_filter: bool,
             top_k: int = 3) -> tuple[dict, list[dict]]:
    traces = []
    for q in questions:
        flt = q.get("filter") if use_filter else None
        t0 = time.perf_counter()
        results = retriever.search(q["question"], filters=flt, top_k=top_k)
        ms = (time.perf_counter() - t0) * 1000
        ctx = pack_context(results, budget)
        rr = next((1 / i for i, c in enumerate(results, 1) if satisfied(q, [c])), 0.0)
        traces.append({
            "query_id": q["id"], "method": retriever.name, "filter": flt, "budget_chars": budget,
            "results": [{"id": c["id"], "score": round(c["score"], 4), "page": c["page"],
                         "source_id": c["source_id"]} for c in results],
            "hit1": satisfied(q, results[:1]), "hit3": satisfied(q, results[:3]),
            "rr": rr, "context_ids": [c["id"] for c in ctx], "context_hit": satisfied(q, ctx),
            "elapsed_ms": round(ms, 2)})
    n = len(traces)
    summary = {"method": retriever.name, "n": n, "use_filter": use_filter, "budget_chars": budget,
               "hit1": f"{sum(t['hit1'] for t in traces)}/{n}",
               "hit3": f"{sum(t['hit3'] for t in traces)}/{n}",
               "context_evidence_rate": f"{sum(t['context_hit'] for t in traces)}/{n}",
               "mrr@3": round(sum(t["rr"] for t in traces) / n, 3),
               "median_ms": round(statistics.median(t["elapsed_ms"] for t in traces), 2),
               "cost_usd": 0}
    return summary, traces


def build_methods(chunks: list[dict]) -> list:
    dense = DenseRetriever()
    uni, unibi = BM25Retriever(chunks, "uni"), BM25Retriever(chunks, "unibi")
    return [dense, uni, unibi, HybridRetriever(dense, uni), HybridRetriever(dense, unibi)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--budget", type=int, default=800, help="context budget in characters")
    ap.add_argument("--use-filter", action="store_true", help="apply user-supplied q['filter']")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--confirm-final", action="store_true",
                    help="required for test: only after the configuration is frozen on dev")
    args = ap.parse_args()
    if args.split == "test" and not args.confirm_final:
        raise SystemExit("Refusing to run test without --confirm-final (freeze the config on dev first)")
    chunks = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))
    qs = [q for q in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
          if q["split"] == args.split and q.get("gold")]  # answerable only
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rows, all_traces = [], []
    for m in build_methods(chunks):
        s, t = evaluate(m, qs, args.budget, args.use_filter)
        rows.append(s)
        all_traces += t
        print(f"{s['method']:<42} Hit@1 {s['hit1']:>6}  Hit@3 {s['hit3']:>6}  "
              f"CtxEv {s['context_evidence_rate']:>6}  MRR {s['mrr@3']:.3f}  {s['median_ms']:>7.1f} ms")
    (out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "traces.json").write_text(json.dumps(all_traces, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
