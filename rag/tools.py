"""Retrieval tools exposed to the agent, and the per-question context session.

A SearchSession accumulates retrieved chunks across tool calls, de-duplicates them, and keeps
the ones that fit the context budget (whole chunks, arrival order, same rule as pack_context).
The kept chunks are exactly the "final context" measured by Context Evidence Rate and the only
ids the answer may cite. No gold or benchmark label ever enters this module.
"""
import time
from typing import Any

from google.genai import types

from .evaluate import pack_context

DOC_TYPES = ["Luật", "Nghị định"]
S = types.Schema

TOOLS = {
    "dense": ("search_dense", "Tìm đoạn văn bản theo ngữ nghĩa (embedding). Phù hợp khi câu hỏi "
              "diễn đạt khác với câu chữ trong luật."),
    "bm25": ("search_keyword", "Tìm đoạn văn bản theo từ khóa (BM25). Phù hợp khi câu hỏi có "
             "thuật ngữ, con số hoặc cụm từ cần khớp chính xác."),
    "hybrid": ("search_hybrid", "Kết hợp tìm theo ngữ nghĩa và theo từ khóa (RRF)."),
}
FINAL_NAME = "final_answer"


def declarations(keys: list[str]) -> list[types.FunctionDeclaration]:
    out = []
    for k in keys:
        name, desc = TOOLS[k]
        out.append(types.FunctionDeclaration(name=name, description=desc, parameters=S(
            type="OBJECT", required=["query"], properties={
                "query": S(type="STRING", description="Truy vấn tìm kiếm tiếng Việt, tự chứa đủ ý."),
                "document_type": S(type="STRING", enum=DOC_TYPES, description=(
                    "Chỉ đặt khi chính câu hỏi nêu rõ loại văn bản (Luật hay Nghị định); "
                    "nếu không, bỏ trống."))})))
    out.append(types.FunctionDeclaration(name=FINAL_NAME, description=(
        "Trả lời cuối cùng cho người dùng. Gọi đúng một lần khi đã đủ bằng chứng hoặc khi xác định "
        "không đủ bằng chứng trong kết quả tìm kiếm."), parameters=S(
        type="OBJECT", required=["answer", "citations", "enough_evidence"], properties={
            "answer": S(type="STRING", description="Câu trả lời tiếng Việt, ghi [chunk-id] sau mỗi ý "
                        "được hỗ trợ. Nếu không đủ bằng chứng, nêu ngắn gọn còn thiếu gì."),
            "citations": S(type="ARRAY", items=S(type="STRING"), description="Danh sách chunk-id đã dùng."),
            "enough_evidence": S(type="BOOLEAN", description="false nếu kết quả tìm kiếm không đủ để trả lời.")})))
    return out


class SearchSession:
    def __init__(self, retrievers: dict[str, Any], top_k: int = 3, budget: int = 3000,
                 max_searches: int = 4) -> None:
        self.retrievers, self.top_k, self.budget = retrievers, top_k, budget
        self.max_searches, self.n_searches = max_searches, 0
        self.pool: list[dict] = []
        self.kept_ids: list[str] = []
        self.tool_names = {TOOLS[k][0]: k for k in retrievers}

    @property
    def context(self) -> list[dict]:
        by_id = {c["id"]: c for c in self.pool}
        return [by_id[i] for i in self.kept_ids]

    def search(self, tool: str, args: dict[str, Any]) -> tuple[dict, dict]:
        """Run one retrieval call -> (response sent to the model, trace event)."""
        key = self.tool_names[tool]
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            err = {"error": "query phải là chuỗi không rỗng"}
            return err, {"event": "tool_error", "tool": tool, "args": args, **err}
        if self.n_searches >= self.max_searches:
            err = {"error": f"đã đạt giới hạn {self.max_searches} lượt tìm; hãy gọi final_answer"}
            return err, {"event": "search_limit", "tool": tool, "args": args}
        dt = args.get("document_type")
        filters = {"document_type": dt} if dt in DOC_TYPES else None
        t0 = time.perf_counter()
        results = self.retrievers[key].search(query, filters=filters, top_k=self.top_k)
        ms = (time.perf_counter() - t0) * 1000
        self.n_searches += 1
        before = set(self.kept_ids)
        known = {c["id"] for c in self.pool}
        self.pool += [c for c in results if c["id"] not in known]
        self.kept_ids = [c["id"] for c in pack_context(self.pool, self.budget)]
        kept = set(self.kept_ids)
        new = [c for c in results if c["id"] in kept and c["id"] not in before]
        response = {
            "results": [{"id": c["id"], "van_ban": c["metadata"].get("title"), "so_hieu": c["metadata"].get("doc_number"),
                         "dieu": c["metadata"].get("article"), "trang": c["page"], "noi_dung": c["text"]} for c in new],
            "da_co_trong_ngu_canh": [c["id"] for c in results if c["id"] in before],
            "bo_do_vuot_ngan_sach": [c["id"] for c in results if c["id"] not in kept]}
        event = {"event": "search", "tool": tool, "method": key, "query": query, "filter": filters,
                 "results": [{"rank": i, "id": c["id"], "score": round(c["score"], 4), "page": c["page"],
                              "source_id": c["source_id"]} for i, c in enumerate(results, 1)],
                 "new_context_ids": [c["id"] for c in new], "dropped_ids": response["bo_do_vuot_ngan_sach"],
                 "context_ids": list(self.kept_ids), "elapsed_ms": round(ms, 2)}
        return response, event
