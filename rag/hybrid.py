"""Hybrid retrieval: Reciprocal Rank Fusion of dense and lexical rankings.

RRF uses ranks only, so the incomparable score scales (cosine vs BM25) never get added.
score(d) = sum over rankers of 1 / (rrf_k + rank_in_ranker(d)), rank starting at 1.
"""
from typing import Any


class HybridRetriever:
    def __init__(self, dense, lexical, depth: int = 20, rrf_k: int = 60) -> None:
        self.name = f"hybrid-rrf({dense.name}+{lexical.name})"
        self.dense, self.lexical, self.depth, self.rrf_k = dense, lexical, depth, rrf_k

    def search(self, query: str, *, filters: dict[str, Any] | None = None,
               top_k: int = 3) -> list[dict[str, Any]]:
        fused: dict[str, dict[str, Any]] = {}
        for ranker in (self.dense, self.lexical):
            for rank, hit in enumerate(ranker.search(query, filters=filters, top_k=self.depth), 1):
                entry = fused.setdefault(hit["id"], {**hit, "score": 0.0, "ranks": {}})
                entry["score"] += 1.0 / (self.rrf_k + rank)
                entry["ranks"][ranker.name] = rank
        ranked = sorted(fused.values(), key=lambda h: (-h["score"], h["id"]))
        return ranked[:top_k]
