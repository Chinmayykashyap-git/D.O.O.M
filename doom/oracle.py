"""Evaluator-only storage for synthetic injection truth, isolated from evidence DB."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class OracleStore:
    """Keep attack labels in a distinct local SQLite file, never the evidence DB."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS injection_truth (
                    record_id TEXT PRIMARY KEY,
                    source_record_id TEXT NOT NULL,
                    tampering_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            connection.commit()

    def replace(self, entries: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM injection_truth")
            connection.executemany(
                "INSERT INTO injection_truth VALUES(?,?,?,?)",
                [
                    (
                        str(item["record_id"]),
                        str(item["source_record_id"]),
                        str(item["tampering_type"]),
                        json.dumps(item, sort_keys=True, default=str),
                    )
                    for item in entries
                ],
            )
            connection.commit()

    def entries(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT payload FROM injection_truth ORDER BY record_id"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
