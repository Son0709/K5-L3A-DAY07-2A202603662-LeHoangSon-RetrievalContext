"""BM25 lexical retrieval over the Day 6 chunks (pure Python, no extra dependency).

Vietnamese words are usually 2+ syllables separated by spaces, so whitespace tokens are
syllables. Two tokenizers are compared on dev (no word segmenter is installed):
  uni    : syllable unigrams
  unibi  : syllable unigrams + adjacent-syllable bigrams (approximates words/phrases)
"""
import math
import re
import unicodedata
from collections import Counter
from typing import Any


def syllables(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def tokenize(text: str, mode: str = "uni") -> list[str]:
    s = syllables(text)
    if mode == "uni":
        return s
    if mode == "unibi":
        return s + [f"{a}_{b}" for a, b in zip(s, s[1:])]
    raise ValueError(f"unknown tokenizer {mode!r}")


def metadata_match(chunk: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    return all(chunk["metadata"].get(k) == v for k, v in filters.items())


class BM25Retriever:
    def __init__(self, chunks: list[dict[str, Any]], tokenizer: str = "uni",
                 k1: float = 1.5, b: float = 0.75) -> None:
        self.name = f"bm25-{tokenizer}"
        self.chunks, self.tokenizer, self.k1, self.b = chunks, tokenizer, k1, b
        self.tf = [Counter(tokenize(c["text"], tokenizer)) for c in chunks]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg_len = sum(self.len) / len(self.len)
        df = Counter(term for t in self.tf for term in t)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, *, filters: dict[str, Any] | None = None,
               top_k: int = 3) -> list[dict[str, Any]]:
        terms = [t for t in tokenize(query, self.tokenizer) if t in self.idf]
        scored = []
        for i, c in enumerate(self.chunks):
            if not metadata_match(c, filters):
                continue
            tf, norm = self.tf[i], self.k1 * (1 - self.b + self.b * self.len[i] / self.avg_len)
            s = sum(self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in terms if t in tf)
            if s > 0:
                scored.append((s, c["id"], c))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{**c, "score": s} for s, _, c in scored[:top_k]]
