"""Evaluation metrics; ground truth enters only through this evaluator module."""

from __future__ import annotations

from typing import Any


def evaluate_detection(
    hidden_injection_log: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    truth = {item["record_id"]: item["tampering_type"] for item in hidden_injection_log}
    predicted = {item["record_id"]: item["tampering_type"] for item in incidents}
    expected_ids = set(truth)
    found_ids = expected_ids & set(predicted)
    true_positive = len(found_ids)
    false_positive = len(set(predicted) - expected_ids)
    false_negative = len(expected_ids - set(predicted))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return {
        "injected_attacks": len(truth),
        "detected_records": len(predicted),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        "type_accuracy_on_detected": round(
            sum(predicted[key] == truth[key] for key in found_ids) / true_positive, 4
        ) if true_positive else 0.0,
        "evaluation_scope": "Record-level comparison against the isolated synthetic injection log; not a production benchmark.",
    }
