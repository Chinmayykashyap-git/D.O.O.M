# Data dictionary

## Manifest record

| Field | Type | Meaning |
|---|---|---|
| `record_id` | string | Unique manifest row identifier (`MF-...`). |
| `shipment_id` | string | Shipment identity; duplicates are checked across rows. |
| `owner` | string | Declared shipment owner. |
| `container_id` | string | Container identifier. |
| `container_owner` | string | Registered owner associated with that container. |
| `origin` | string | Planned first port UN/LOCODE. |
| `destination` | string | Planned final port UN/LOCODE. |
| `planned_route` | string | Ordered, pipe-delimited port codes. |
| `route_distance_nm` | number | Great-circle waypoint distance, nautical miles. |
| `speed_class` | enum | Synthetic vessel speed class. |
| `quantity` | integer | Synthetic declared unit count. |
| `unit_price_usd` | number | Declared price per unit, USD. |
| `departure_ts` | ISO-8601 string | Planned departure time in UTC. |
| `arrival_ts` | ISO-8601 string | Planned arrival time in UTC. |
| `declared_value_usd` | number | Synthetic declared cargo value, USD. |
| `weight_kg` | number | Synthetic cargo weight, kilograms. |
| `status` | string | Synthetic manifest status. |
| `current_location` | string | Observed port code in shipment history. |
| `event_ts` | ISO-8601 string | Observed event time, UTC. |
| `ledger_sequence` | integer | Position in the manifest integrity ledger. |
| `previous_hash` | hex string | Previous chained entry hash, or fixed genesis marker. |
| `payload_hash` | hex string | SHA-256 of canonical record fields excluding ledger fields. |
| `ledger_hash` | hex string | SHA-256 over sequence, previous hash, and payload hash. |

The `policy_epoch` and `routing_signature` fields appear only in the unknown-schema live demonstration; they are intentionally outside the batch manifest schema.

## Batch artifacts

| File | Contents | Trust boundary |
|---|---|---|
| `clean_manifest.csv` | Deterministic generated clean reference. | Evaluation/setup only; never passed to detectors. |
| `corrupted_manifest.csv` | Manifest after seeded attack injection. | Detector input. |
| `control_ledger.csv` | Expected IDs, sequence positions, payload digests, and chained hashes. | Detector input; contains neither expected source field values nor attack labels. |
| `witnesses/*.csv` | Owner/container registry, vessel schedule, movement events, port logs, and customs records. | Synthetic detector/reconstruction witnesses, not external authenticated evidence. |
| `oracle/attack_truth.sqlite3` | Attack labels and original values for evaluation. | Evaluator only; separate database, never detector/API/UI input. |
| `../reports/calibration.json` | Seed-separated standardized logistic calibration models and held-out reliability/type metrics. | Trained on fixed synthetic training seeds; labels are used only by offline training/evaluation, never by detector inference. |
| `../reports/ablation.json` | One-factor detector ablation on the fixed synthetic seed. | Descriptive synthetic diagnostic; not a causal or real-world benchmark. |
| `evaluation.json` | Human-readable copy of the computed run metrics. | Synthetic evaluation result. |
| `../reports/metrics.json` | Machine-readable measured evaluation report. | Synthetic evaluation result. |
| `doom.sqlite3` | Observed/reconstructed records, incidents, decisions, stream events, and metrics. | Operator store; contains no ground truth. |

## Incident

`record_id`, `tampering_type`, `risk_score` (0–100), `confidence` (raw strongest-rule score), `detection_probability` (seed-separated calibrated synthetic estimate), `type_probabilities` (raw uncalibrated rule hypotheses), `type_probabilities_calibrated` (held-out-evaluated synthetic model outputs), `type_prediction_calibrated`, standard detector evidence (detector, record IDs, field, expected/observed, score contribution, explanation), detectors, related records, counterfactual, and `record_missing`.

Batch labels: `MODIFIED_VALUE`, `DELETED`, `DUPLICATE_EXACT`, `DUPLICATE_NEAR`, `FABRICATED`, `TIMESTAMP_SHIFT`, `TELEPORTATION`, `PORT_SKIP`, `NEGATIVE_TRANSIT`, `RELATIONAL_ORPHAN`, `VESSEL_MISMATCH`, `SLOW_DRIFT`. Open-set findings use `UNKNOWN ANOMALY`.

## Reconstruction decision

`record_id`, status, reconstruction method, relied-on evidence, confidence, field-level before/after diff, human-readable `why`/explanation, explicit changes, and `tampering_type` when applicable. A deleted record has an `UNRECOVERABLE` decision but no source payload in the reconstructed dataframe.

## Evaluation

Record-level true/false positives and negatives, precision, recall, F1, type confusion, reconstruction status/field accuracy, detector ablation, and held-out synthetic calibration reliability are computed against the isolated injection oracle. They are not validated production performance estimates.
