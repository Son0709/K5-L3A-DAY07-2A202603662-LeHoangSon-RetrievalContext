"""Query embedder identical to Day 6 (multilingual-e5-small, mean pooling, L2 norm, "query: ").

Day 6 documents were embedded with the "passage: " prefix, so queries MUST use "query: ";
a different model, prefix or pooling would make the query vectors incompatible with the index.
Fails loudly if the model cannot be loaded; there is no mock fallback.
"""
import torch
from transformers import AutoModel, AutoTokenizer

from .config import EMBED_DIM, EMBED_MODEL, MAX_TOKENS


class QueryEmbedder:
    def __init__(self, model_name: str = EMBED_MODEL) -> None:
        self.model_name = model_name
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).eval()
        except Exception as exc:
            raise RuntimeError(f"Cannot load embedding model {model_name!r}: {exc}") from exc
        self.dimensions = int(self.model.config.hidden_size)
        if self.dimensions != EMBED_DIM:
            raise RuntimeError(f"embedding dim {self.dimensions} != index dim {EMBED_DIM}")

    @torch.inference_mode()
    def embed_query(self, text: str) -> list[float]:
        enc = self.tokenizer([f"query: {text}"], padding=True, truncation=True,
                             max_length=MAX_TOKENS, return_tensors="pt")
        hidden = self.model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1)
        return torch.nn.functional.normalize(pooled, p=2, dim=1)[0].tolist()
