"""Create a manual review sheet and a label table from agent traces.

  python scripts/make_review_sheet.py --traces results/agent-dev-A1-all-b3000/traces.jsonl

Writes next to the traces, in review/:
  sheet.md     : per question - agent answer, tool calls, and the FULL text of every cited chunk,
                 plus the expected answer / gold quotes / absence reason for the grader
  reviews.csv  : the label table you fill in (UTF-8 with BOM, opens in Excel)

Gold and expected answers appear only here, after the agent ran; the agent never saw them.
The "gợi ý" lines (does the cited chunk contain a gold quote?) are heuristics to speed up
reading. They are NOT labels: an id in the context or a quote match does not prove that the
source supports the whole answer (see BENCHMARK.md).
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.config import CHUNKS_JSON, QUESTIONS_JSON  # noqa: E402

COLUMNS = ["query_id", "kind", "status", "citations", "answer_grade", "citation_support",
           "abstention_correct", "context_score", "note"]


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", type=Path, required=True)
    a = ap.parse_args()
    out = a.traces.parent / "review"
    out.mkdir(exist_ok=True)
    traces = [json.loads(l) for l in a.traces.read_text(encoding="utf-8").splitlines() if l.strip()]
    chunks = {c["id"]: c for c in json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))}
    qs = {q["id"]: q for q in json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))}
    cfg = traces[0]["config"]
    md = [f"# Phiếu chấm tay: {cfg['name']}\n",
          f"Model `{cfg['model']}`, công cụ {cfg['tools']}, top_k {cfg['top_k']}, budget {cfg['budget_chars']} ký tự, "
          f"max_searches {cfg['max_searches']}.\n",
          "## Cách chấm (theo BENCHMARK.md)\n",
          "- **answer_grade** (câu có đáp án): 0 = sai/thiếu evidence (hoặc bị từ chối), 1 = đúng một phần, 2 = đúng và đủ.\n"
          "- **citation_support**: một số 1/0 cho MỖI trích dẫn theo thứ tự trong cột `citations`, cách nhau bằng dấu cách (vd `1 0 1`). "
          "1 = đoạn đó hỗ trợ điều được khẳng định; id không có trong context hoặc không hỗ trợ = 0.\n"
          "- **abstention_correct** (câu thiếu bằng chứng): 1 nếu agent từ chối/nêu rõ không đủ bằng chứng và không thêm khẳng định vô căn cứ; 0 nếu không.\n"
          "- **context_score** (tùy chọn, bắt buộc cho ≥5 câu test): 0 = context không có evidence, 1 = có nhưng thiếu điều kiện hoặc nguồn, 2 = đủ.\n"
          "- Câu có đáp án mà agent từ chối: `answer_grade` = 0 (đã điền sẵn).\n"]
    rows = []
    for t in traces:
        q = qs[t["query_id"]]
        answerable = q.get("answerable", True)
        md.append(f"\n---\n\n## {t['query_id']} ({'có đáp án' if answerable else 'THIẾU BẰNG CHỨNG'}, {q.get('qtype')})\n")
        md.append(f"**Câu hỏi:** {q['question']}\n")
        if answerable:
            md.append(f"**Đáp án mong đợi:** {q['expected_answer']}\n")
            md.append(f"**Bằng chứng gold (gold_mode={q.get('gold_mode')}):**\n" + "".join(
                f"- [{g['source_id']} tr.{g['page']}] {g['evidence']}\n" for g in q["gold"]))
        else:
            md.append(f"**Hành vi mong đợi:** từ chối. **Lý do vắng bằng chứng:** {q['absence_reason']}\n")
        md.append(f"**Agent:** status=`{t['status']}`{' (' + t['reason'] + ')' if t.get('reason') else ''}, "
                  f"{t['n_searches']} lượt tìm, context {len(t['context_ids'])} chunk\n")
        for e in t["events"]:
            if e["event"] == "search":
                md.append(f"- `{e['tool']}` truy vấn: {e['query']!r}"
                          f"{' filter=' + json.dumps(e['filter'], ensure_ascii=False) if e['filter'] else ''}"
                          f" -> top: {[r['id'].split(':', 1)[1] for r in e['results']]}"
                          f" | vào context: {[i.split(':', 1)[1] for i in e['new_context_ids']]}"
                          f" | bị loại do budget: {[i.split(':', 1)[1] for i in e['dropped_ids']]}\n")
        md.append(f"\n**Câu trả lời của agent:**\n\n> " + (t["answer"] or "(trống)").replace("\n", "\n> ") + "\n")
        cites = t["citations"]
        ctx = set(t["context_ids"])
        for i, c in enumerate(cites, 1):
            text = chunks.get(c, {}).get("text")
            tag = "trong context" if c in ctx else "NGOÀI context"
            hint = ""
            if text and answerable:
                has = [squash(g["evidence"]) in squash(text) for g in q["gold"]]
                hint = f" — gợi ý: chứa {sum(has)}/{len(has)} trích dẫn gold"
            md.append(f"\n**Trích dẫn {i}: `{c}`** ({tag}{'' if text else ', id KHÔNG TỒN TẠI trong corpus'}{hint})\n")
            if text:
                md.append("```\n" + text + "\n```\n")
        rows.append({"query_id": t["query_id"], "kind": "answerable" if answerable else "unanswerable",
                     "status": t["status"], "citations": " | ".join(cites),
                     "answer_grade": "0" if (answerable and t["status"] == "abstain") else "",
                     "citation_support": "", "abstention_correct": "", "context_score": "", "note": ""})
    (out / "sheet.md").write_text("".join(md), encoding="utf-8")
    with open(out / "reviews.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} questions -> {out / 'sheet.md'}, {out / 'reviews.csv'}")


if __name__ == "__main__":
    main()
