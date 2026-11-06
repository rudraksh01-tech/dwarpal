"""Storage for tool pins, the audit log and the known-attack library.

PostgresStore (with pgvector) is used when DATABASE_URL is set; MemoryStore
otherwise, so the gateway, tests and the offline demo need no database.
Both expose the same methods.
"""

import json
import threading
import time
from collections import Counter, deque

import numpy as np

from dwarpal import config, embeddings
from dwarpal.checks.descriptor import Pin


MAX_MEMORY_EVENTS = 2000


class MemoryStore:
    backend = "memory"

    def __init__(self):
        self.pins = {}
        self.events = deque(maxlen=MAX_MEMORY_EVENTS)
        self.attacks = []          # (id, text, language, category)
        self._attack_vectors = None
        self._lock = threading.Lock()

    # ---- pins ----

    def get_pin(self, server, tool):
        return self.pins.get((server, tool))

    def save_pin(self, pin):
        with self._lock:
            self.pins[(pin.server, pin.tool)] = pin

    def list_pins(self):
        return list(self.pins.values())

    # ---- audit log ----

    def log_event(self, event):
        event = {"id": len(self.events) + 1, "ts": time.time(), **event}

        with self._lock:
            self.events.append(event)

        return event

    def recent_events(self, limit=50):
        return list(self.events)[-limit:][::-1]

    def stats(self):
        events = list(self.events)
        decisions = Counter(event["decision"] for event in events)
        checks = Counter(
            finding["check"]
            for event in events if event["decision"] != "allow"
            for finding in event.get("findings", [])
        )
        latencies = sorted(event.get("latency_ms", 0) for event in events)

        def percentile(p):
            if not latencies:
                return None
            return round(latencies[min(len(latencies) - 1, int(p * len(latencies)))], 1)

        return {
            "events": len(events),
            "decisions": dict(decisions),
            "blocked_by_check": dict(checks),
            "latency_ms": {"p50": percentile(0.5), "p95": percentile(0.95)},
        }

    # ---- known attacks (vector search) ----

    def add_attacks(self, items):
        """items: [{"text", "language", "category"}]"""
        with self._lock:
            for item in items:
                self.attacks.append((len(self.attacks) + 1, item["text"], item.get("language"), item.get("category")))

            self._attack_vectors = None

    def similar_attacks(self, text, k=3):
        if not self.attacks:
            return []

        if self._attack_vectors is None:
            self._attack_vectors = embeddings.embed([attack[1] for attack in self.attacks])

        scores = self._attack_vectors @ embeddings.embed([text])[0]
        order = np.argsort(-scores)[:k]

        return [
            {"id": self.attacks[i][0], "text": self.attacks[i][1], "language": self.attacks[i][2],
             "category": self.attacks[i][3], "similarity": round(float(scores[i]), 3)}
            for i in order
        ]


def _vector_literal(vector):
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


class PostgresStore(MemoryStore):
    """Same interface, persisted in Postgres; vectors in pgvector columns.

    Tables are created on first use. Similar-attack search uses an HNSW
    index with cosine distance (<=>).
    """

    backend = "postgres+pgvector"

    SCHEMA = f"""
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS tool_pins (
        server text NOT NULL,
        tool text NOT NULL,
        fingerprint text NOT NULL,
        canonical text NOT NULL,
        text text NOT NULL,
        embedding vector({config.EMBEDDING_DIMENSIONS}),
        approved boolean NOT NULL DEFAULT true,
        history jsonb NOT NULL DEFAULT '[]',
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (server, tool)
    );
    CREATE TABLE IF NOT EXISTS audit_events (
        id bigserial PRIMARY KEY,
        ts double precision NOT NULL,
        body jsonb NOT NULL
    );
    CREATE TABLE IF NOT EXISTS known_attacks (
        id bigserial PRIMARY KEY,
        text text NOT NULL UNIQUE,
        language text,
        category text,
        embedding vector({config.EMBEDDING_DIMENSIONS}) NOT NULL
    );
    CREATE INDEX IF NOT EXISTS known_attacks_embedding
        ON known_attacks USING hnsw (embedding vector_cosine_ops);
    """

    def __init__(self, url):
        super().__init__()
        import psycopg

        self.connection = psycopg.connect(url, autocommit=True)
        self.connection.execute(self.SCHEMA)

    def get_pin(self, server, tool):
        row = self.connection.execute(
            "SELECT fingerprint, canonical, text, approved, history FROM tool_pins WHERE server=%s AND tool=%s",
            (server, tool),
        ).fetchone()

        if not row:
            return None

        return Pin(server, tool, row[0], row[1], row[2], row[3], list(row[4]))

    def save_pin(self, pin):
        vector = _vector_literal(embeddings.embed([pin.text])[0])
        self.connection.execute(
            """INSERT INTO tool_pins (server, tool, fingerprint, canonical, text, embedding, approved, history)
               VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s::jsonb)
               ON CONFLICT (server, tool) DO UPDATE SET
                 fingerprint=EXCLUDED.fingerprint, canonical=EXCLUDED.canonical, text=EXCLUDED.text,
                 embedding=EXCLUDED.embedding, approved=EXCLUDED.approved, history=EXCLUDED.history,
                 updated_at=now()""",
            (pin.server, pin.tool, pin.fingerprint, pin.canonical, pin.text, vector, pin.approved, json.dumps(pin.history)),
        )

    def list_pins(self):
        rows = self.connection.execute(
            "SELECT server, tool, fingerprint, canonical, text, approved, history FROM tool_pins ORDER BY server, tool"
        ).fetchall()
        return [Pin(r[0], r[1], r[2], r[3], r[4], r[5], list(r[6])) for r in rows]

    def log_event(self, event):
        event = {"ts": time.time(), **event}
        row = self.connection.execute(
            "INSERT INTO audit_events (ts, body) VALUES (%s, %s::jsonb) RETURNING id",
            (event["ts"], json.dumps(event, ensure_ascii=False)),
        ).fetchone()
        event["id"] = row[0]
        self.events.append(event)   # recent events stay in memory for the dashboard
        return event

    def add_attacks(self, items):
        texts = [item["text"] for item in items]
        vectors = embeddings.embed(texts)

        with self.connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO known_attacks (text, language, category, embedding)
                   VALUES (%s, %s, %s, %s::vector) ON CONFLICT (text) DO NOTHING""",
                [(item["text"], item.get("language"), item.get("category"), _vector_literal(vector))
                 for item, vector in zip(items, vectors)],
            )

    def similar_attacks(self, text, k=3):
        vector = _vector_literal(embeddings.embed([text])[0])
        rows = self.connection.execute(
            """SELECT id, text, language, category, 1 - (embedding <=> %s::vector) AS similarity
               FROM known_attacks ORDER BY embedding <=> %s::vector LIMIT %s""",
            (vector, vector, k),
        ).fetchall()
        return [{"id": r[0], "text": r[1], "language": r[2], "category": r[3], "similarity": round(float(r[4]), 3)}
                for r in rows]


_store = None


def get_store():
    global _store

    if _store is None:
        _store = PostgresStore(config.DATABASE_URL) if config.DATABASE_URL else MemoryStore()

    return _store


def reset_store(store=None):
    global _store
    _store = store
