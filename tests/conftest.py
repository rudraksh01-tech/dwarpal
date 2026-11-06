import os

# Tests never call Groq or Gemini: model layers are skipped and embeddings
# use the local n-gram backend, so the suite runs offline and in CI.
os.environ["DWARPAL_OFFLINE"] = "1"
os.environ["DWARPAL_EMBEDDINGS"] = "local"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

import pytest  # noqa: E402

from dwarpal.cache import MemoryCache, reset_cache  # noqa: E402
from dwarpal.store import reset_store  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state():
    reset_cache(MemoryCache())
    reset_store(None)
    yield
