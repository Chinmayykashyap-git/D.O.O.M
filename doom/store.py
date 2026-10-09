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

    def add_stream_event(self, event: dict[str, Any], limit: int = 1000) -> None:
        if limit < 1:
            raise ValueError("stream event retention limit must be positive")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO stream_events(created_at,payload) VALUES(?,?)",
                (event["timestamp"], json.dumps(_json_safe(event))),
            )
            connection.execute(
                """
                DELETE FROM stream_events
                WHERE event_id NOT IN (
                    SELECT event_id FROM stream_events ORDER BY event_id DESC LIMIT ?
                )
                """,
                (limit,),
            )

    def stream_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM stream_events ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in reversed(rows)]

    def upsert_record(self, record: dict[str, Any]) -> None:
        record_id = str(record.get("record_id", ""))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO records(record_id, payload) VALUES(?, ?)
                ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload
                """,
                (record_id, json.dumps(_json_safe(record))),
            )

    def upsert_incident(self, incident: dict[str, Any]) -> None:
        record_id = str(incident.get("record_id", ""))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents(record_id, payload) VALUES(?, ?)
                ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload
                """,
                (record_id, json.dumps(_json_safe(incident))),
            )

    def delete_incident(self, record_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM incidents WHERE record_id=?",
                (record_id,),
            )

    def upsert_reconstruction(self, decision: dict[str, Any]) -> None:
        record_id = str(decision.get("record_id", ""))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO reconstruction(record_id, payload) VALUES(?, ?)
                ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload
                """,
                (record_id, json.dumps(_json_safe(decision))),
            )

    def upsert_reconstructed_record(self, record: dict[str, Any]) -> None:
        record_id = str(record.get("record_id", ""))
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO reconstructed_records(record_id, payload) VALUES(?, ?)
                ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload
                """,
                (record_id, json.dumps(_json_safe(record))),
            )

    def get_sar(self) -> dict[str, Any]:
        """Generate a real-time Suspicious Activity Report (SAR) synchronized with the current store."""
        from datetime import datetime, timezone
        incidents = self.incidents(limit=10000)
        records = self.records(limit=10000)
        reconstruction = self.reconstruction()

        critical = [inc for inc in incidents if inc.get("risk_score", 0) >= 90]
        high = [inc for inc in incidents if 75 <= inc.get("risk_score", 0) < 90]
        medium = [inc for inc in incidents if 55 <= inc.get("risk_score", 0) < 75]
        low = [inc for inc in incidents if inc.get("risk_score", 0) < 55]

        type_breakdown: dict[str, int] = {}
        for inc in incidents:
            t = str(inc.get("tampering_type", "UNKNOWN"))
            type_breakdown[t] = type_breakdown.get(t, 0) + 1

        now_utc = datetime.now(timezone.utc)
        return {
            "report_id": f"SAR-{now_utc.strftime('%Y%m%d-%H%M%S')}",
            "generated_at": now_utc.isoformat(),
            "executive_summary": {
                "total_records_monitored": len(records),
                "total_incidents_active": len(incidents),
                "critical_threats": len(critical),
                "high_threats": len(high),
                "medium_threats": len(medium),
                "low_threats": len(low),
                "fleet_integrity_percentage": round(
                    100 * (1 - len(incidents) / max(len(records), 1)), 2
                ),
                "reconstruction_coverage": len(reconstruction),
            },
            "type_breakdown": dict(sorted(type_breakdown.items())),
            "top_critical_incidents": critical[:20],
            "recommended_actions": [
                "Quarantine records with active cryptographic hash chain breaks."
                if any(inc.get("tampering_type") == "UNKNOWN ANOMALY" for inc in incidents)
                else "Maintain standard surveillance.",
                "Verify customs discrepancy items against external witness declaration.",
                "Review automated provisional repairs before releasing manifest to port authority.",
            ],
        }


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
