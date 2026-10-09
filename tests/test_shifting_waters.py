"""Tests for hackathon 'Shifting Waters Twist': real-time record modification and stream forensics."""

import asyncio
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from doom.api import create_app
from doom.generator import generate_dataset
from doom.store import EvidenceStore
from doom.streaming import StreamingService


def test_incremental_ingest_without_batch_rerun(tmp_path: Path):
    """Test Requirement 1: Continuously process incoming records without requiring a complete batch rerun."""
    db_path = tmp_path / "incremental.sqlite3"
    store = EvidenceStore(db_path)
    clean, _ = generate_dataset(25, seed=1001)

    # Seed initial 20 records into store
    for row in clean.iloc[:20].to_dict(orient="records"):
        store.upsert_record(row)

    app = create_app(db_path)
    client = TestClient(app)

    # Initial record count
    overview_before = client.get("/api/overview").json()
    assert overview_before["record_count"] == 20

    # Ingest a new, independently generated 21st record via /api/ingest
    new_record = clean.iloc[20].to_dict()
    new_record["record_id"] = "STREAM-NEW-001"
    response = client.post("/api/ingest", json={"record": new_record})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event"]["status"] == "CLEARED"

    # Confirmed instantly queryable via /api/records and /api/overview without any batch rerun
    overview_after = client.get("/api/overview").json()
    assert overview_after["record_count"] == 21
    fetched = client.get("/api/records?limit=50").json()
    assert any(item["record_id"] == "STREAM-NEW-001" for item in fetched)


def test_realtime_record_modification_reassessment(tmp_path: Path):
    """Test Requirement 2: Reassess a record when its contents change in real time."""
    db_path = tmp_path / "modify.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    clean, _ = generate_dataset(5, seed=2002)
    baseline = clean.iloc[0].to_dict()
    baseline["record_id"] = "ACTIVE-TARGET-01"

    res_ingest = client.post("/api/ingest", json={"record": baseline})
    assert res_ingest.status_code == 200
    assert res_ingest.json()["event"]["status"] == "CLEARED"

    # The attacker modifies the container_id in real-time
    original_container = baseline["container_id"]
    res_mod = client.post("/api/records/modify", json={
        "record_id": "ACTIVE-TARGET-01",
        "updates": {"container_id": f"SWAPPED-{original_container}"},
    })
    assert res_mod.status_code == 200
    data = res_mod.json()
    assert data["status"] == "success"
    assert data["incident"]["tampering_type"] == "UNKNOWN ANOMALY"
    assert data["incident"]["evidence"][0]["evidence_code"] == "STREAM_RECORD_ID_MUTATION"
    assert data["live_reconstruction"]["status"] == "REPAIRED"
    assert data["live_reconstruction"]["reconstructed_record"]["container_id"] == original_container

    # Incident Register and Overview reflect the new anomaly immediately
    incidents = client.get("/api/incidents").json()
    assert any(item["record_id"] == "ACTIVE-TARGET-01" for item in incidents)
    overview = client.get("/api/overview").json()
    assert overview["incident_count"] == 1


def test_measurable_subsecond_latency(tmp_path: Path):
    """Test Requirement 3: Run detection incrementally with measurable seconds-level (sub-second) latency."""
    db_path = tmp_path / "latency.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    clean, _ = generate_dataset(20, seed=3003)
    latencies_ms = []
    for i in range(15):
        rec = clean.iloc[i].to_dict()
        rec["record_id"] = f"LAT-{i:03d}"
        t0 = time.perf_counter()
        resp = client.post("/api/ingest", json={"record": rec})
        t1 = time.perf_counter()
        assert resp.status_code == 200
        http_latency_ms = (t1 - t0) * 1000.0
        reported_internal_latency = resp.json()["latency_ms"]
        assert reported_internal_latency > 0
        latencies_ms.append(http_latency_ms)

    max_latency = max(latencies_ms)
    avg_latency = sum(latencies_ms) / len(latencies_ms)
    assert max_latency < 250.0, f"Max latency was {max_latency:.2f} ms"
    assert avg_latency < 100.0, f"Avg latency was {avg_latency:.2f} ms"


