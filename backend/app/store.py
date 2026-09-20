import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return uuid4().hex


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "workspace.sqlite3"
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, source_path TEXT NOT NULL, filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    original_path TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS documents_source ON documents(source_path, active);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    text TEXT NOT NULL, locator TEXT NOT NULL, embedding TEXT NOT NULL,
                    embedding_model TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, text);
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY, vector TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS queries (
                    id TEXT PRIMARY KEY, result TEXT NOT NULL, created_at TEXT NOT NULL,
                    evaluation INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, query_id TEXT NOT NULL REFERENCES queries(id),
                    kind TEXT NOT NULL, comment TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, query_id TEXT NOT NULL REFERENCES queries(id),
                    answer TEXT NOT NULL, comment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                    resolution_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def event(self, kind: str, payload: dict):
        with self.connect() as conn:
            conn.execute("INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)", (kind, encode(payload), now()))

    def get_query(self, query_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT result FROM queries WHERE id=?", (query_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_query(self, result: dict, evaluation=False):
        with self.connect() as conn:
            conn.execute("INSERT INTO queries VALUES(?,?,?,?)", (result["query_id"], encode(result), result["created_at"], int(evaluation)))
            if result["status"] != "answered" and not evaluation:
                conn.execute("INSERT INTO review(id,kind,query_id,answer,comment,created_at) VALUES(?,?,?,?,?,?)",
                             (identifier(), "gap", result["query_id"], encode(result), result["message"], now()))

    def feedback(self, value: dict):
        result = self.get_query(value["query_id"])
        if not result:
            raise KeyError("Query not found.")
        record_id, timestamp = identifier(), now()
        with self.connect() as conn:
            conn.execute("INSERT INTO feedback VALUES(?,?,?,?,?)", (record_id, value["query_id"], value["kind"], value["comment"], timestamp))
            if value["kind"] != "accepted":
                conn.execute("INSERT INTO review(id,kind,query_id,answer,comment,created_at) VALUES(?,?,?,?,?,?)",
                             (record_id, value["kind"], value["query_id"], encode(result), value["comment"], timestamp))
        return {"id": record_id}

    def reviews(self, kind=None):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM review " + ("WHERE kind=? " if kind else "") + "ORDER BY created_at DESC", (kind,) if kind else ()).fetchall()
        items = []
        for row in rows:
            value = dict(row)
            value["answer"] = json.loads(value["answer"])
            value["question"] = value["answer"]["question"]
            items.append(value)
        return {"items": items}

    def counts(self):
        with self.connect() as conn:
            docs = conn.execute("SELECT count(*) FROM documents WHERE active=1").fetchone()[0]
            chunks = conn.execute("SELECT count(*) FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.active=1").fetchone()[0]
        return docs, chunks

    def metrics(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with self.connect() as conn:
            all_queries = conn.execute("SELECT result FROM queries WHERE evaluation=0 AND created_at>=?", (cutoff,)).fetchall()
            answered = {q["query_id"] for row in all_queries if (q := json.loads(row[0]))["status"] in ("answered", "partial") and q["claims"]}
            negative = {r[0] for r in conn.execute("SELECT DISTINCT query_id FROM feedback WHERE kind IN ('rejected','corrected') AND created_at>=?", (cutoff,))}
            events = conn.execute("SELECT kind,payload FROM events WHERE created_at>=?", (cutoff,)).fetchall()
        calls = [json.loads(e[1]) for e in events if e[0] == "provider"]
        failures = sum(1 for c in calls if not c.get("success"))
        return {"window_days": 30, "query_count": len(all_queries), "answered_query_count": len(answered),
                "rejected_or_corrected_query_count": len(answered & negative),
                "rejection_correction_rate": len(answered & negative) / len(answered) if answered else None,
                "provider_attempts": len(calls), "provider_failures": failures,
                "provider_tokens": sum(c.get("total_tokens", 0) for c in calls),
                "mean_provider_latency_ms": round(sum(c.get("latency_ms", 0) for c in calls) / len(calls), 1) if calls else None,
                "feedback_bias_note": "Voluntary feedback may undercount problems and is not a representative accuracy estimate."}
