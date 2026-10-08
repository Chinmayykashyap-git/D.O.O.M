"""Evaluate attacks excluded from batch injection and calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from doom.calibration import apply_calibration, load_calibrator
from doom.detectors import ManifestDetector
from doom.generator import generate_dataset, make_control_ledger
from doom.reconstruction import reconstruct_manifest
from holdout_attacks import HOLDOUT_ATTACKS, inject_holdout_attacks


def evaluate_holdout(
    record_count: int = 1200, seed: int = 2291,
) -> dict[str, Any]:
    clean, witnesses = generate_dataset(record_count, seed)
    observed, truth = inject_holdout_attacks(clean, seed + 1)
    incidents = ManifestDetector().detect(
        observed,
        expected_record_ids=clean["record_id"].astype(str).tolist(),
        expected_ledger=make_control_ledger(clean),
        witnesses=witnesses,
    )
    root = Path(__file__).resolve().parent.parent
    calibrator = load_calibrator(root / "reports" / "calibration.json")
    if calibrator:
        incidents = apply_calibration(incidents, calibrator)
    by_id = {str(item["record_id"]): item for item in incidents}
    truth_ids = {item["record_id"] for item in truth}
    true_positive = len(truth_ids & set(by_id))
    false_positive = len(set(by_id) - truth_ids)
    false_negative = len(truth_ids - set(by_id))
    type_correct = sum(
        by_id[item["record_id"]]["tampering_type"] == "UNKNOWN ANOMALY"
        for item in truth if item["record_id"] in by_id
    )
    reconstruction, decisions = reconstruct_manifest(
        observed, incidents, witnesses, make_control_ledger(clean)
    )
    decision_by_id = {str(item["record_id"]): item for item in decisions}
    type_results = {}
    for attack in HOLDOUT_ATTACKS:
        record_id = next(item["record_id"] for item in truth if item["holdout_attack"] == attack)
        incident = by_id.get(record_id)
        decision = decision_by_id.get(record_id)
        type_results[attack] = {
            "detected": incident is not None,
            "classified_unknown": bool(
                incident and incident["tampering_type"] == "UNKNOWN ANOMALY"
            ),
            "detection_probability": (
                incident.get("detection_probability") if incident else 0.0
            ),
            "evidence_codes": (
                sorted({item["evidence_code"] for item in incident["evidence"]})
                if incident else []
            ),
            "unknown_analysis": (
                incident.get("unknown_analysis") if incident else None
            ),
            "reconstruction_status": decision["status"] if decision else None,
            "explanation_present": bool(decision and decision["explanation"]),
        }
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    report = {
        "seed": seed,
        "record_count": record_count,
        "attack_families": list(HOLDOUT_ATTACKS),
        "known_batch_attack_families": "none of the holdout family names appears in the batch attack catalog",
        "holdout_detector_imports": "holdout generator is imported only by this evaluator and its package export",
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if precision + recall else 0.0,
        "unknown_type_accuracy": round(type_correct / max(len(truth), 1), 4),
        "reconstruction_rows": len(reconstruction),
        "per_attack": type_results,
        "evaluation_scope": (
            "Three deterministic synthetic families held outside batch injection and calibration. "
            "This is a narrow open-set test, not generalization evidence for arbitrary attacks."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate unseen D.O.O.M. attack families.")
    parser.add_argument("--records", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=2291)
    args = parser.parse_args()
    if args.records < 30:
        parser.error("--records must be at least 30")
    report = evaluate_holdout(args.records, args.seed)
    output = Path(__file__).resolve().parent.parent / "reports" / "holdout.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), **report}, indent=2))


if __name__ == "__main__":
    main()