def test_unseen_pattern_detection_defensible(tmp_path: Path):
    """Test Requirement 4: Defensible anomaly detection for unseen statistical distribution outliers."""
    db_path = tmp_path / "unseen.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    clean, _ = generate_dataset(5, seed=4004)
    rec = clean.iloc[0].to_dict()
    rec["record_id"] = "UNSEEN-001"
    # Inject an unseen statistical anomaly: declared_value $8,000,000 diverging wildly from unit_price * quantity
    rec["unit_price_usd"] = 50.0
    rec["quantity"] = 10
    rec["declared_value_usd"] = 8000000.0

    resp = client.post("/api/ingest", json={"record": rec})
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"]["status"] == "ANOMALY"
    incident = data["event"]["incident"]
    assert incident["tampering_type"] == "UNKNOWN ANOMALY"
    assert incident["evidence"][0]["evidence_code"] == "VALUE_QUANTITY_INCOHERENCE"
    # Defensible calibrated confidence: does not claim 100% confidence for unseen attack
    assert 0.70 <= incident["confidence"] <= 0.90
    assert "statistical_novelty" in incident["detectors"]


def test_benign_update_false_positive_control(tmp_path: Path):
    """Test Requirement 5: Control false positives on benign updates; suppress unwarranted alerts."""
    db_path = tmp_path / "benign.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    clean, _ = generate_dataset(5, seed=5005)
    initial = clean.iloc[0].to_dict()
    initial["record_id"] = "BENIGN-TRACK-01"
    client.post("/api/ingest", json={"record": initial})

    # Benign operational progression: event_ts advances within valid shipment window
    dep = pd.to_datetime(initial["departure_ts"])
    arr = pd.to_datetime(initial["arrival_ts"])
    mid = (dep + (arr - dep) / 2).isoformat()

    benign_update = {
        "record_id": "BENIGN-TRACK-01",
        "updates": {
            "event_ts": mid,
        },
    }
    resp = client.post("/api/records/modify", json=benign_update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"]["status"] == "CLEARED"
    assert data["incident"] is None

    # Alert was suppressed: incident count is 0
    overview = client.get("/api/overview").json()
    assert overview["incident_count"] == 0


def test_idempotent_duplicate_delivery(tmp_path: Path):
    """Test Requirement 7: Make processing idempotent so duplicate delivery does not create duplicate incidents."""
    db_path = tmp_path / "idempotent.sqlite3"
    store = EvidenceStore(db_path)
    service = StreamingService(store)

    clean, _ = generate_dataset(5, seed=6006)
    event_payload = clean.iloc[0].to_dict()
    event_payload["record_id"] = "IDEMP-001"

    # First delivery
    first_event = asyncio.run(service.publish(event_payload, event_id="UNIQUE-EV-100"))
    assert first_event["sequence"] == 1
    assert "idempotent_replay" not in first_event

    # Duplicate delivery of exact same event_id
    second_event = asyncio.run(service.publish(event_payload, event_id="UNIQUE-EV-100"))
    assert second_event["sequence"] == 1  # Sequence did NOT increment
    assert second_event["idempotent_replay"] is True

    # Total recorded stream events in database is only 1
    assert len(store.stream_events(10)) == 1


def test_malformed_event_quarantine_resilience(tmp_path: Path):
    """Test Requirement 8: Handle malformed events and failed processing without crashing or silently losing records."""
    db_path = tmp_path / "malformed.sqlite3"
    store = EvidenceStore(db_path)
    service = StreamingService(store)

    # Malformed event (missing record_id)
    malformed = {"shipment_id": "MISSING_ID_SHIPMENT", "declared_value_usd": 500}
    event = asyncio.run(service.publish(malformed))

    assert event["status"] == "ANOMALY"
    assert event["incident"]["evidence"][0]["evidence_code"] == "MALFORMED_PAYLOAD"
    assert event["live_reconstruction"]["status"] == "UNRECOVERABLE"

    # Confirmed persisted to store rather than silently lost
    stored_events = store.stream_events(10)
    assert len(stored_events) == 1
    assert stored_events[0]["incident"]["evidence"][0]["evidence_code"] == "MALFORMED_PAYLOAD"


def test_sar_and_reconstructed_manifest_synchronized(tmp_path: Path):
    """Test Requirement 6: Keep reconstructed manifest, incident state, and Suspicious Activity Report synchronized."""
    db_path = tmp_path / "sar.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    # Initial SAR with no incidents
    initial_sar = client.get("/api/reports/sar").json()
    assert initial_sar["executive_summary"]["total_incidents_active"] == 0

    clean, _ = generate_dataset(5, seed=7007)
    record = clean.iloc[0].to_dict()
    record["record_id"] = "SAR-REC-01"
    original_container = record["container_id"]
    client.post("/api/ingest", json={"record": record})

    # Attacker tampers with container identity in real time
    client.post("/api/records/modify", json={
        "record_id": "SAR-REC-01",
        "updates": {"container_id": f"SWAPPED-{original_container}"},
    })

    # Updated SAR
    updated_sar = client.get("/api/reports/sar").json()
    assert updated_sar["executive_summary"]["total_incidents_active"] == 1
    assert updated_sar["executive_summary"]["critical_threats"] == 1
    assert "UNKNOWN ANOMALY" in updated_sar["type_breakdown"]
    assert updated_sar["top_critical_incidents"][0]["record_id"] == "SAR-REC-01"

    # Reconstructed manifest is synchronized
    recon_manifest = client.get("/api/reconstruction/manifest").json()
    assert len(recon_manifest) >= 1
    target_row = next(r for r in recon_manifest if r["record_id"] == "SAR-REC-01")
    # Provisional repair restored to baseline value
    assert target_row["container_id"] == original_container


def test_precision_and_false_positive_rate_on_labeled_stream(tmp_path: Path):
    """Test Requirement 10: Measure precision and false-positive rate on a ground-truth labeled test stream."""
    db_path = tmp_path / "metrics.sqlite3"
    app = create_app(db_path)
    client = TestClient(app)

    clean_manifest, _ = generate_dataset(30, seed=8008)

    # 10 Ground-Truth Clean records
    for i in range(10):
        row = clean_manifest.iloc[i].to_dict()
        row["record_id"] = f"GROUND-CLEAN-{i:02d}"
        resp = client.post("/api/ingest", json={"record": row})
        assert resp.json()["event"]["status"] == "CLEARED"

    # 10 Ground-Truth Benign Updates (expected status: CLEARED, label: negative)
    benign_results = []
    for i in range(10):
        dep = pd.to_datetime(clean_manifest.iloc[i]["departure_ts"])
        arr = pd.to_datetime(clean_manifest.iloc[i]["arrival_ts"])
        mid = (dep + (arr - dep) / 2).isoformat()
        resp = client.post("/api/records/modify", json={
            "record_id": f"GROUND-CLEAN-{i:02d}",
            "updates": {"event_ts": mid},
        })
        benign_results.append(resp.json()["event"]["status"] == "ANOMALY")

    # 10 Ground-Truth Malicious Mutations (expected status: ANOMALY, label: positive)
    malicious_results = []
    for i in range(10):
        orig_container = clean_manifest.iloc[i]["container_id"]
        resp = client.post("/api/records/modify", json={
            "record_id": f"GROUND-CLEAN-{i:02d}",
            "updates": {"container_id": f"TAMPERED-{orig_container}"},
        })
        malicious_results.append(resp.json()["event"]["status"] == "ANOMALY")

    tp = sum(malicious_results)  # correctly flagged malicious
    fn = len(malicious_results) - tp
    fp = sum(benign_results)     # falsely flagged benign updates
    tn = len(benign_results) - fp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    assert tp == 10, f"Expected 10 true positives, got {tp}"
    assert fp == 0, f"Expected 0 false positives, got {fp}"
    assert precision == 1.0, f"Precision was {precision}"
    assert recall == 1.0, f"Recall was {recall}"
    assert false_positive_rate == 0.0, f"FPR was {false_positive_rate}"

