import ast
import asyncio
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from doom.api import create_app
from doom.calibration import apply_calibration, load_calibrator
from doom.corruption import ATTACK_TYPES, inject_attacks
from doom.detectors import ManifestDetector
from doom.generator import (
    generate_dataset,
    make_control_ledger,
    output_hashes,
)
from doom.holdout_eval import evaluate_holdout
from doom.metrics import evaluate_detection
from doom.oracle import OracleStore
from doom.reconstruction import reconstruct_manifest
from doom.store import EvidenceStore
from doom.streaming import StreamingService
from holdout_attacks import HOLDOUT_ATTACKS, inject_holdout_attacks


def generated(count: int = 300, seed: int = 1907):
    clean, witnesses = generate_dataset(count, seed)
    observed, oracle = inject_attacks(clean, seed + 1)
    ledger = make_control_ledger(clean)
    return clean, witnesses, observed, oracle, ledger


def detect(clean, witnesses, observed, ledger):
    return ManifestDetector().detect(
        observed,
        expected_record_ids=clean["record_id"].astype(str),
        expected_ledger=ledger,
        witnesses=witnesses,
    )


def test_generator_and_attacks_are_deterministic_with_realistic_schema():
    clean_a, witness_a = generate_dataset(180, 41)
    corrupt_a, oracle_a = inject_attacks(clean_a, 42)
    clean_b, witness_b = generate_dataset(180, 41)
    corrupt_b, oracle_b = inject_attacks(clean_b, 42)

    pd.testing.assert_frame_equal(clean_a, clean_b)
    pd.testing.assert_frame_equal(corrupt_a, corrupt_b)
    assert witness_a.as_dict() == witness_b.as_dict()
    assert oracle_a == oracle_b
    assert output_hashes(clean_a) == output_hashes(clean_b)
    assert len(oracle_a) == 12
    assert {entry["tampering_type"] for entry in oracle_a} == set(ATTACK_TYPES)
    assert clean_a["record_id"].str.fullmatch(r"MF-\d{7}").all()
    assert clean_a["shipment_id"].str.fullmatch(r"SHP-\d{7}").all()
    assert "tampering_type" not in clean_a.columns
    assert {"movement_history", "customs_entries", "port_logs"} <= set(witness_a.as_dict())
    first = generate_dataset(180, 41)[0]
    hashes = []
    for _ in range(3):
        manifest, witness = generate_dataset(100, 41)
        observed, truth = inject_attacks(manifest, 42)
        payload = {
            "manifest": manifest.to_csv(index=False, lineterminator="\n"),
            "observed": observed.to_csv(index=False, lineterminator="\n"),
            "witnesses": witness.as_dict(),
            "oracle": truth,
        }
        hashes.append(hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest())
    assert len(set(hashes)) == 1
    assert first.equals(clean_a)


def _surface_features(frame):
    feature = pd.DataFrame(index=frame.index)
    for field in (
        "record_id", "shipment_id", "container_id", "owner", "container_owner",
        "vessel_id", "planned_route", "current_location", "status",
    ):
        values = frame[field].astype(str)
        feature[f"{field}_length"] = values.str.len()
        feature[f"{field}_prefix"] = values.str[:3].map(
            lambda value: sum(map(ord, value))
        )
    for field in ("departure_ts", "arrival_ts", "event_ts"):
        timestamp = pd.to_datetime(frame[field], utc=True, errors="coerce")
        feature[f"{field}_hour"] = timestamp.dt.hour.fillna(-1)
        feature[f"{field}_minute"] = timestamp.dt.minute.fillna(-1)
        feature[f"{field}_second"] = timestamp.dt.second.fillna(-1)
        feature[f"{field}_length"] = frame[field].astype(str).str.len()
    for field in (
        "quantity", "unit_price_usd", "declared_value_usd", "weight_kg",
        "route_distance_nm",
    ):
        feature[f"{field}_length"] = frame[field].astype(str).str.len()
    feature["file_row_order"] = frame["_surface_row_order"]
    return feature.fillna(-1)


