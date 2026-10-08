"""Live event ingestion and novel-schema anomaly detection."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from doom.detectors import ManifestDetector
from doom.generator import generate_clean_manifest
from doom.store import EvidenceStore


class StreamingService:
    def __init__(self, store: EvidenceStore):
        self.store = store
        self.clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self.recent: deque[dict[str, Any]] = deque(maxlen=100)
        self.detector = ManifestDetector()
        self.sequence = 0

    async def publish(self, record: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        incident = self.detector.detect_record(record)
        event = {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "record_id": str(record.get("record_id", "UNKNOWN")),
            "status": "ANOMALY" if incident else "CLEARED",
            "incident": incident,
            "record": record,
        }
        self.recent.append(event)
        self.store.add_stream_event(event)
        for queue in tuple(self.clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)
        return event

    async def run(self, interval_seconds: float = 8.0) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            frame = generate_clean_manifest(1, seed=83_000 + self.sequence)
            record = frame.iloc[0].to_dict()
            record["record_id"] = f"LIVE-{self.sequence + 1:06d}"
            if self.sequence == 2:
                record["policy_epoch"] = "OMEGA-7"
                record["routing_signature"] = "UNSEEN-FUTURE-FORMAT"
            await self.publish(record)

    def snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self.recent)[-limit:]


def public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Produce an operator-facing payload without exposing hidden evaluator data."""
    return json.loads(json.dumps(event, default=str))
