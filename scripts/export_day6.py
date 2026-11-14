"""Convert Day 6 chunks (strategy B) and benchmark into the Day 7 schema (data/README.md).

Run from the repo root:  python scripts/export_day6.py
Outputs data/chunks.json and data/questions_day6.json (merged into data/questions.json by build_benchmark.py). Only field renames and a split of
`evidence_quotes` into `gold` entries happen here; nothing is guessed or regenerated.

Multi-quote questions (d06, d09, t02) need ALL their quotes: `gold_mode` is "all" for them
(a single-quote question has "any"). Evaluation code must honour `gold_mode`.
Day 6 had no unanswerable questions; new questions live in data/questions_new.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.config import CHUNKS_JSON, DAY6_DIR, DAY6_RESULTS, QUESTIONS_DAY6_JSON  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def convert_chunk(c: dict) -> dict:
    return {"id": c["chunk_id"], "text": c["text"], "source_id": c["document_id"],
            "source": c["source"], "page": c["page"], "metadata": c["metadata"]}


def convert_question(q: dict) -> dict:
    gold = [{"source_id": q["gold_source_id"], "page": q["gold_page"], "evidence": e}
            for e in q["evidence_quotes"]]
    for alt in q.get("alt_gold", []):
        gold.append({"source_id": alt["source_id"], "page": alt["page"],
                     "evidence": alt.get("evidence", "")})
    return {"id": q["id"], "split": q["split"], "qtype": q.get("qtype"), "question": q["question"],
            "expected_answer": q["expected_answer"], "gold": gold,
            "gold_mode": "all" if len(q["evidence_quotes"]) > 1 else "any",
            "filter": q["filter"]}


def main() -> None:
    chunks = [convert_chunk(c) for c in read_jsonl(DAY6_RESULTS / "chunks_B.jsonl")]
    questions = [convert_question(q) for q in read_jsonl(DAY6_DIR / "benchmark" / "questions.jsonl")]
    if len({c["id"] for c in chunks}) != len(chunks):
        raise SystemExit("duplicate chunk ids")
    CHUNKS_JSON.parent.mkdir(exist_ok=True)
    CHUNKS_JSON.write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    QUESTIONS_DAY6_JSON.write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(chunks)} chunks -> {CHUNKS_JSON}\n{len(questions)} questions -> {QUESTIONS_DAY6_JSON}")


if __name__ == "__main__":
    main()
