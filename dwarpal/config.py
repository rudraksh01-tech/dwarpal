"""Settings, read from environment variables (a local .env is loaded if present)."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _float(name, default):
    return float(os.getenv(name, default))


# ---------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------

# Injection score (0..1) at or above which text is blocked. One weak signal
# (e.g. the word "send" near "email") scores 0.5 and is only flagged.
BLOCK_SCORE = _float("DWARPAL_BLOCK_SCORE", 0.6)
FLAG_SCORE = _float("DWARPAL_FLAG_SCORE", 0.3)

# Semantic drift (1 - cosine) between the approved and the new description
# of a tool, above which a change is treated as a change in meaning.
DRIFT_THRESHOLD = _float("DWARPAL_DRIFT_THRESHOLD", 0.15)


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

GROQ_MODEL = os.getenv("DWARPAL_AGENT_MODEL", "openai/gpt-oss-20b")
PROMPT_GUARD_MODEL = "meta-llama/llama-prompt-guard-2-86m"

GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


def use_gemini_embeddings():
    """Gemini embeddings when a key is set, unless turned off (tests set this)."""
    if os.getenv("DWARPAL_EMBEDDINGS", "auto") == "local":
        return False

    return bool((os.getenv("GEMINI_API_KEY") or "").strip())


# ---------------------------------------------------------
# Storage (in-memory fallbacks when these are not set)
# ---------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")  # Postgres with the pgvector extension
REDIS_URL = os.getenv("REDIS_URL")


# ---------------------------------------------------------
# Public demo API
# ---------------------------------------------------------

CORS_ORIGINS = [origin.strip() for origin in os.getenv(
    "DWARPAL_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]

# Each live run costs ~10-20 free-tier model calls
RUNS_PER_MINUTE = int(os.getenv("DWARPAL_RUNS_PER_MINUTE", "3"))
CHECKS_PER_MINUTE = int(os.getenv("DWARPAL_CHECKS_PER_MINUTE", "10"))
