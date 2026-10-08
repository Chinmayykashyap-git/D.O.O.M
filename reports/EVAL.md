# Evaluation report

All reported detection and reconstruction results are generated from seeded synthetic data. They are not evidence of field performance.

- Seeds: `19, 41, 75, 2222, 31415`
- Records per seed: 1200
- Calibration training seeds: `113, 401, 809, 1301`
- Holdout attack generators are excluded from batch injection and calibration.

## Known batch attacks

| Metric | Mean | Std. dev. |
|---|---:|---:|
| Precision | 1.0000 | 0.0000 |
| Recall | 1.0000 | 0.0000 |
| F1 | 1.0000 | 0.0000 |
| Reconstruction Status Accuracy | 1.0000 | 0.0000 |
| Reconstruction Field Accuracy | 1.0000 | 0.0000 |
| Reconstruction Field Coverage | 0.8750 | 0.0000 |
| Type accuracy | 1.0000 | 0.0000 |

### Per-attack precision, recall, and F1

| Attack | Precision mean ± std | Recall mean ± std | F1 mean ± std | Support |
|---|---:|---:|---:|---:|
| DELETED | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| DUPLICATE_EXACT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| DUPLICATE_NEAR | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| FABRICATED | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| MODIFIED_VALUE | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| NEGATIVE_TRANSIT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| PORT_SKIP | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| RELATIONAL_ORPHAN | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| SLOW_DRIFT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| TELEPORTATION | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| TIMESTAMP_SHIFT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| VESSEL_MISMATCH | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |

### Type-classification confusion matrix

| Expected \ Predicted | MODIFIED_VALUE | DELETED | DUPLICATE_EXACT | DUPLICATE_NEAR | FABRICATED | TIMESTAMP_SHIFT | TELEPORTATION | PORT_SKIP | NEGATIVE_TRANSIT | RELATIONAL_ORPHAN | VESSEL_MISMATCH | SLOW_DRIFT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DELETED | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DUPLICATE_EXACT | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DUPLICATE_NEAR | 0 | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| FABRICATED | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| MODIFIED_VALUE | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NEGATIVE_TRANSIT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 0 |
| PORT_SKIP | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 0 | 0 |
| RELATIONAL_ORPHAN | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 | 0 | 0 |
| SLOW_DRIFT | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 |
| TELEPORTATION | 0 | 0 | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 |
| TIMESTAMP_SHIFT | 0 | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 |
| VESSEL_MISMATCH | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 | 0 |

### Reconstruction by attack and disposition

| Group | Status accuracy | Field accuracy | Field coverage | Support |
|---|---:|---:|---:|---:|
| Attack: DELETED | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.8095 ± 0.0000 | 35 |
| Attack: DUPLICATE_EXACT | 1.0000 ± 0.0000 | n/a | n/a | 35 |
| Attack: DUPLICATE_NEAR | 1.0000 ± 0.0000 | n/a | n/a | 35 |
| Attack: FABRICATED | 1.0000 ± 0.0000 | n/a | n/a | 35 |
| Attack: MODIFIED_VALUE | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: NEGATIVE_TRANSIT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: PORT_SKIP | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: RELATIONAL_ORPHAN | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: SLOW_DRIFT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: TELEPORTATION | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: TIMESTAMP_SHIFT | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Attack: VESSEL_MISMATCH | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 35 |
| Disposition: ORIGINAL | n/a | n/a | n/a | 5685 |
| Disposition: REMOVED | 1.0000 ± 0.0000 | n/a | n/a | 105 |
| Disposition: REPAIRED | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 280 |
| Disposition: UNRECOVERABLE | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.8095 ± 0.0000 | 35 |

Field accuracy is correctness among attempted target fields. Field coverage is the attempted target-field count divided by the number of ground-truth target fields. A removed record is not credited with field repair. Missing records can have high partial-field accuracy and still remain `UNRECOVERABLE`.

## Calibration and ablation

The calibration curve and one-factor ablation below are reused from the Phase 2 artifacts; no holdout observations enter either artifact.

| Calibration metric | Raw | Calibrated |
|---|---:|---:|
| Detection Brier | 0.000099 | 0.000000 |
| Detection ECE | 0.002351 | 0.000093 |

### Detection reliability bins (calibrated)

| Count | Mean predicted | Observed frequency |
|---:|---:|---:|
| 2274 | 0.000099 | 0.000000 |
| 168 | 0.999997 | 1.000000 |

### Detector ablation

| Configuration | Precision | Recall | F1 | Type accuracy |
|---|---:|---:|---:|---:|
| all_detectors | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| without_duplicate_detection | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| without_integrity_hash | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| without_control_ledger | 1.0000 | 0.9167 | 0.9565 | 0.9091 |
| without_relational_analysis | 1.0000 | 1.0000 | 1.0000 | 0.7143 |
| without_route_validation | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| without_temporal_analysis | 1.0000 | 1.0000 | 1.0000 | 0.9167 |
| without_movement_history | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| without_customs_witness | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| without_schema_novelty | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Isolated holdout attacks

Recall: 1.0000 (3 TP, 0 FN); precision: 1.0000 (0 FP). Three deterministic synthetic families held outside batch injection and calibration. This is a narrow open-set test, not generalization evidence for arbitrary attacks.

| Holdout family | Detected | Classified unknown | Nearest known type | Similarity | Novelty | Reconstruction status |
|---|---:|---:|---|---:|---:|---|
| LEDGER_FORK | True | True | DELETED | 0.0000 | 1.0000 | UNRECOVERABLE |
| WEIGHT_WITNESS_DRIFT | True | True | SLOW_DRIFT | 0.5000 | 0.5000 | UNRECOVERABLE |
| UNREGISTERED_EXTENSION_FIELD | True | True | DELETED | 0.0000 | 1.0000 | UNRECOVERABLE |
A similarity of 0.0000 means no evidence-signature overlap; the displayed nearest category is only a deterministic zero-distance tie-break, not a semantic attribution.

## What we do poorly

- The known-attack evaluation is a closed, synthetic generator suite; repeated perfect detection does not establish real-world accuracy or resilience against adaptive tampering.
- Holdout coverage is only three attack instances across three synthetic families. The measured precision and recall are too small-sample to support a general open-set performance claim.
- A deleted record cannot be fully restored when independent sources do not attest every field; the system deliberately leaves such rows `UNRECOVERABLE` and reports partial coverage.
- Novel schema evidence can yield a low calibrated probability even when rule-based handling raises an unknown anomaly; probability estimates and alert policy are not interchangeable.
- Synthetic witnesses are generated with the manifest and are not authenticated external carrier, customs, or port systems.

Reproduce this report with `python -m doom.evaluation` (or `make eval` once the project targets are installed).
