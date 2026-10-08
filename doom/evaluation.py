"""Reproducible multi-seed known and isolated holdout evaluation."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path
from typing import Any

from doom.calibration import load_calibrator
from doom.corruption import ATTACK_TYPES, inject_attacks
from doom.detectors import ManifestDetector
from doom.generator import generate_dataset, make_control_ledger
from doom.metrics import evaluate_detection
from doom.reconstruction import reconstruct_manifest
from doom.streaming import measure_streaming

ROOT = Path(__file__).resolve().parent.parent
EVALUATION_SEEDS = (19, 41, 75, 2222, 31415)
RECORDS_PER_SEED = 1200
REGRESSION_TARGETS = {
    "known_precision": 0.95,
    "known_recall": 0.95,
    "known_f1": 0.95,
    "known_type_accuracy": 0.90,
    "reconstruction_status_accuracy": 0.95,
    "reconstruction_field_accuracy": 0.98,
    "reconstruction_field_coverage": 0.80,
}
METRIC_NAMES = ("precision", "recall", "f1")


def evaluate_seed(record_count: int, seed: int) -> dict[str, Any]:
    clean, witnesses = generate_dataset(record_count, seed)
    observed, truth = inject_attacks(clean, seed + 1)
    ledger = make_control_ledger(clean)
    incidents = ManifestDetector().detect(
        observed,
        expected_record_ids=clean["record_id"].astype(str).tolist(),
        expected_ledger=ledger,
        witnesses=witnesses,
    )
    reconstructed, decisions = reconstruct_manifest(
        observed, incidents, witnesses, ledger
    )
    measured = evaluate_detection(
        truth, incidents, decisions, reconstructed.to_dict(orient="records")
    )
    return measured


def _mean_std(values: list[float | int | None]) -> dict[str, float | int | None]:
    observed = [float(value) for value in values if value is not None]
    if not observed:
        return {"mean": None, "std": None}
    return {
        "mean": round(statistics.mean(observed), 6),
        "std": round(statistics.pstdev(observed), 6),
    }


def _metric_summary(
    samples: list[dict[str, Any]], keys: tuple[str, ...]
) -> dict[str, Any]:
    return {
        key: _mean_std([sample.get(key) for sample in samples])
        for key in keys
    }


def _aggregate_known(by_seed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples = list(by_seed.values())
    per_attack: dict[str, Any] = {}
    for attack in ATTACK_TYPES:
        attack_samples = [
            sample["per_attack"][attack] for sample in samples
            if attack in sample["per_attack"]
        ]
        per_attack[attack] = {
            **_metric_summary(attack_samples, METRIC_NAMES),
            "support_total": sum(item["support"] for item in attack_samples),
        }

    attack_names = sorted(ATTACK_TYPES)
    confusion = {
        expected: {observed: 0 for observed in attack_names}
        for expected in attack_names
    }
    for sample in samples:
        for expected, row in sample["type_confusion_matrix"].items():
            if expected not in confusion:
                continue
            for observed, count in row.items():
                if observed in confusion[expected]:
                    confusion[expected][observed] += count

    def aggregate_reconstruction(group_key: str, metric_keys: tuple[str, ...]):
        group_names = set()
        for sample in samples:
            group_names.update(sample["reconstruction"][group_key])
        result = {}
        for group_name in sorted(group_names):
            group_samples = [
                sample["reconstruction"][group_key][group_name]
                for sample in samples
                if group_name in sample["reconstruction"][group_key]
            ]
            result[group_name] = {
                **_metric_summary(group_samples, metric_keys),
                "support_total": sum(
                    item.get(
                        "decision_count",
                        item.get("status_support", item.get("support", 0)),
                    )
                    for item in group_samples
                ),
                "attack_support_total": sum(
                    item.get("support", item.get("status_support", 0))
                    for item in group_samples
                ),
                "field_support_total": sum(
                    item.get("field_support", 0) for item in group_samples
                ),
                "field_target_total": sum(
                    item.get("field_target", 0) for item in group_samples
                ),
            }
        return result

    return {
        "precision_recall_f1": _metric_summary(samples, METRIC_NAMES),
        "type_accuracy": _mean_std([
            sample["type_accuracy_on_detected"] for sample in samples
        ]),
        "reconstruction": {
            "status_accuracy": _mean_std([
                sample["reconstruction"]["status_accuracy"] for sample in samples
            ]),
            "field_accuracy": _mean_std([
                sample["reconstruction"]["field_accuracy"] for sample in samples
            ]),
            "field_coverage": _mean_std([
                sample["reconstruction"]["field_coverage"] for sample in samples
            ]),
            "by_attack": aggregate_reconstruction(
                "per_attack",
                ("status_accuracy", "field_accuracy", "field_coverage"),
            ),
            "by_status": aggregate_reconstruction(
                "by_status",
                ("status_accuracy", "field_accuracy", "field_coverage"),
            ),
        },
        "per_attack": per_attack,
        "type_confusion_matrix": confusion,
    }


def _make_eval_markdown(metrics: dict[str, Any]) -> str:
    known = metrics["known_evaluation"]
    aggregate = known["aggregate"]
    lines = [
        "# Evaluation report",
        "",
        "All reported detection and reconstruction results are generated from seeded synthetic data. "
        "They are not evidence of field performance.",
        "",
        f"- Seeds: `{', '.join(map(str, known['seeds']))}`",
        f"- Records per seed: {known['record_count_per_seed']}",
        f"- Calibration training seeds: `{', '.join(map(str, metrics['calibration']['training_seeds']))}`",
        "- Holdout attack generators are excluded from batch injection and calibration.",
        "",
        "## Known batch attacks",
        "",
        "| Metric | Mean | Std. dev. |",
        "|---|---:|---:|",
    ]
    for metric, stats in aggregate["precision_recall_f1"].items():
        lines.append(f"| {metric.title()} | {stats['mean']:.4f} | {stats['std']:.4f} |")
    for metric, stats in aggregate["reconstruction"].items():
        if isinstance(stats, dict) and "mean" in stats and stats["mean"] is not None:
            lines.append(f"| Reconstruction {metric.replace('_', ' ').title()} | {stats['mean']:.4f} | {stats['std']:.4f} |")
    type_accuracy = aggregate["type_accuracy"]
    lines.append(
        f"| Type accuracy | {type_accuracy['mean']:.4f} | {type_accuracy['std']:.4f} |"
    )
    lines.extend([
        "",
        "### Per-attack precision, recall, and F1",
        "",
        "| Attack | Precision mean ± std | Recall mean ± std | F1 mean ± std | Support |",
        "|---|---:|---:|---:|---:|",
    ])
    for attack, stats in sorted(aggregate["per_attack"].items()):
        lines.append(
            f"| {attack} | {stats['precision']['mean']:.4f} ± {stats['precision']['std']:.4f} "
            f"| {stats['recall']['mean']:.4f} ± {stats['recall']['std']:.4f} "
            f"| {stats['f1']['mean']:.4f} ± {stats['f1']['std']:.4f} "
            f"| {stats['support_total']} |"
        )
    lines.extend([
        "",
        "### Type-classification confusion matrix",
        "",
        "| Expected \\ Predicted | " + " | ".join(ATTACK_TYPES) + " |",
        "|---|" + "---:|" * len(ATTACK_TYPES),
    ])
    for expected, row in aggregate["type_confusion_matrix"].items():
        lines.append(
            f"| {expected} | "
            + " | ".join(str(row.get(observed, 0)) for observed in ATTACK_TYPES)
            + " |"
        )

    lines.extend([
        "",
        "### Reconstruction by attack and disposition",
        "",
        "| Group | Status accuracy | Field accuracy | Field coverage | Support |",
        "|---|---:|---:|---:|---:|",
    ])
    for heading, key in (("Attack", "by_attack"), ("Disposition", "by_status")):
        for name, values in aggregate["reconstruction"][key].items():
            def format_stat(metric: str) -> str:
                result = values[metric]
                if result["mean"] is None:
                    return "n/a"
                return f"{result['mean']:.4f} ± {result['std']:.4f}"
            lines.append(
                f"| {heading}: {name} | {format_stat('status_accuracy')} "
                f"| {format_stat('field_accuracy')} | {format_stat('field_coverage')} "
                f"| {values['support_total']} |"
            )
    lines.extend([
        "",
        "Field accuracy is correctness among attempted target fields. Field coverage is the attempted "
        "target-field count divided by the number of ground-truth target fields. A removed record is "
        "not credited with field repair. Missing records can have high partial-field accuracy and still "
        "remain `UNRECOVERABLE`.",
        "",
        "## Calibration and ablation",
        "",
        "The calibration curve and one-factor ablation below are reused from the Phase 2 artifacts; "
        "no holdout observations enter either artifact.",
        "",
        "| Calibration metric | Raw | Calibrated |",
        "|---|---:|---:|",
        f"| Detection Brier | {metrics['calibration']['evaluation']['detection_brier_raw']:.6f} "
        f"| {metrics['calibration']['evaluation']['detection_brier_calibrated']:.6f} |",
        f"| Detection ECE | {metrics['calibration']['evaluation']['detection_ece_raw']:.6f} "
        f"| {metrics['calibration']['evaluation']['detection_ece_calibrated']:.6f} |",
        "",
        "### Detection reliability bins (calibrated)",
        "",
        "| Count | Mean predicted | Observed frequency |",
        "|---:|---:|---:|",
    ])
    for row in metrics["calibration"]["evaluation"]["detection_reliability_calibrated"]:
        lines.append(
            f"| {row['count']} | {row['mean_predicted_probability']:.6f} "
            f"| {row['observed_frequency']:.6f} |"
        )
    lines.extend([
        "",
        "### Detector ablation",
        "",
        "| Configuration | Precision | Recall | F1 | Type accuracy |",
        "|---|---:|---:|---:|---:|",
    ])
    for name, values in metrics["ablation"]["results"].items():
        lines.append(
            f"| {name} | {values['precision']:.4f} | {values['recall']:.4f} "
            f"| {values['f1']:.4f} | {values['type_accuracy']:.4f} |"
        )

    stream = metrics["streaming"]
    lines.extend([
        "",
        "## Streaming performance",
        "",
        f"Measured {stream['event_count']} local events at "
        f"{stream['throughput_events_per_second']:.3f} events/second; "
        f"p50 latency {stream['latency_ms']['p50']:.3f} ms, "
        f"p95 latency {stream['latency_ms']['p95']:.3f} ms, and maximum "
        f"{stream['latency_ms']['max']:.3f} ms. The run raised "
        f"{stream['unknown_anomaly_count']} streaming unknown anomaly.",
        "",
        stream["measurement"],
        "",
        "These are single-host synthetic microbenchmark measurements, not a production throughput guarantee.",
        "",
    ])

    holdout = metrics["holdout_evaluation"]
    lines.extend([
        "",
        "## Isolated holdout attacks",
        "",
        f"Recall: {holdout['recall']:.4f} ({holdout['true_positive']} TP, "
        f"{holdout['false_negative']} FN); precision: {holdout['precision']:.4f} "
        f"({holdout['false_positive']} FP). {holdout['evaluation_scope']}",
        "",
        "| Holdout family | Detected | Classified unknown | Nearest known type | Similarity | Novelty | Reconstruction status |",
        "|---|---:|---:|---|---:|---:|---|",
    ])
    for family, values in holdout["per_attack"].items():
        analysis = values.get("unknown_analysis")
        nearest = analysis["nearest_known_attack_type"] if analysis else "n/a"
        similarity = f"{analysis['nearest_similarity']:.4f}" if analysis else "n/a"
        novelty = f"{analysis['novelty_score']:.4f}" if analysis else "n/a"
        lines.append(
            f"| {family} | {values['detected']} | {values['classified_unknown']} "
            f"| {nearest} | {similarity} | {novelty} "
            f"| {values['reconstruction_status']} |"
        )
    lines.append(
        "A similarity of 0.0000 means no evidence-signature overlap; the displayed nearest category is "
        "only a deterministic zero-distance tie-break, not a semantic attribution."
    )
    lines.extend([
        "",
        "## What we do poorly",
        "",
        "- The known-attack evaluation is a closed, synthetic generator suite; repeated perfect detection "
        "does not establish real-world accuracy or resilience against adaptive tampering.",
        "- Holdout coverage is only three attack instances across three synthetic families. The measured "
        "precision and recall are too small-sample to support a general open-set performance claim.",
        "- A deleted record cannot be fully restored when independent sources do not attest every field; "
        "the system deliberately leaves such rows `UNRECOVERABLE` and reports partial coverage.",
        "- Novel schema evidence can yield a low calibrated probability even when rule-based handling "
        "raises an unknown anomaly; probability estimates and alert policy are not interchangeable.",
        "- Synthetic witnesses are generated with the manifest and are not authenticated external carrier, "
        "customs, or port systems.",
        f"- Streaming performance covers only {stream['event_count']} local events and "
        f"{stream['unknown_anomaly_count']} stream-only unknown anomaly; latency and throughput are "
        "single-host measurements, not capacity guarantees.",
        "",
        "Reproduce this report with `python -m doom.evaluation` (or `make eval` once the project targets "
        "are installed).",
        "",
    ])
    return "\n".join(lines)


def _make_targets_markdown(metrics: dict[str, Any]) -> str:
    targets = metrics["regression_targets"]
    known = metrics["known_evaluation"]["aggregate"]
    rows = [
        ("Known precision", known["precision_recall_f1"]["precision"]["mean"], "known_precision"),
        ("Known recall", known["precision_recall_f1"]["recall"]["mean"], "known_recall"),
        ("Known F1", known["precision_recall_f1"]["f1"]["mean"], "known_f1"),
        ("Known type accuracy", known["type_accuracy"]["mean"], "known_type_accuracy"),
        ("Reconstruction status accuracy", known["reconstruction"]["status_accuracy"]["mean"], "reconstruction_status_accuracy"),
        ("Reconstruction field accuracy", known["reconstruction"]["field_accuracy"]["mean"], "reconstruction_field_accuracy"),
        ("Reconstruction field coverage", known["reconstruction"]["field_coverage"]["mean"], "reconstruction_field_coverage"),
    ]
    lines = [
        "# Regression targets",
        "",
        "Thresholds are conservative floors derived from the measured multi-seed synthetic evaluation "
        "in [`reports/metrics.json`](./reports/metrics.json). They are regression guards, not production "
        "service-level objectives.",
        "",
        "| Metric | Measured mean | Minimum accepted |",
        "|---|---:|---:|",
    ]
    for label, measured, key in rows:
        lines.append(f"| {label} | {measured:.4f} | {targets[key]:.4f} |")
    lines.extend([
        "",
        "A regression test enforces every listed floor against the checked-in measured evaluation artifact. "
        "Holdout results are reported independently and are not used to choose or tune these thresholds.",
        "",
    ])
    return "\n".join(lines)


def run_evaluation(
    record_count: int = RECORDS_PER_SEED,
    seeds: tuple[int, ...] = EVALUATION_SEEDS,
) -> dict[str, Any]:
    calibration_path = ROOT / "reports" / "calibration.json"
    calibrator = load_calibrator(calibration_path)
    if calibrator is None:
        raise FileNotFoundError(f"Required calibration artifact missing: {calibration_path}")
    calibration = calibrator["study"]
    overlap = set(seeds) & (
        set(calibration["training_seeds"]) | set(calibration["evaluation_seeds"])
    )
    if len(seeds) < 5:
        raise ValueError("evaluation requires at least five independent seeds")
    if len(set(seeds)) != len(seeds) or overlap:
        raise ValueError(f"evaluation seeds must be unique and calibration-disjoint: {sorted(overlap)}")

    by_seed = {
        str(seed): evaluate_seed(record_count, seed) for seed in seeds
    }
    holdout_path = ROOT / "reports" / "holdout.json"
    if not holdout_path.exists():
        raise FileNotFoundError(
            f"Required holdout artifact missing: {holdout_path}; run the isolated holdout evaluator first."
        )
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    if holdout.get("seed") in seeds:
        raise ValueError("known and holdout evaluations must use disjoint seeds")
    if not set(holdout.get("attack_families", ())).isdisjoint(ATTACK_TYPES):
        raise ValueError("holdout families must remain outside the known attack catalog")
    if any(
        not values.get("unknown_analysis")
        for values in holdout.get("per_attack", {}).values()
    ):
        raise ValueError("holdout report is stale or missing unknown-anomaly analysis")
    ablation_path = ROOT / "reports" / "ablation.json"
    ablation = json.loads(ablation_path.read_text(encoding="utf-8"))
    report = {
        "known_evaluation": {
            "seeds": list(seeds),
            "record_count_per_seed": record_count,
            "by_seed": by_seed,
            "aggregate": _aggregate_known(by_seed),
            "evaluation_scope": (
                "Five fixed synthetic seeds excluded from the calibration study's training and "
                "evaluation seeds. The evaluator oracle is used only after detector and reconstruction output."
            ),
        },
        "holdout_evaluation": holdout,
        "calibration": calibration,
        "ablation": ablation,
        "streaming": asyncio.run(measure_streaming()),
        "regression_targets": REGRESSION_TARGETS,
    }
    metrics_path = ROOT / "reports" / "metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "reports" / "holdout.json").write_text(
        json.dumps(holdout, indent=2), encoding="utf-8"
    )
    (ROOT / "reports" / "EVAL.md").write_text(
        _make_eval_markdown(report), encoding="utf-8"
    )
    (ROOT / "TARGETS.md").write_text(
        _make_targets_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated, reproducible D.O.O.M. evaluation.")
    parser.add_argument("--records", type=int, default=RECORDS_PER_SEED)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(EVALUATION_SEEDS))
    args = parser.parse_args()
    if args.records < 30:
        parser.error("--records must be at least 30")
    report = run_evaluation(args.records, tuple(args.seeds))
    print(json.dumps({
        "metrics": str(ROOT / "reports" / "metrics.json"),
        "known_seeds": report["known_evaluation"]["seeds"],
        "known_aggregate": report["known_evaluation"]["aggregate"],
        "holdout": {
            "precision": report["holdout_evaluation"]["precision"],
            "recall": report["holdout_evaluation"]["recall"],
            "families": report["holdout_evaluation"]["attack_families"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