def test_surface_feature_classifier_is_near_chance_across_five_seeds():
    accuracies = []
    aucs = []
    for seed in (1907, 19, 41, 75, 113):
        clean, _ = generate_dataset(1200, seed)
        corrupted, oracle = inject_attacks(clean, seed + 1)
        attacked_ids = {
            entry["record_id"] for entry in oracle
            if entry["tampering_type"] != "DELETED"
        }
        attacked = corrupted.loc[
            corrupted["record_id"].astype(str).isin(attacked_ids)
        ].copy()
        attacked["_surface_row_order"] = attacked.index / max(len(corrupted) - 1, 1)
        controls, _ = generate_dataset(len(attacked), seed + 9000)
        controls["_surface_row_order"] = controls.index / max(len(controls) - 1, 1)
        sample = pd.concat([attacked, controls], ignore_index=True)
        labels = np.array([1] * len(attacked) + [0] * len(controls))
        permutation = np.random.RandomState(seed).permutation(len(labels))
        sample = sample.iloc[permutation].reset_index(drop=True)
        labels = labels[permutation]
        features = _surface_features(sample)
        train, test = train_test_split(
            np.arange(len(labels)), test_size=0.3, random_state=seed, stratify=labels
        )
        classifier = RandomForestClassifier(
            n_estimators=120,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        )
        classifier.fit(features.iloc[train], labels[train])
        accuracies.append(accuracy_score(labels[test], classifier.predict(features.iloc[test])))
        aucs.append(roc_auc_score(
            labels[test], classifier.predict_proba(features.iloc[test])[:, 1]
        ))

    assert 0.35 <= float(np.mean(accuracies)) <= 0.65, accuracies
    assert float(np.mean(aucs)) <= 0.65, aucs


def test_ledger_hashes_and_witness_formulas_hold_for_clean_data():
    clean, witnesses = generate_dataset(120, 88)
    owner_by_id = {
        row["owner_id"]: row["owner_name"]
        for row in witnesses.owner_registry.to_dict(orient="records")
    }
    containers = {
        row["container_id"]: row
        for row in witnesses.container_registry.to_dict(orient="records")
    }
    previous = "DOOM-GENESIS-v1"
    for row in clean.sort_values("ledger_sequence").to_dict(orient="records"):
        assert row["previous_hash"] == previous
        assert row["owner"] == owner_by_id[row["owner_id"]]
        assert round(row["quantity"] * row["unit_price_usd"], 2) == row["declared_value_usd"]
        assert row["weight_kg"] <= containers[row["container_id"]]["maximum_weight_kg"]
        expected_sea_hours = row["route_distance_nm"] / {
            "ECONOMY": 15.0, "STANDARD": 18.0, "EXPRESS": 22.0,
        }[row["speed_class"]]
        actual_hours = (
            pd.Timestamp(row["arrival_ts"]) - pd.Timestamp(row["departure_ts"])
        ).total_seconds() / 3600
        assert actual_hours >= expected_sea_hours
        previous = row["ledger_hash"]


def test_detector_detects_and_classifies_known_synthetic_taxonomy():
    clean, witnesses, observed, oracle, ledger = generated(480, 19)
    incidents = detect(clean, witnesses, observed, ledger)
    predicted = {item["record_id"]: item for item in incidents}

    assert set(item["record_id"] for item in oracle) <= set(predicted)
    for item in oracle:
        assert predicted[item["record_id"]]["tampering_type"] == item["tampering_type"]
    assert all(item["evidence"] and item["detectors"] for item in incidents)
    assert all(item["counterfactual"] for item in incidents)
    assert all(
        {"detector_id", "record_ids", "field", "expected", "observed",
         "score_contribution", "explanation"} <= set(evidence)
        for item in incidents for evidence in item["evidence"]
    )
    assert all(item["type_probabilities"] for item in incidents)


