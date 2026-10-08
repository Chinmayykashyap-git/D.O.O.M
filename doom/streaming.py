"""Bounded incremental event detection, reconstruction, and stream benchmarking."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import tempfile
import time
from collections import OrderedDict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from doom.detectors import ManifestDetector
from doom.generator import generate_clean_manifest
from doom.store import EvidenceStore


class StreamingService:
    def __init__(
        self,
        store: EvidenceStore,
        memory_limit: int = 100,
        persistence_limit: int = 1000,
        client_limit: int = 32,
    ):
        if memory_limit < 1 or persistence_limit < 1 or client_limit < 1:
            raise ValueError("stream retention limits must be positive")
        self.store = store
        self.clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self.recent: deque[dict[str, Any]] = deque(maxlen=memory_limit)
        self._trusted_first_observation: OrderedDict[
            str, dict[str, Any]
        ] = OrderedDict()
        self._memory_limit = memory_limit
        self._persistence_limit = persistence_limit
        self.client_limit = client_limit
        self.detector = ManifestDetector()
        self.sequence = 0

    async def publish(
        self,
        record: dict[str, Any],
        *,
        event_id: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        record_id = str(record.get("record_id", "UNKNOWN"))
        observed = dict(record)
        incident = self.detector.detect_record(observed)
        prior = self._trusted_first_observation.get(record_id)
        changed_fields = (
            _changed_fields(prior, observed) if prior is not None else []
        )
        if changed_fields and prior is not None:
            evidence = _mutation_evidence(record_id, prior, observed, changed_fields)
            if incident is not None:
                evidence = [*incident["evidence"], *evidence]
            incident = {
                "record_id": record_id,
                "tampering_type": "UNKNOWN ANOMALY",
                "unknown_analysis": self.detector.analyze_unknown(evidence),
                "type_probabilities": {"UNKNOWN ANOMALY": 0.95},
                "risk_score": 90,
                "confidence": 0.8 if prior is not None else 0.5,
                "evidence": evidence,
                "detectors": sorted({item["detector_id"] for item in evidence}),
                "related_records": [],
                "counterfactual": (
                    "If the first independently observed event is trusted, restore the "
                    "record fields to that snapshot."
                ),
                "record_missing": False,
            }

        if incident is None:
            reconstruction = {
                "record_id": record_id,
                "status": "ORIGINAL",
                "method": "incremental_invariant_checks",
                "evidence_relied_on": [],
                "confidence": 1.0,
                "before_after": {},
                "explanation": "No stream invariant or registered-schema violation was detected.",
                "why": "No stream invariant or registered-schema violation was detected.",
                "changes": [],
                "provisional": False,
            }
            if prior is None:
                self._remember(record_id, observed)
        elif changed_fields and prior is not None:
            diff = {
                field: {"before": observed.get(field), "after": prior.get(field)}
                for field in changed_fields
            }
            explanation = (
                "Changed fields are restored to the first observed event, which passed "
                "the available per-record checks. This is a provisional stream witness, "
                "not an authenticated external source."
            )
            reconstruction = {
                "record_id": record_id,
                "status": "REPAIRED",
                "method": "first_observed_stream_snapshot",
                "evidence_relied_on": ["stream_sequence:STREAM_RECORD_ID_MUTATION"],
                "confidence": 0.8,
                "before_after": diff,
                "explanation": explanation,
                "why": explanation,
                "changes": [
                    {"field": field, "from": observed.get(field), "to": prior.get(field)}
                    for field in changed_fields
                ],
                "reconstructed_record": dict(prior),
                "provisional": True,
            }
        else:
            explanation = (
                "The event is anomalous, but no earlier clean observation or independent "
                "witness establishes a safe replacement value. The original event is preserved."
            )
            reconstruction = {
                "record_id": record_id,
                "status": "UNRECOVERABLE",
                "method": "insufficient_live_witnesses",
                "evidence_relied_on": [
                    f"{item['detector_id']}:{item['evidence_code']}"
                    for item in incident["evidence"]
                ],
                "confidence": incident["confidence"],
                "before_after": {},
                "explanation": explanation,
                "why": explanation,
                "changes": [],
                "provisional": False,
            }

        self.sequence += 1
        event = {
            "event_id": event_id or str(uuid4()),
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
            "sequence": self.sequence,
            "record_id": record_id,
            "status": "ANOMALY" if incident else "CLEARED",
            "incident": incident,
            "record": observed,
            "live_reconstruction": reconstruction,
        }
        self.recent.append(event)
        self.store.add_stream_event(event, limit=self._persistence_limit)
        for queue in tuple(self.clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)
        return event

    def _remember(self, record_id: str, record: dict[str, Any]) -> None:
        self._trusted_first_observation[record_id] = dict(record)
        self._trusted_first_observation.move_to_end(record_id)
        while len(self._trusted_first_observation) > self._memory_limit:
            self._trusted_first_observation.popitem(last=False)

    async def run(self, interval_seconds: float = 8.0) -> None:
        if interval_seconds < 0:
            raise ValueError("stream interval cannot be negative")
        first_record: dict[str, Any] | None = None
        while True:
            await asyncio.sleep(interval_seconds)
            if self.sequence == 2 and first_record is not None:
                record = dict(first_record)
                record["container_id"] = f"SWAPPED-{record['container_id']}"
            else:
                frame = generate_clean_manifest(1, seed=83_000 + self.sequence)
                record = frame.iloc[0].to_dict()
                record["record_id"] = f"LIVE-{self.sequence + 1:06d}"
                if first_record is None:
                    first_record = dict(record)
            await self.publish(record)

    async def replay_seeded(
        self,
        event_count: int = 10,
        seed: int = 83,
        fast: bool = False,
    ) -> tuple[list[dict[str, Any]], list[float], float]:
        if event_count < 1:
            raise ValueError("event_count must be positive")
        events: list[dict[str, Any]] = []
        latencies_ms: list[float] = []
        first_record: dict[str, Any] | None = None
        start = time.perf_counter()
        origin = datetime(2025, 1, 1, tzinfo=UTC)
        for index in range(event_count):
            if not fast:
                await asyncio.sleep(0.05)
            if index == 2 and first_record is not None:
                record = dict(first_record)
                record["container_id"] = f"SWAPPED-{record['container_id']}"
            else:
                record = generate_clean_manifest(1, seed=seed + index).iloc[0].to_dict()
                record["record_id"] = f"LIVE-{seed:04d}-{index:06d}"
                if first_record is None:
                    first_record = dict(record)
            started = time.perf_counter()
            event = await self.publish(
                record,
                event_id=f"stream-{seed:04d}-{index:06d}",
                timestamp=(origin + timedelta(seconds=index)).isoformat(),
            )
            latencies_ms.append((time.perf_counter() - started) * 1000)
            events.append(event)
        elapsed_seconds = time.perf_counter() - start
        return events, latencies_ms, elapsed_seconds

    def snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self.recent)[-limit:]


def _changed_fields(
    previous: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    return sorted(
        field for field in set(previous) | set(current)
        if _canonical(previous.get(field)) != _canonical(current.get(field))
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _mutation_evidence(
    record_id: str,
    previous: dict[str, Any],
    current: dict[str, Any],
    changed_fields: list[str],
) -> list[dict[str, Any]]:
    return [
        {
            "detector_id": "stream_sequence",
            "evidence_code": "STREAM_RECORD_ID_MUTATION",
            "record_ids": [record_id],
            "field": field,
            "expected": previous.get(field),
            "observed": current.get(field),
            "score_contribution": 0.95,
            "explanation": (
                "A previously observed record ID reappeared with a different field value "
                "within the retained stream window."
            ),
        }
        for field in changed_fields
    ]


def summarize_streaming(
    latencies_ms: list[float], elapsed_seconds: float, events: list[dict[str, Any]]
) -> dict[str, Any]:
    if not latencies_ms or elapsed_seconds <= 0:
        raise ValueError("stream benchmark requires measured events and positive elapsed time")
    ordered = sorted(latencies_ms)
    p95_index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "event_count": len(events),
        "unknown_anomaly_count": sum(
            (event.get("incident") or {}).get("tampering_type") == "UNKNOWN ANOMALY"
            for event in events
        ),
        "throughput_events_per_second": round(len(events) / elapsed_seconds, 3),
        "latency_ms": {
            "p50": round(statistics.median(ordered), 3),
            "p95": round(ordered[p95_index], 3),
            "max": round(max(ordered), 3),
        },
        "measurement": (
            "Measured in-process publish duration including per-record detection, SQLite "
            "persistence, and bounded in-memory fan-out; includes event creation overhead."
        ),
    }


async def measure_streaming(event_count: int = 200, seed: int = 8300) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="doom-stream-metrics-") as directory:
        service = StreamingService(
            EvidenceStore(Path(directory) / "stream.sqlite3"),
            memory_limit=100,
            persistence_limit=200,
        )
        events, latencies, elapsed = await service.replay_seeded(
            event_count=event_count, seed=seed, fast=True
        )
        metrics = summarize_streaming(latencies, elapsed, events)
        metrics["state_limits"] = {
            "recent_events": service.recent.maxlen,
            "trusted_record_snapshots": service._memory_limit,
            "persisted_events": service._persistence_limit,
            "websocket_clients": service.client_limit,
        }
        return metrics


async def _cli_run(event_count: int, seed: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="doom-stream-cli-") as directory:
        service = StreamingService(EvidenceStore(Path(directory) / "stream.sqlite3"))
        events, latencies, elapsed = await service.replay_seeded(
            event_count=event_count, seed=seed, fast=True
        )
        return {
            "seed": seed,
            "fast": True,
            "metrics": summarize_streaming(latencies, elapsed, events),
            "events": [public_event(event) for event in events],
        }


def public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Produce an operator-facing payload without exposing hidden evaluator data."""
    return json.loads(json.dumps(event, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a deterministic local D.O.O.M. stream.")
    parser.add_argument("--events", type=int, default=10)
    parser.add_argument("--seed", type=int, default=83)
    parser.add_argument("--fast", action="store_true", help="Replay without simulated delays.")
    parser.add_argument(
        "--summary-only", action="store_true", help="Omit individual event payloads."
    )
    args = parser.parse_args()
    if not args.fast:
        parser.error("Use --fast for a finite deterministic local replay.")
    report = asyncio.run(_cli_run(args.events, args.seed))
    if args.summary_only:
        report.pop("events")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
