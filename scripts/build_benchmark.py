"""Build and verify the Day 7 benchmark against the ORIGINAL page texts of the PDFs.

Run from the repo root (after scripts/export_day6.py):  python scripts/build_benchmark.py

Inputs : data/questions_day6.json (20 Day 6 questions), data/questions_new.json (new questions)
Outputs: data/questions.json (merged benchmark), data/benchmark_report.json (verification)

Checks (any failure exits non-zero, nothing is silently fixed):
  * every evidence quote occurs on its gold page of the Day 6 page texts (whitespace-normalised);
    for new questions the page is LOCATED by search and must be unique unless given explicitly;
  * every quote is retrievable: some Day 6 chunk (strategy B) covers it, so a miss is a retrieval
    problem, not a chunking artefact;
  * unanswerable questions: every absence regex has ZERO matches in the whole corpus;
  * ids unique; no identical evidence quote is shared by a dev and a test question.
The 5 Day 6 "test" questions (t01-t05) were already used to compare strategies in Day 6, so
they are moved to dev (origin "day6-test-seen"); the held-out test is the new t06-t14 + u04-u06.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rag.config import (CHUNKS_JSON, DAY6_DIR, DATA_DIR, QUESTIONS_DAY6_JSON,  # noqa: E402
                        QUESTIONS_JSON, QUESTIONS_NEW_JSON)

sys.path.insert(0, str(DAY6_DIR / "starter"))
from src.corpus import load_all  # noqa: E402  (Day 6 loader: same page texts the index was built from)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    pages, _, _ = load_all()
    page_text = {(p.document_id, p.page): squash(p.text) for p in pages}
    doc_text = {}
    for (d, _), t in sorted(page_text.items()):
        doc_text[d] = doc_text.get(d, "") + " " + t
    chunks = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))
    problems: list[str] = []

    def retrievable(source_id: str, page: int, quote: str) -> bool:
        q = squash(quote)
        return any(c["source_id"] == source_id and c["page"] <= page <= c["metadata"]["page_end"]
                   and q in squash(c["text"]) for c in chunks)

    merged: list[dict] = []
    for q in json.loads(QUESTIONS_DAY6_JSON.read_text(encoding="utf-8")):
        q = {**q, "origin": "day6"}
        if q["split"] == "test":
            q.update(split="dev", origin="day6-test-seen")
        merged.append(q)
    for q in json.loads(QUESTIONS_NEW_JSON.read_text(encoding="utf-8")):
        merged.append({**q, "origin": "day7-new"})

    if len({q["id"] for q in merged}) != len(merged):
        problems.append("duplicate question ids")

    rows = []
    for q in merged:
        if q.get("answerable") is False:
            hits = {}
            for pat in q["absence_checks"]:
                n = sum(len(re.findall(pat, t, flags=re.IGNORECASE)) for t in doc_text.values())
                hits[pat] = n
                if n:
                    problems.append(f"{q['id']}: absence pattern {pat!r} has {n} matches")
            rows.append({"id": q["id"], "split": q["split"], "kind": "unanswerable",
                         "absence_pattern_matches": hits})
            continue
        ok = True
        for g in q["gold"]:
            t = squash(g["evidence"])
            found = sorted(p for (d, p), txt in page_text.items() if d == g["source_id"] and t in txt)
            if "page" in g:
                if g["page"] not in found:
                    ok = False
                    problems.append(f"{q['id']}: quote not on page {g['page']}: {t[:60]!r}")
            elif len(found) == 1:
                g["page"] = found[0]
            else:
                ok = False
                problems.append(f"{q['id']}: quote found on pages {found}, need exactly one or an explicit page: {t[:60]!r}")
                continue
            if ok and not retrievable(g["source_id"], g["page"], g["evidence"]):
                ok = False
                problems.append(f"{q['id']}: no chunk covers quote on page {g['page']}: {t[:60]!r}")
        rows.append({"id": q["id"], "split": q["split"], "kind": "answerable", "evidence_ok": ok,
                     "pages": sorted({g.get("page") for g in q["gold"]}, key=lambda x: (x is None, x))})

    ev = {s: {squash(g["evidence"]) for q in merged if q["split"] == s and q.get("gold")
              for g in q["gold"]} for s in ("dev", "test")}
    shared = ev["dev"] & ev["test"]
    if shared:
        problems.append(f"{len(shared)} identical evidence quotes shared by dev and test")

    count = Counter((q["split"], "unanswerable" if q.get("answerable") is False else "answerable")
                    for q in merged)
    summary = {
        "counts": {f"{s}/{k}": n for (s, k), n in sorted(count.items())},
        "origin": dict(Counter(q["origin"] for q in merged)),
        "qtype": dict(Counter(q.get("qtype") for q in merged)),
        "multi_evidence": sum(q.get("gold_mode") == "all" for q in merged),
        "meets_minimums_BENCHMARK_md": (count[("dev", "answerable")] >= 15 and count[("dev", "unanswerable")] >= 2
                                         and count[("test", "answerable")] >= 5 and count[("test", "unanswerable")] >= 2),
        "meets_SUBMISSION_md": (sum(n for (s, k), n in count.items() if k == "answerable") >= 20
                                and sum(n for (s, k), n in count.items() if k == "unanswerable") >= 4),
        "problems": problems, "rows": rows}
    (DATA_DIR / "benchmark_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if problems:
        print("\n".join(f"PROBLEM: {p}" for p in problems))
        raise SystemExit(1)
    QUESTIONS_JSON.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in summary.items() if k not in ("rows", "problems")})


if __name__ == "__main__":
    main()
