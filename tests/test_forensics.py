import asyncio

import pandas as pd
from fastapi.testclient import TestClient

from doom.api import create_app
from doom.detectors import ManifestDetector
from doom.generator import generate_batch, generate_clean_manifest
from doom.metrics import evaluate_detection
from doom.reconstruction import reconstruct_manifest
from doom.store import EvidenceStore
from doom.streaming import StreamingService


def test_generator_is_deterministic_and_keeps_control_ledger_separate():
    first = generate_batch(count=120, seed=41)
    second = generate_batch(count=120, seed=41)

    pd.testing.assert_frame_equal(first.clean, second.clean)
    pd.testing.assert_frame_equal(first.corrupted, second.corrupted)
    assert first.expected_record_ids == second.expected_record_ids
    assert len(first.hidden_injection_log) == 7
    assert "tampering_type" not in first.clean.columns
    assert "tampering_type" not in first.corrupted.columns


def test_detector_finds_all_batch_attack_classes_from_manifest_and_ledger_only():
    batch = generate_batch(count=300, seed=19)
    incidents = ManifestDetector().detect(
        batch.corrupted, expected_record_ids=batch.expected_record_ids
    )
    predicted = {item["record_id"]: item for item in incidents}
    actual = {item["record_id"]: item["tampering_type"] for item in batch.hidden_injection_log}

    assert set(actual) <= set(predicted)
    assert {predicted[key]["tampering_type"] for key in actual} == set(actual.values())
    assert all(item["risk_score"] > 0 for item in incidents)
    assert all(item["confidence"] > 0 for item in incidents)
    assert all(item["evidence"] and item["detectors"] for item in incidents)
    assert predicted[next(key for key, value in actual.items() if value == "DELETED")]["record_missing"]


def test_reconstruction_is_explicit_and_retains_canonical_duplicate():
    batch = generate_batch(count=160, seed=75)
    incidents = ManifestDetector().detect(
        batch.corrupted, expected_record_ids=batch.expected_record_ids
    )
    reconstructed, decisions = reconstruct_manifest(batch.corrupted, incidents)
    statuses = {item["status"] for item in decisions}

    assert statuses == {"ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"}
    assert reconstructed["record_id"].is_unique
    duplicate = next(item for item in incidents if item["tampering_type"] == "DUPLICATE")
    assert duplicate["record_id"] not in set(reconstructed["record_id"])
    canonical = duplicate["record_id"].removesuffix("-COPY")
    assert canonical in set(reconstructed["record_id"])
    assert all("explanation" in item and "changes" in item for item in decisions)


def test_evaluation_reports_actual_record_level_counts():
    batch = generate_batch(count=240, seed=202)
    incidents = ManifestDetector().detect(
        batch.corrupted, expected_record_ids=batch.expected_record_ids
    )
    metrics = evaluate_detection(batch.hidden_injection_log, incidents)

    assert metrics["injected_attacks"] == len(batch.hidden_injection_log)
    assert metrics["true_positive"] <= len(batch.hidden_injection_log)
    assert metrics["false_positive"] == len(incidents) - metrics["true_positive"]
    assert 0 <= metrics["precision"] <= 1
    assert 0 <= metrics["recall"] <= 1
    assert "not a production benchmark" in metrics["evaluation_scope"]


def test_unknown_schema_attack_is_detected_in_streaming_only(tmp_path):
    store = EvidenceStore(tmp_path / "stream.sqlite3")
    service = StreamingService(store)
    row = generate_clean_manifest(1, seed=8).iloc[0].to_dict()
    row["record_id"] = "LIVE-OMEGA"
    row["policy_epoch"] = "OMEGA-7"

    event = asyncio.run(service.publish(row))

    assert event["status"] == "ANOMALY"
    assert event["incident"]["tampering_type"] == "UNKNOWN_ANOMALY"
    assert "UNRECOGNIZED_SCHEMA_FIELD" in {
        evidence["code"] for evidence in event["incident"]["evidence"]
    }
    assert store.stream_events()[0]["record_id"] == "LIVE-OMEGA"


def test_local_api_returns_incident_evidence_without_ground_truth(tmp_path):
    batch = generate_batch(count=120, seed=113)
    incidents = ManifestDetector().detect(batch.corrupted, batch.expected_record_ids)
    reconstructed, decisions = reconstruct_manifest(batch.corrupted, incidents)
    metrics = evaluate_detection(batch.hidden_injection_log, incidents)
    database = tmp_path / "api.sqlite3"
    EvidenceStore(database).replace_batch(
        batch.corrupted, reconstructed, incidents, decisions, metrics
    )

    with TestClient(create_app(database, start_stream=False)) as client:
        assert client.get("/api/health").json()["status"] == "operational"
        listed = client.get("/api/incidents").json()
        assert listed
        incident_id = listed[0]["record_id"]
        detail = client.get(f"/api/incidents/{incident_id}").json()
        assert detail["incident"]["evidence"]
        assert detail["reconstruction"]["status"]
        reconstructed = client.get("/api/reconstruction/manifest").json()
        assert reconstructed
        assert len(reconstructed) < len(batch.corrupted)
        assert client.get("/api/hidden-injection-log").status_code == 404
