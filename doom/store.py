"""Small local SQLite evidence store; hidden evaluator data is never persisted here."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd


class EvidenceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incidents (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconstructed_records (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconstruction (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stream_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def replace_batch(
        self,
        records: pd.DataFrame,
        reconstructed_records: pd.DataFrame,
        incidents: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        metrics: dict[str, Any],
    ) -> None:
        incident_json = {item["record_id"]: item for item in incidents}
        decision_json = {item["record_id"]: item for item in decisions}
        with self.connect() as connection:
            connection.execute("DELETE FROM records")
            connection.execute("DELETE FROM reconstructed_records")
            connection.execute("DELETE FROM incidents")
            connection.execute("DELETE FROM reconstruction")
            connection.execute("DELETE FROM stream_events")
            connection.execute("DELETE FROM metadata")
            connection.executemany(
                "INSERT INTO records(record_id,payload) VALUES(?,?)",
                [
                    (str(row["record_id"]), json.dumps(_json_safe(row)))
                    for row in records.to_dict(orient="records")
                ],
            )
            connection.executemany(
                "INSERT INTO reconstructed_records(record_id,payload) VALUES(?,?)",
                [
                    (str(row["record_id"]), json.dumps(_json_safe(row)))
                    for row in reconstructed_records.to_dict(orient="records")
                ],
            )
            connection.executemany(
                "INSERT INTO incidents(record_id,payload) VALUES(?,?)",
                [
                    (key, json.dumps(_json_safe(value)))
                    for key, value in incident_json.items()
                ],
            )
            connection.executemany(
                "INSERT INTO reconstruction(record_id,payload) VALUES(?,?)",
                [
                    (key, json.dumps(_json_safe(value)))
                    for key, value in decision_json.items()
                ],
            )
            connection.execute(
                "INSERT INTO metadata(key,value) VALUES('metrics',?)",
                (json.dumps(_json_safe(metrics)),),
            )

    def records(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM records ORDER BY record_id LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def record(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def reconstructed_records(self, limit: int = 5000) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM reconstructed_records ORDER BY record_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def incidents(self, limit: int = 500) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM incidents ORDER BY record_id LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def incident(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM incidents WHERE record_id=?", (record_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def reconstruction(self, record_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if record_id is not None:
                rows = connection.execute(
                    "SELECT payload FROM reconstruction WHERE record_id=?", (record_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload FROM reconstruction ORDER BY record_id"
                ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def metrics(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='metrics'"
            ).fetchone()
        return json.loads(row["value"]) if row else {}

    def add_stream_event(self, event: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO stream_events(created_at,payload) VALUES(?,?)",
                (event["timestamp"], json.dumps(_json_safe(event))),
            )

    def stream_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM stream_events ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in reversed(rows)]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    if pd.isna(value):
        return None
    return value
