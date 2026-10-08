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
    field_attempted = 0
    field_correct = 0
    per_attack: dict[str, Counter[str]] = {}
    per_status: dict[str, Counter[str]] = {}
    decision_status_counts = Counter(
        str(item["status"]) for item in decisions
    )
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
        attack_counts = per_attack.setdefault(attack, Counter())
        attack_counts["support"] += 1
        attack_counts["status_correct"] += int(status_correct)
        status_counts = per_status.setdefault(str(decision["status"]), Counter())
        status_counts["support"] += 1
        status_counts["status_correct"] += int(status_correct)
        reconstructed_row = record_by_id.get(record_id) or {}
        recovered_fields = decision.get("recovered_fields", {})
        if attack == "DELETED":
            target_fields = {
                key: value for key, value in item.get("original", {}).items()
                if key not in {
                    "record_id", "previous_hash", "payload_hash", "ledger_hash",
                    "ledger_sequence",
                }
            }
        elif expected_status == "REMOVED":
            target_fields = {}
        else:
            target_fields = {
                field: values["original"]
                for field, values in item.get("modified_fields", {}).items()
                if field not in {
                "record_id", "previous_hash", "payload_hash", "ledger_hash",
                "ledger_sequence",
                }
            }
        for field, expected_value in target_fields.items():
            if field in reconstructed_row:
                observed_value = reconstructed_row[field]
            elif field in recovered_fields:
                observed_value = recovered_fields[field]
            else:
                continue
            field_attempted += 1
            attack_counts["field_attempted"] += 1
            status_counts["field_attempted"] += 1
            matches = observed_value == expected_value
            field_correct += int(matches)
            attack_counts["field_correct"] += int(matches)
            status_counts["field_correct"] += int(matches)
        attack_counts["field_target"] += len(target_fields)
        status_counts["field_target"] += len(target_fields)
    per_attack_accuracy = {
        kind: {
            "status_accuracy": round(_ratio(counts["status_correct"], counts["support"]), 4),
            "field_accuracy": (
                round(_ratio(counts["field_correct"], counts["field_attempted"]), 4)
                if counts["field_attempted"] else None
            ),
            "field_coverage": (
                round(_ratio(counts["field_attempted"], counts["field_target"]), 4)
                if counts["field_target"] else None
            ),
            "status_support": counts["support"],
            "field_support": counts["field_attempted"],
            "field_target": counts["field_target"],
        }
        for kind, counts in sorted(per_attack.items())
    }
    all_statuses = {"ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"}
    all_statuses.update(per_status)
    per_status_accuracy = {}
    for status in sorted(all_statuses):
        counts = per_status.get(status, Counter())
        per_status_accuracy[status] = {
            "status_accuracy": (
                round(_ratio(counts["status_correct"], counts["support"]), 4)
                if counts["support"] else None
            ),
            "field_accuracy": (
                round(_ratio(counts["field_correct"], counts["field_attempted"]), 4)
                if counts["field_attempted"] else None
            ),
            "field_coverage": (
                round(_ratio(counts["field_attempted"], counts["field_target"]), 4)
                if counts["field_target"] else None
            ),
            "support": counts["support"],
            "decision_count": decision_status_counts.get(status, 0),
            "field_support": counts["field_attempted"],
            "field_target": counts["field_target"],
        }
    return {
        "reconstruction": {
            "status_accuracy": round(_ratio(correct_status, len(truth)), 4),
            "status_correct": correct_status,
            "status_total": len(truth),
            "field_accuracy": round(_ratio(field_correct, field_attempted), 4),
            "field_coverage": round(
                _ratio(field_attempted, sum(
                    counts["field_target"] for counts in per_attack.values()
                )), 4
            ),
            "field_correct": field_correct,
            "field_total": field_attempted,
            "per_attack": per_attack_accuracy,
            "by_status": per_status_accuracy,
            "disposition_counts": {
                status: decision_status_counts.get(status, 0)
                for status in sorted(all_statuses)
            },
            "field_scoring": (
                "Accuracy is correct values among attempted target fields; coverage is attempted target "
                "fields divided by the ground-truth target-field count. Deleted rows score all recoverable "
                "non-hash fields; fields without independent witnesses remain uncovered."
            ),
        }
    }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