def test_reconstruction_is_explained_and_duplicate_canonical_is_retained():
    clean, witnesses, observed, oracle, ledger = generated(300, 75)
    incidents = detect(clean, witnesses, observed, ledger)
    reconstructed, decisions = reconstruct_manifest(
        observed, incidents, witnesses, ledger
    )
    by_id = {item["record_id"]: item for item in decisions}

    assert {item["status"] for item in decisions} >= {
        "ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE",
    }
    assert reconstructed["record_id"].is_unique
    for item in decisions:
        assert item["method"] and item["why"] and item["before_after"] is not None
        if item["changes"]:
            assert item["status"] == "REPAIRED"
            assert item["evidence_relied_on"]
    duplicate = next(
        item for item in oracle if item["tampering_type"] == "DUPLICATE_EXACT"
    )
    assert by_id[duplicate["record_id"]]["status"] == "REMOVED"
    assert duplicate["source_record_id"] in set(reconstructed["record_id"])
    deleted = next(item for item in oracle if item["tampering_type"] == "DELETED")
    deletion_decision = by_id[deleted["record_id"]]
    assert deletion_decision["status"] == "UNRECOVERABLE"
    assert deletion_decision["recovered_fields"]["shipment_id"] == (
        deleted["original"]["shipment_id"]
    )
    assert deletion_decision["recovered_fields"]["declared_value_usd"] == (
        deleted["original"]["declared_value_usd"]
    )
    assert {"weight_kg", "status", "current_location", "event_ts"} <= set(
        deletion_decision["unrecoverable_fields"]
    )
    assert deletion_decision["field_provenance"]["shipment_id"].startswith(
        "movement_history:"
    )
    assert deletion_decision["before_after"]["ledger_sequence"]["before"] == "ABSENT"


def test_metrics_are_truth_scoped_and_reconstruction_is_field_scored():
    clean, witnesses, observed, oracle, ledger = generated(360, 202)
    incidents = detect(clean, witnesses, observed, ledger)
    reconstructed, decisions = reconstruct_manifest(
        observed, incidents, witnesses, ledger
    )
    metrics = evaluate_detection(
        oracle, incidents, decisions, reconstructed.to_dict(orient="records")
    )

    assert metrics["injected_attacks"] == len(oracle)
    assert set(metrics["per_attack"]) == set(ATTACK_TYPES)
    assert metrics["false_positive"] >= 0
    assert metrics["reconstruction"]["field_total"] > 0
    assert metrics["reconstruction"]["per_attack"]
    assert metrics["reconstruction"]["by_status"]
    assert 0 < metrics["reconstruction"]["field_coverage"] < 1
    assert "field_coverage" in metrics["reconstruction"]["per_attack"]["DELETED"]
    assert metrics["reconstruction"]["per_attack"]["FABRICATED"]["field_accuracy"] is None
    assert {"REPAIRED", "REMOVED", "UNRECOVERABLE"} <= set(
        metrics["reconstruction"]["by_status"]
    )
    assert set(metrics["reconstruction"]["by_status"]) == {
        "ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE",
    }
    assert metrics["reconstruction"]["by_status"]["ORIGINAL"]["status_accuracy"] is None
    assert "not a production benchmark" in metrics["evaluation_scope"]


def test_unknown_stream_schema_attack_is_not_a_batch_training_import(tmp_path):
    _, witnesses, observed, _, _ = generated(240, 113)
    clean, _ = generate_dataset(240, 113)
    clean_ids = set(clean["record_id"].astype(str))
    batch_incidents = ManifestDetector().detect(
        observed, expected_record_ids=clean_ids,
        expected_ledger=make_control_ledger(clean), witnesses=witnesses,
    )
    row = clean.iloc[0].to_dict()
    row["record_id"] = "MF-7770001"
    row["policy_epoch"] = "OMEGA-7"
    store = EvidenceStore(tmp_path / "stream.sqlite3")
    service = StreamingService(store)
    event = asyncio.run(service.publish(row))
    assert event["status"] == "ANOMALY"
    assert event["incident"]["tampering_type"] == "UNKNOWN ANOMALY"
    assert event["incident"]["evidence"][0]["evidence_code"] == "UNRECOGNIZED_SCHEMA_FIELD"
    assert event["incident"]["unknown_analysis"]["invariant_violations"]
    assert 0 <= event["incident"]["unknown_analysis"]["novelty_score"] <= 1
    assert event["incident"]["unknown_analysis"]["nearest_known_attack_type"] in ATTACK_TYPES
    assert not any(item["record_id"] == row["record_id"] for item in batch_incidents)


