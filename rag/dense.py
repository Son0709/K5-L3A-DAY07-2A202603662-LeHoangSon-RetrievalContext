"""Dense retrieval over the Day 6 ChromaDB index (collection lab_B by default).

Implements the starter `Retriever` protocol: returns at most top_k chunks with
id, text, source_id, source, page, metadata and score (cosine similarity = 1 - distance).
"""
import sys
import time
import types
from typing import Any

try:
    import grpc  # noqa: F401
except ImportError:
    # Same workaround as Day 6: some machines block grpc's native DLL, which chromadb only
    # needs for an optional telemetry exporter. Storage and search are unaffected.
    _stub = types.ModuleType("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
    _stub.OTLPSpanExporter = object
    sys.modules[_stub.__name__] = _stub

import chromadb

from .config import CHROMA_PATH, COLLECTION
from .embedder import QueryEmbedder


class DenseRetriever:
    name = "dense"

    def __init__(self, embedder: QueryEmbedder | None = None, path=CHROMA_PATH,
                 collection: str = COLLECTION) -> None:
        if not (path / "chroma.sqlite3").exists():
            raise RuntimeError(f"Day 6 Chroma index not found at {path}; "
                               "run `python -m src.index` in the Day 6 starter first")
        self.embedder = embedder or QueryEmbedder()
        client = chromadb.PersistentClient(
            path=str(path), settings=chromadb.Settings(anonymized_telemetry=False))
        self.col = client.get_collection(collection)  # raises if the collection is missing
        if self.col.count() == 0:
            raise RuntimeError(f"collection {collection!r} is empty")

    @staticmethod
    def _where(filters: dict[str, Any] | None):
        if not filters:
            return None
        items = [{k: v} for k, v in filters.items()]
        return items[0] if len(items) == 1 else {"$and": items}

    def search(self, query: str, *, filters: dict[str, Any] | None = None,
               top_k: int = 3) -> list[dict[str, Any]]:
        vec = self.embedder.embed_query(query)
        res = self.col.query(query_embeddings=[vec], n_results=top_k, where=self._where(filters),
                             include=["documents", "metadatas", "distances"])
        out = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                        res["metadatas"][0], res["distances"][0]):
            out.append({"id": cid, "text": doc, "source_id": meta["document_id"],
                        "source": meta["source"], "page": meta["page"],
                        "metadata": meta, "score": 1.0 - dist})
        return out

    def timed_search(self, query: str, **kw) -> tuple[list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        return self.search(query, **kw), time.perf_counter() - t0
