import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Overridable via env in case Google deprecates/renames the model again.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

KNOWLEDGE_BASE_DIR = BASE_DIR / "datasets" / "knowledge_base"

# Kept for backward compatibility with any script referencing a single PDF.
PDF_PATH = KNOWLEDGE_BASE_DIR / "Myntra Policies.pdf"

VECTORSTORE_PATH = BASE_DIR / "vectorstore" / "faiss_index"

DATA_DIR = BASE_DIR / "datasets"
TRANSACTION_DATA_DIR = DATA_DIR / "transaction_data"
MASTER_DATA_DIR = DATA_DIR / "master_data"

RAG_SCORE_THRESHOLD = 0.55