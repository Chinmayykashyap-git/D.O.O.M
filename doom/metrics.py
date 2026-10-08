"""Evaluator-only record, type, and field-level scores for synthetic runs."""

from __future__ import annotations

from collections import Counter
from typing import Any


def evaluate_detection(
    hidden_injection_log: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    reconstruction_decisions: list[dict[str, Any]] | None = None,
    reconstructed_manifest: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    truth = {
        str(item["record_id"]): str(item["tampering_type"])
        for item in hidden_injection_log
    }
    predicted = {
        str(item["record_id"]): str(item["tampering_type"])
        for item in incidents
    }
    expected_ids = set(truth)
    found_ids = expected_ids & set(predicted)
    true_positive = len(found_ids)
    false_positive = len(set(predicted) - expected_ids)
    false_negative = len(expected_ids - set(predicted))
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    attack_types = sorted(set(truth.values()))
    per_attack: dict[str, Any] = {}
    confusion: dict[str, dict[str, int]] = {
        expected: {observed: 0 for observed in attack_types}
        for expected in attack_types
    }
    for kind in attack_types:
        actual = {key for key, value in truth.items() if value == kind}
        detected_as = {key for key, value in predicted.items() if value == kind}
        correct = sum(predicted.get(key) == kind for key in actual)
        class_precision = _ratio(correct, len(detected_as))
        class_recall = _ratio(correct, len(actual))
        per_attack[kind] = {
            "support": len(actual),
            "true_positive": correct,
            "false_positive": len(detected_as - actual),
            "false_negative": len(actual - detected_as),
            "precision": round(class_precision, 4),
            "recall": round(class_recall, 4),
            "f1": _f1(class_precision, class_recall),
        }
    for record_id in found_ids:
        expected_type, observed_type = truth[record_id], predicted[record_id]
        if expected_type in confusion and observed_type in confusion[expected_type]:
            confusion[expected_type][observed_type] += 1

    result: dict[str, Any] = {
        "injected_attacks": len(truth),
        "detected_records": len(predicted),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": _f1(precision, recall),
        "type_accuracy_on_detected": round(
            sum(predicted[key] == truth[key] for key in found_ids) / true_positive, 4
        ) if true_positive else 0.0,
        "per_attack": per_attack,
        "type_confusion_matrix": confusion,
        "evaluation_scope": (
            "Synthetic record-level comparison against a separately stored injection oracle; "
            "not a production benchmark."
        ),
    }
    if reconstruction_decisions is not None and reconstructed_manifest is not None:
        result.update(_evaluate_reconstruction(
            hidden_injection_log, reconstruction_decisions, reconstructed_manifest
        ))
    return result


def _evaluate_reconstruction(
    truth: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    reconstructed: list[dict[str, Any]],
) -> dict[str, Any]:
    decision_by_id = {str(item["record_id"]): item for item in decisions}
    record_by_id = {str(item["record_id"]): item for item in reconstructed}
    correct_status = 0
    field_total = 0
    field_correct = 0
    per_attack: dict[str, Counter[str]] = {}
    for item in truth:
        record_id = str(item["record_id"])
        attack = str(item["tampering_type"])
        decision = decision_by_id.get(record_id)
        if decision is None:
            continue
        expected_status = (
            "UNRECOVERABLE" if attack == "DELETED"
            else "REMOVED" if attack.startswith("DUPLICATE") or attack == "FABRICATED"
            else "REPAIRED"
        )
        status_correct = decision["status"] == expected_status
        correct_status += int(status_correct)
        counts = per_attack.setdefault(attack, Counter())
        counts["support"] += 1
        counts["status_correct"] += int(status_correct)
        source_id = str(item.get("source_record_id", record_id))
        reconstructed_row = record_by_id.get(record_id) or record_by_id.get(source_id)
        if not reconstructed_row:
            continue
        for field, values in item.get("modified_fields", {}).items():
            if field in {
                "record_id", "previous_hash", "payload_hash", "ledger_hash",
                "ledger_sequence",
            }:
                continue
            field_total += 1
            counts["field_total"] += 1
            matches = reconstructed_row.get(field) == values["original"]
            field_correct += int(matches)
            counts["field_correct"] += int(matches)
    per_attack_accuracy = {
        kind: {
            "status_accuracy": round(_ratio(counts["status_correct"], counts["support"]), 4),
            "field_accuracy": (
                round(_ratio(counts["field_correct"], counts["field_total"]), 4)
                if counts["field_total"] else None
            ),
            "status_support": counts["support"],
            "field_support": counts["field_total"],
        }
        for kind, counts in sorted(per_attack.items())
    }
    return {
        "reconstruction": {
            "status_accuracy": round(_ratio(correct_status, len(truth)), 4),
            "status_correct": correct_status,
            "status_total": len(truth),
            "field_accuracy": round(_ratio(field_correct, field_total), 4),
            "field_correct": field_correct,
            "field_total": field_total,
            "per_attack": per_attack_accuracy,
        }
    }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
