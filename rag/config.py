"""Paths and Day 6 index settings. Override the Day 6 location with env DAY6_DIR."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAY6_DIR = Path(os.environ.get(
    "DAY6_DIR", ROOT / "K5-L3A-Day06-LeHoangSon-03662-DataIngestionEngineering"))
DAY6_RESULTS = DAY6_DIR / "starter" / "results"

# Day 6 index: strategy B (article-aware chunks), cosine, E5 with query/passage prefixes.
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", DAY6_RESULTS / "chroma"))
COLLECTION = os.environ.get("CHROMA_COLLECTION", "lab_B")
EMBED_MODEL = "intfloat/multilingual-e5-small"
EMBED_DIM = 384
MAX_TOKENS = 512

DATA_DIR = ROOT / "data"
CHUNKS_JSON = DATA_DIR / "chunks.json"
QUESTIONS_JSON = DATA_DIR / "questions.json"
