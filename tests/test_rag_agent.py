"""Control-flow tests with a scripted fake LLM and a fake retriever (code checks only, not quality)."""
import unittest

from google.genai import types

from rag.agent import run_agent
from rag.hybrid import HybridRetriever
from rag.lexical import BM25Retriever, tokenize
from rag.llm import LLMError
from rag.tools import FINAL_NAME, SearchSession

CHUNKS = [
    {"id": f"c{i}", "text": t, "source_id": "s", "source": "s.pdf", "page": i + 1,
     "metadata": {"title": "T", "doc_number": "1", "document_type": "Luật", "article": f"Điều {i}", "page_end": i + 1}}
    for i, t in enumerate(["thông báo vi phạm trong 72 giờ", "xóa dữ liệu khi có yêu cầu", "chữ ký số hợp lệ"])]


def reply(*calls, text=""):
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in calls]
    return {"content": types.Content(role="model", parts=parts), "calls": list(calls), "text": text,
            "usage": {"prompt_tokens": 10, "output_tokens": 5, "thought_tokens": 0},
            "attempts": [], "elapsed_ms": 1}


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def generate(self, contents, system, declarations):
        self.seen.append(len(contents))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def session(budget=3000, max_searches=4):
    return SearchSession({"bm25": BM25Retriever(CHUNKS)}, top_k=2, budget=budget, max_searches=max_searches)


class AgentTests(unittest.TestCase):
    def test_answer_with_valid_citation(self):
        llm = FakeLLM([reply(("search_keyword", {"query": "thông báo vi phạm 72 giờ"})),
                       reply((FINAL_NAME, {"answer": "72 giờ [c0]", "citations": ["c0"], "enough_evidence": True}))])
        r = run_agent("q", llm, session(), tool_keys=["bm25"])
        self.assertEqual((r["status"], r["citations"], r["n_searches"]), ("answered", ["c0"], 1))
        self.assertEqual(llm.seen, [1, 3])  # history grows: question, model call, tool response

    def test_citation_outside_context_is_flagged_not_hidden(self):
        llm = FakeLLM([reply(("search_keyword", {"query": "72 giờ"})),
                       reply((FINAL_NAME, {"answer": "x [c0] [c9]", "citations": ["c0", "c9"], "enough_evidence": True}))])
        r = run_agent("q", llm, session(), tool_keys=["bm25"])
        self.assertEqual((r["status"], r["citations"], r["invalid_citation_ids"]), ("answered", ["c0", "c9"], ["c9"]))

    def test_no_citation_abstains(self):
        llm = FakeLLM([reply(("search_keyword", {"query": "72 giờ"})),
                       reply((FINAL_NAME, {"answer": "x", "citations": [], "enough_evidence": True}))])
        self.assertEqual(run_agent("q", llm, session(), tool_keys=["bm25"])["reason"], "no_citations")

    def test_model_declines(self):
        llm = FakeLLM([reply(("search_keyword", {"query": "72 giờ"})),
                       reply((FINAL_NAME, {"answer": "thiếu", "citations": [], "enough_evidence": False}))])
        self.assertEqual(run_agent("q", llm, session(), tool_keys=["bm25"])["reason"], "model_declined")

    def test_llm_error_is_recorded_not_faked(self):
        r = run_agent("q", FakeLLM([LLMError("boom", [{"code": 429}])]), session(), tool_keys=["bm25"])
        self.assertEqual((r["status"], r["answer"]), ("error", ""))

    def test_search_limit_and_step_limit(self):
        s = session(max_searches=1)
        calls = [reply(("search_keyword", {"query": "72 giờ"})) for _ in range(3)]
        r = run_agent("q", FakeLLM(calls), s, tool_keys=["bm25"], max_steps=3)
        self.assertEqual((r["status"], r["reason"], r["n_searches"]), ("abstain", "step_limit", 1))
        self.assertIn("search_limit", [e["event"] for e in r["events"]])

    def test_context_budget_drops_whole_chunks_and_dedups(self):
        s = session(budget=80)
        _, e1 = s.search("search_keyword", {"query": "thông báo vi phạm 72 giờ xóa dữ liệu"})
        self.assertLessEqual(len(e1["context_ids"]), 1)
        _, e2 = s.search("search_keyword", {"query": "thông báo vi phạm 72 giờ xóa dữ liệu"})
        self.assertEqual(e2["new_context_ids"], [])
        self.assertEqual(len(set(s.kept_ids)), len(s.kept_ids))


class RetrievalTests(unittest.TestCase):
    def test_bm25_filter_and_tokenizers(self):
        r = BM25Retriever(CHUNKS)
        self.assertEqual(r.search("72 giờ", top_k=1)[0]["id"], "c0")
        self.assertEqual(r.search("72 giờ", filters={"document_type": "Nghị định"}), [])
        self.assertIn("thông_báo", tokenize("thông báo vi phạm", "unibi"))

    def test_rrf_fuses_ranks_not_scores(self):
        class Fixed:
            def __init__(self, name, ids):
                self.name, self.ids = name, ids

            def search(self, q, *, filters=None, top_k=3):
                return [{**c, "score": 99.0} for i in self.ids for c in CHUNKS if c["id"] == i][:top_k]
        h = HybridRetriever(Fixed("a", ["c0", "c1"]), Fixed("b", ["c1", "c2"]), depth=5)
        self.assertEqual([x["id"] for x in h.search("q", top_k=3)][0], "c1")  # ranked by both


if __name__ == "__main__":
    unittest.main()