def test_holdout_families_are_isolated_and_explain_novelty():
    root = Path(__file__).resolve().parents[1]
    assert set(HOLDOUT_ATTACKS).isdisjoint(ATTACK_TYPES)
    clean, _ = generate_dataset(120, 9181)
    original = clean.copy(deep=True)
    first, first_truth = inject_holdout_attacks(clean, 9182)
    second, second_truth = inject_holdout_attacks(clean, 9182)
    pd.testing.assert_frame_equal(clean, original)
    pd.testing.assert_frame_equal(first, second)
    assert first_truth == second_truth

    for source in (root / "doom").glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        if any(name == "holdout_attacks" or name.startswith("holdout_attacks.") for name in imported):
            assert source.name == "holdout_eval.py"
    calibration_source = (root / "doom" / "calibration.py").read_text(encoding="utf-8")
    assert "holdout_attacks" not in calibration_source
    report = evaluate_holdout(record_count=120, seed=9183)
    assert report["attack_families"] == list(HOLDOUT_ATTACKS)
    assert report["true_positive"] + report["false_negative"] == len(HOLDOUT_ATTACKS)
    for result in report["per_attack"].values():
        assert result["classified_unknown"]
        analysis = result["unknown_analysis"]
        assert analysis["invariant_violations"]
        assert analysis["nearest_known_attack_type"] in ATTACK_TYPES
        assert 0 <= analysis["nearest_similarity"] <= 1
        assert 0 <= analysis["novelty_score"] <= 1
        assert analysis["nearest_match_meaningful"] == (
            analysis["nearest_similarity"] > 0
        )


