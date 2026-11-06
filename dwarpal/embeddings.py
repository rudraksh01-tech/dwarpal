"""Text embeddings for semantic drift and attack similarity.

Gemini's multilingual embedding model is used when GEMINI_API_KEY is set.
Without a key (tests, CI, offline demo) a local character n-gram embedding
is used instead: weaker, but deterministic and free. Every vector is
L2-normalised, so a dot product is cosine similarity.
"""

import hashlib
import os
from functools import lru_cache

import numpy as np

from dwarpal import config


def _local_embedding(text, dimensions=config.EMBEDDING_DIMENSIONS):
    """Hash character 3-grams into a fixed-size vector (works for any script)."""
    vector = np.zeros(dimensions, dtype=np.float32)
    padded = f"  {text.lower()}  "

    for index in range(len(padded) - 2):
        digest = hashlib.blake2b(padded[index:index + 3].encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    return vector


@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())


def _gemini_embeddings(texts):
    from google.genai import types

    result = _gemini_client().models.embed_content(
        model=config.GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=config.EMBEDDING_DIMENSIONS,
        ),
    )
    return np.asarray([embedding.values for embedding in result.embeddings], dtype=np.float32)


def backend_name():
    return "gemini" if config.use_gemini_embeddings() else "local-ngram"


_cache = {}


def embed(texts):
    """Return an (n, d) matrix of normalised embeddings, cached per text."""
    missing = [text for text in dict.fromkeys(texts) if (backend_name(), text) not in _cache]

    if missing:
        if config.use_gemini_embeddings():
            vectors = _gemini_embeddings(missing)
        else:
            vectors = np.stack([_local_embedding(text) for text in missing])

        for text, vector in zip(missing, vectors):
            norm = np.linalg.norm(vector)
            _cache[(backend_name(), text)] = vector / norm if norm else vector

    return np.stack([_cache[(backend_name(), text)] for text in texts])


def cosine(a, b):
    vectors = embed([a, b])
    return float(vectors[0] @ vectors[1])
