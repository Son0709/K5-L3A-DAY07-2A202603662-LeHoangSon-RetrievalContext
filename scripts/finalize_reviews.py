"""Turn the filled reviews.csv into JSON and aggregate it with starter/agent_metrics.py.

  python scripts/finalize_reviews.py --traces results/agent-dev-A1-all-b3000/traces.jsonl --split dev

Reads review/reviews.csv (next to the traces); fails with the list of problems if any label is
missing or inconsistent, so a half-filled sheet can never produce a summary.
Writes review/{cases,traces,reviews}.json and review/summary.json.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "starter"))
from agent_metrics import aggregate  # noqa: E402
from rag.config import QUESTIONS_JSON  # noqa: E402

TRUE, FALSE = {"1", "true", "đúng", "x"}, {"0", "false", "sai"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", type=Path, required=True)
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    a = ap.parse_args()
    out = a.traces.parent / "review"
    traces = [json.loads(l) for l in a.traces.read_text(encoding="utf-8").splitlines() if l.strip()]
    qs = {q["id"]: q for q in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))}
    table = {r["query_id"]: r for r in csv.DictReader(open(out / "reviews.csv", encoding="utf-8-sig", newline=""))}
    problems, reviews, cases = [], [], []
    for t in traces:
        qid, q = t["query_id"], qs[t["query_id"]]
        answerable = q.get("answerable", True)
        cases.append({"id": qid, "split": q["split"], "answerable": answerable})
        if t["status"] == "error":
            continue
        row = table.get(qid)
        if row is None:
            problems.append(f"{qid}: không có dòng trong reviews.csv")
            continue
        review: dict = {"query_id": qid}
        sup = row["citation_support"].replace(",", " ").split()
        if len(sup) != len(t["citations"]) or any(s.lower() not in TRUE | FALSE for s in sup):
            problems.append(f"{qid}: citation_support cần {len(t['citations'])} giá trị 1/0 (có {sup})")
        review["citation_support"] = [s.lower() in TRUE for s in sup]
        if answerable:
            if row["answer_grade"] not in ("0", "1", "2"):
                problems.append(f"{qid}: answer_grade phải là 0, 1 hoặc 2")
            else:
                review["answer_grade"] = int(row["answer_grade"])
        else:
            v = row["abstention_correct"].strip().lower()
            if v not in TRUE | FALSE:
                problems.append(f"{qid}: abstention_correct phải là 1 hoặc 0")
            else:
                review["abstention_correct"] = v in TRUE
        if row["context_score"].strip():
            review["context_score"] = int(row["context_score"])
        reviews.append(review)
    if problems:
        print("\n".join(f"PROBLEM: {p}" for p in problems))
        raise SystemExit(1)
    cases = [c for c in cases if c["split"] == a.split]
    for name, obj in (("cases", cases), ("traces", traces), ("reviews", reviews)):
        (out / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    ids = {c["id"] for c in cases}
    report = {"split": a.split, "config": traces[0]["config"]["name"],
              **aggregate(cases, [t for t in traces if t["query_id"] in ids],
                          [r for r in reviews if r["query_id"] in ids])}
    ctx = Counter(r["context_score"] for r in reviews if "context_score" in r)
    if ctx:
        report["context_score_distribution"] = {str(k): v for k, v in sorted(ctx.items())}
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