def test_detector_import_graph_cannot_access_injection_or_holdout_truth():
    root = Path(__file__).resolve().parents[1]
    source = (root / "doom" / "detectors.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_modules = {"doom.corruption", "doom.oracle", "doom.metrics", "holdout_attacks"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports.isdisjoint(forbidden_modules)
    assert "hidden_injection_log" not in source


def test_calibration_artifact_uses_disjoint_seeds_and_returns_bounded_probabilities():
    root = Path(__file__).resolve().parents[1]
    artifact = load_calibrator(root / "reports" / "calibration.json")
    assert artifact is not None
    study = artifact["study"]
    assert set(study["training_seeds"]).isdisjoint(study["evaluation_seeds"])
    assert study["evaluation"]["detection_brier_calibrated"] <= (
        study["evaluation"]["detection_brier_raw"]
    )
    assert study["evaluation"]["type_accuracy"] == 1.0
    assert study["evaluation"]["detection_reliability_calibrated"]
    assert study["evaluation"]["type_reliability"]

    clean, witnesses, observed, oracle, ledger = generated(480, 2222)
    incidents = detect(clean, witnesses, observed, ledger)
    calibrated = apply_calibration(incidents, artifact)
    truth = {entry["record_id"]: entry["tampering_type"] for entry in oracle}
    predicted = {entry["record_id"]: entry for entry in calibrated}
    assert set(truth) <= set(predicted)
    for record_id, incident in predicted.items():
        assert 0 <= incident["detection_probability"] <= 1
        probabilities = incident["type_probabilities_calibrated"]
        assert set(probabilities) == set(ATTACK_TYPES)
        assert abs(sum(probabilities.values()) - 1) < 1e-5
        if record_id in truth:
            assert incident["type_prediction_calibrated"] == truth[record_id]


def test_ablation_report_shows_control_ledger_contribution():
    root = Path(__file__).resolve().parents[1]
    ablation = json.loads((root / "reports" / "ablation.json").read_text(encoding="utf-8"))
    full = ablation["results"]["all_detectors"]
    without_ledger = ablation["results"]["without_control_ledger"]
    assert full["f1"] == 1.0
    assert without_ledger["false_negative"] > full["false_negative"]
    assert without_ledger["recall"] < full["recall"]


def test_multiseed_metrics_meet_regression_targets_without_seed_leakage():
    root = Path(__file__).resolve().parents[1]
    metrics = json.loads((root / "reports" / "metrics.json").read_text(encoding="utf-8"))
    known = metrics["known_evaluation"]
    calibration = metrics["calibration"]
    targets = metrics["regression_targets"]
    aggregate = known["aggregate"]

    assert len(known["seeds"]) >= 5
    assert len(set(known["seeds"])) == len(known["seeds"])
    assert set(known["seeds"]).isdisjoint(calibration["training_seeds"])
    assert set(known["seeds"]).isdisjoint(calibration["evaluation_seeds"])
    measured = {
        "known_precision": aggregate["precision_recall_f1"]["precision"]["mean"],
        "known_recall": aggregate["precision_recall_f1"]["recall"]["mean"],
        "known_f1": aggregate["precision_recall_f1"]["f1"]["mean"],
        "known_type_accuracy": aggregate["type_accuracy"]["mean"],
        "reconstruction_status_accuracy": aggregate["reconstruction"]["status_accuracy"]["mean"],
        "reconstruction_field_accuracy": aggregate["reconstruction"]["field_accuracy"]["mean"],
        "reconstruction_field_coverage": aggregate["reconstruction"]["field_coverage"]["mean"],
    }
    assert set(measured) == set(targets)
    assert all(measured[name] >= floor for name, floor in targets.items())
    holdout = metrics["holdout_evaluation"]
    assert set(holdout["attack_families"]).isdisjoint(ATTACK_TYPES)
    assert holdout["true_positive"] + holdout["false_negative"] == len(
        holdout["attack_families"]
    )
    assert all(result["classified_unknown"] for result in holdout["per_attack"].values())
    assert all(
        result["unknown_analysis"]["invariant_violations"]
        and result["unknown_analysis"]["novelty_method"]
        for result in holdout["per_attack"].values()
    )
    assert (root / "reports" / "EVAL.md").exists()
    assert (root / "TARGETS.md").exists()


def test_api_evidence_reconstruction_and_oracle_db_isolation(tmp_path):
    clean, witnesses, observed, oracle, ledger = generated(120, 113)
    incidents = apply_calibration(
        detect(clean, witnesses, observed, ledger),
        load_calibrator(Path(__file__).resolve().parents[1] / "reports" / "calibration.json"),
    )
    reconstructed, decisions = reconstruct_manifest(
        observed, incidents, witnesses, ledger
    )
    metrics = evaluate_detection(
        oracle, incidents, decisions, reconstructed.to_dict(orient="records")
    )
    database = tmp_path / "evidence.sqlite3"
    EvidenceStore(database).replace_batch(
        observed, reconstructed, incidents, decisions, metrics
    )
    oracle_path = tmp_path / "oracle" / "attack_truth.sqlite3"
    OracleStore(oracle_path).replace(oracle)

    with TestClient(create_app(database, start_stream=False)) as client:
        assert client.get("/api/health").json()["status"] == "operational"
        listed = client.get("/api/incidents?limit=200").json()
        assert listed
        detail = client.get(f"/api/incidents/{listed[0]['record_id']}").json()
        assert detail["incident"]["evidence"]
        assert detail["incident"]["counterfactual"]
        assert 0 <= detail["incident"]["detection_probability"] <= 1
        assert detail["incident"]["type_probabilities_calibrated"]
        assert detail["reconstruction"]["method"]
        output = client.get("/api/reconstruction/manifest").json()
        assert output
        assert len(output) < len(observed)
        assert client.get("/api/hidden-injection-log").status_code == 404
    with EvidenceStore(database).connect() as connection:
        table_names = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "injection_truth" not in table_names
    stored_truth = OracleStore(oracle_path).entries()
    assert {item["record_id"]: item["tampering_type"] for item in stored_truth} == {
        item["record_id"]: item["tampering_type"] for item in oracle
    }
