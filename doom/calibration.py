"""Reproducible, seed-separated calibration for detector evidence outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

from doom.corruption import ATTACK_TYPES, inject_attacks
from doom.detectors import ManifestDetector
from doom.generator import generate_dataset, make_control_ledger
from doom.metrics import evaluate_detection

TRAIN_SEEDS = (113, 401, 809, 1301)
EVALUATION_SEEDS = (1501, 1907)
NUMERIC_FEATURES = (
    "event_present",
    "evidence_count",
    "detector_count",
    "max_contribution",
    "total_contribution",
    "risk_score",
)


def _feature_values(incident: dict[str, Any] | None) -> dict[str, float]:
    values = {name: 0.0 for name in NUMERIC_FEATURES}
    if incident is None:
        return values
    evidence = incident.get("evidence", [])
    contributions = [float(item.get("score_contribution", 0.0)) for item in evidence]
    values.update({
        "event_present": 1.0,
        "evidence_count": float(len(evidence)),
        "detector_count": float(len(set(incident.get("detectors", [])))),
        "max_contribution": max(contributions, default=0.0),
        "total_contribution": sum(contributions),
        "risk_score": float(incident.get("risk_score", 0.0)) / 100.0,
    })
    for item in evidence:
        values[f"evidence:{item['evidence_code']}"] = 1.0
        values[f"detector:{item['detector_id']}"] = 1.0
    for attack_type, value in incident.get("type_probabilities", {}).items():
        values[f"hypothesis:{attack_type}"] = float(value)
    return values


def _matrix(
    incidents: list[dict[str, Any]],
    record_ids: list[str],
    feature_names: list[str],
) -> np.ndarray:
    by_id = {str(item["record_id"]): item for item in incidents}
    matrix = np.zeros((len(record_ids), len(feature_names)), dtype=float)
    positions = {name: index for index, name in enumerate(feature_names)}
    for row, record_id in enumerate(record_ids):
        for name, value in _feature_values(by_id.get(record_id)).items():
            if name in positions:
                matrix[row, positions[name]] = value
    return matrix


def _scale(matrix: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (matrix - mean) / scale


def _serialize_model(
    model: LogisticRegression, mean: np.ndarray, scale: np.ndarray,
) -> dict[str, Any]:
    return {
        "classes": [str(item) for item in model.classes_.tolist()],
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "coefficients": model.coef_.tolist(),
        "intercepts": model.intercept_.tolist(),
    }


def _probabilities(matrix: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    scaled = _scale(matrix, np.asarray(model["mean"]), np.asarray(model["scale"]))
    logits = scaled @ np.asarray(model["coefficients"]).T + np.asarray(model["intercepts"])
    if logits.shape[1] == 1:
        positive = 1 / (1 + np.exp(-np.clip(logits[:, 0], -40, 40)))
        return np.column_stack((1 - positive, positive))
    logits -= logits.max(axis=1, keepdims=True)
    exponent = np.exp(logits)
    return exponent / exponent.sum(axis=1, keepdims=True)


def _dataset(seed: int, count: int) -> tuple[
    pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]], list[str],
]:
    clean, witnesses = generate_dataset(count, seed)
    observed, truth = inject_attacks(clean, seed + 1)
    ledger = make_control_ledger(clean)
    incidents = ManifestDetector().detect(
        observed,
        expected_record_ids=clean["record_id"].astype(str).tolist(),
        expected_ledger=ledger,
        witnesses=witnesses,
    )
    labels = {str(item["record_id"]): str(item["tampering_type"]) for item in truth}
    record_ids = sorted(set(clean["record_id"].astype(str)) | set(observed["record_id"].astype(str)))
    ids = record_ids + sorted(set(labels) - set(record_ids))
    return observed, truth, incidents, ids


def _expected_calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 10,
) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for index in range(bins):
        mask = (probabilities >= edges[index]) & (
            probabilities < edges[index + 1]
            if index < bins - 1 else probabilities <= edges[index + 1]
        )
        if mask.any():
            result += float(mask.mean()) * abs(
                float(labels[mask].mean()) - float(probabilities[mask].mean())
            )
    return result


def _reliability_curve(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 10,
) -> list[dict[str, float | int]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    curve = []
    for index in range(bins):
        mask = (probabilities >= edges[index]) & (
            probabilities < edges[index + 1]
            if index < bins - 1 else probabilities <= edges[index + 1]
        )
        if mask.any():
            curve.append({
                "count": int(mask.sum()),
                "mean_predicted_probability": round(float(probabilities[mask].mean()), 6),
                "observed_frequency": round(float(labels[mask].mean()), 6),
            })
    return curve


def fit_calibration_study(
    output_path: Path,
    record_count: int = 1200,
    training_seeds: tuple[int, ...] = TRAIN_SEEDS,
    evaluation_seeds: tuple[int, ...] = EVALUATION_SEEDS,
) -> dict[str, Any]:
    """Fit only on listed training seeds; evaluate once on disjoint seeds."""
    training: list[tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]] = []
    feature_names = set(NUMERIC_FEATURES)
    for seed in training_seeds:
        _, truth, incidents, ids = _dataset(seed, record_count)
        for incident in incidents:
            feature_names.update(_feature_values(incident))
        training.append((truth, incidents, ids))
    ordered_features = sorted(feature_names)

    binary_x: list[np.ndarray] = []
    binary_y: list[int] = []
    type_x: list[np.ndarray] = []
    type_y: list[str] = []
    for truth, incidents, ids in training:
        matrix = _matrix(incidents, ids, ordered_features)
        labels_by_id = {
            str(item["record_id"]): str(item["tampering_type"]) for item in truth
        }
        for index, record_id in enumerate(ids):
            label = labels_by_id.get(record_id)
            binary_x.append(matrix[index])
            binary_y.append(int(label is not None))
            if label is not None:
                type_x.append(matrix[index])
                type_y.append(label)

    binary_matrix = np.asarray(binary_x)
    binary_labels = np.asarray(binary_y)
    binary_mean = binary_matrix.mean(axis=0)
    binary_scale = binary_matrix.std(axis=0)
    binary_scale[binary_scale == 0] = 1.0
    binary_model = LogisticRegression(max_iter=2000, random_state=0).fit(
        _scale(binary_matrix, binary_mean, binary_scale), binary_labels
    )
    type_matrix = np.asarray(type_x)
    type_labels = np.asarray(type_y)
    type_mean = type_matrix.mean(axis=0)
    type_scale = type_matrix.std(axis=0)
    type_scale[type_scale == 0] = 1.0
    type_model = LogisticRegression(
        max_iter=2000, random_state=0, solver="lbfgs",
    ).fit(_scale(type_matrix, type_mean, type_scale), type_labels)

    binary_serialized = _serialize_model(binary_model, binary_mean, binary_scale)
    type_serialized = _serialize_model(type_model, type_mean, type_scale)
    per_seed: dict[str, Any] = {}
    all_detection_labels: list[int] = []
    all_detection_probabilities: list[float] = []
    all_raw_scores: list[float] = []
    type_actual: list[str] = []
    type_predicted: list[str] = []
    type_probability_rows: list[list[float]] = []
    type_class_order = type_serialized["classes"]

    for seed in evaluation_seeds:
        _, truth, incidents, ids = _dataset(seed, record_count)
        matrix = _matrix(incidents, ids, ordered_features)
        truth_by_id = {str(item["record_id"]): str(item["tampering_type"]) for item in truth}
        detection_labels_for_seed = np.asarray([
            int(record_id in truth_by_id) for record_id in ids
        ])
        probabilities = _probabilities(matrix, binary_serialized)[:, 1]
        raw_scores = np.asarray([
            max(
                (float(item["confidence"]) for item in incidents
                 if str(item["record_id"]) == record_id),
                default=0.0,
            )
            for record_id in ids
        ])
        detected = [record_id for record_id in ids if record_id in truth_by_id]
        detected_matrix = _matrix(incidents, detected, ordered_features)
        class_probabilities = _probabilities(detected_matrix, type_serialized)
        class_predictions = [
            type_class_order[int(index)] for index in class_probabilities.argmax(axis=1)
        ]
        class_actual = [truth_by_id[record_id] for record_id in detected]
        per_seed[str(seed)] = {
            "record_support": len(ids),
            "attack_support": int(detection_labels_for_seed.sum()),
            "detection_brier_raw": round(float(brier_score_loss(
                detection_labels_for_seed, raw_scores
            )), 6),
            "detection_brier_calibrated": round(
                float(brier_score_loss(detection_labels_for_seed, probabilities)), 6
            ),
            "detection_ece_raw": round(_expected_calibration_error(
                detection_labels_for_seed, raw_scores
            ), 6),
            "detection_ece_calibrated": round(
                _expected_calibration_error(detection_labels_for_seed, probabilities), 6
            ),
            "detection_reliability_raw": _reliability_curve(
                detection_labels_for_seed, raw_scores
            ),
            "detection_reliability_calibrated": _reliability_curve(
                detection_labels_for_seed, probabilities
            ),
            "type_accuracy": round(float(accuracy_score(class_actual, class_predictions)), 6)
            if class_actual else 0.0,
            "type_log_loss": round(float(log_loss(
                class_actual, class_probabilities, labels=type_class_order
            )), 6) if class_actual else 0.0,
            "type_brier": round(float(np.mean(np.sum(
                (class_probabilities - np.eye(len(type_class_order))[[
                    type_class_order.index(item) for item in class_actual
                ]]) ** 2, axis=1
            ))), 6) if class_actual else 0.0,
            "type_top_label_ece": round(_expected_calibration_error(
                np.asarray([actual == predicted for actual, predicted in zip(class_actual, class_predictions)]),
                class_probabilities.max(axis=1),
            ), 6) if class_actual else 0.0,
            "type_reliability": _reliability_curve(
                np.asarray([actual == predicted for actual, predicted in zip(class_actual, class_predictions)]),
                class_probabilities.max(axis=1),
            ),
        }
        all_detection_labels.extend(int(label) for label in detection_labels_for_seed)
        all_detection_probabilities.extend(probabilities.tolist())
        all_raw_scores.extend(raw_scores.tolist())
        type_actual.extend(class_actual)
        type_predicted.extend(class_predictions)
        type_probability_rows.extend(class_probabilities.tolist())

    detection_labels = np.asarray(all_detection_labels)
    calibrated_probs = np.asarray(all_detection_probabilities)
    raw_probs = np.asarray(all_raw_scores)
    typed = np.asarray(type_actual)
    type_probs = np.asarray(type_probability_rows)
    type_one_hot = np.eye(len(type_class_order))[[
        type_class_order.index(item) for item in type_actual
    ]]
    report = {
        "method": "standardized logistic regression; all attack labels are synthetic",
        "training_seeds": list(training_seeds),
        "evaluation_seeds": list(evaluation_seeds),
        "record_count_per_seed": record_count,
        "training_records": len(binary_y),
        "training_attacks": len(type_y),
        "feature_count": len(ordered_features),
        "type_classes": type_class_order,
        "evaluation": {
            "by_seed": per_seed,
            "detection_brier_raw": round(float(brier_score_loss(detection_labels, raw_probs)), 6),
            "detection_brier_calibrated": round(
                float(brier_score_loss(detection_labels, calibrated_probs)), 6
            ),
            "detection_ece_raw": round(_expected_calibration_error(detection_labels, raw_probs), 6),
            "detection_ece_calibrated": round(
                _expected_calibration_error(detection_labels, calibrated_probs), 6
            ),
            "detection_reliability_raw": _reliability_curve(detection_labels, raw_probs),
            "detection_reliability_calibrated": _reliability_curve(
                detection_labels, calibrated_probs
            ),
            "type_accuracy": round(float(accuracy_score(typed, type_predicted)), 6),
            "type_log_loss": round(float(log_loss(
                typed, type_probs, labels=type_class_order
            )), 6),
            "type_brier": round(float(np.mean(np.sum((type_probs - type_one_hot) ** 2, axis=1))), 6),
            "type_top_label_ece": round(_expected_calibration_error(
                np.asarray([actual == predicted for actual, predicted in zip(typed, type_predicted)]),
                type_probs.max(axis=1),
            ), 6),
            "type_reliability": _reliability_curve(
                np.asarray([actual == predicted for actual, predicted in zip(typed, type_predicted)]),
                type_probs.max(axis=1),
            ),
        },
    }
    artifact = {
        "feature_names": ordered_features,
        "binary_model": binary_serialized,
        "type_model": type_serialized,
        "study": report,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return report


def run_ablation_study(
    output_path: Path, record_count: int = 1200, seed: int = 1907,
) -> dict[str, Any]:
    clean, witnesses = generate_dataset(record_count, seed)
    observed, truth = inject_attacks(clean, seed + 1)
    ledger = make_control_ledger(clean)
    groups = (
        "duplicate_detection", "integrity_hash", "control_ledger",
        "relational_analysis", "route_validation", "temporal_analysis",
        "movement_history", "customs_witness", "schema_novelty",
    )
    results: dict[str, Any] = {}
    all_groups = set(groups)
    for removed in (None, *groups):
        active = all_groups if removed is None else all_groups - {removed}
        incidents = ManifestDetector().detect(
            observed,
            expected_record_ids=clean["record_id"].astype(str).tolist(),
            expected_ledger=ledger,
            witnesses=witnesses,
            active_detectors=active,
        )
        measured = evaluate_detection(truth, incidents)
        results["all_detectors" if removed is None else f"without_{removed}"] = {
            "removed_detector": removed,
            "enabled_detectors": sorted(active),
            "true_positive": measured["true_positive"],
            "false_positive": measured["false_positive"],
            "false_negative": measured["false_negative"],
            "precision": measured["precision"],
            "recall": measured["recall"],
            "f1": measured["f1"],
            "type_accuracy": measured["type_accuracy_on_detected"],
            "per_attack_recall": {
                name: item["recall"] for name, item in measured["per_attack"].items()
            },
        }
    report = {
        "seed": seed,
        "record_count": record_count,
        "attack_families": list(ATTACK_TYPES),
        "evaluation_scope": "One fixed synthetic seed; detector ablation is descriptive, not causal evidence.",
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def apply_calibration(
    incidents: list[dict[str, Any]], artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach fitted detection/type probabilities without changing raw evidence."""
    ids = [str(item["record_id"]) for item in incidents]
    matrix = _matrix(incidents, ids, artifact["feature_names"])
    detection = _probabilities(matrix, artifact["binary_model"])[:, 1]
    classes = artifact["type_model"]["classes"]
    type_probs = _probabilities(matrix, artifact["type_model"])
    calibrated = []
    for index, incident in enumerate(incidents):
        result = dict(incident)
        result["detection_probability"] = round(float(detection[index]), 6)
        result["type_probabilities_calibrated"] = {
            name: round(float(type_probs[index, class_index]), 6)
            for class_index, name in enumerate(classes)
        }
        result["type_prediction_calibrated"] = classes[int(type_probs[index].argmax())]
        calibrated.append(result)
    return calibrated


def load_calibrator(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    calibration_path = root / "reports" / "calibration.json"
    calibration = fit_calibration_study(calibration_path)
    ablation_path = root / "reports" / "ablation.json"
    ablation = run_ablation_study(ablation_path)
    print(json.dumps({
        "calibration_artifact": str(calibration_path),
        "calibration": calibration,
        "ablation_report": str(ablation_path),
        "ablation": ablation,
    }, indent=2))


if __name__ == "__main__":
    main()
