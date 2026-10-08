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
| `departure_ts` | ISO-8601 string | Planned departure time in UTC. |
| `arrival_ts` | ISO-8601 string | Planned arrival time in UTC. |
| `declared_value_usd` | number | Synthetic declared cargo value, USD. |
| `weight_kg` | number | Synthetic cargo weight, kilograms. |
| `status` | string | Synthetic manifest status. |
| `current_location` | string | Observed port code in shipment history. |
| `event_ts` | ISO-8601 string | Observed event time, UTC. |

The `policy_epoch` and `routing_signature` fields appear only in the unknown-schema live demonstration; they are intentionally outside the batch manifest schema.

## Batch artifacts

| File | Contents | Trust boundary |
|---|---|---|
| `clean_manifest.csv` | Deterministic generated clean reference. | Evaluation/setup only; never passed to detectors. |
| `corrupted_manifest.csv` | Manifest after seeded attack injection. | Detector input. |
| `control_totals.json` | Expected record IDs, independent of attack labels. | Detector input for deletion checks. |
| `hidden_injection_log.json` | Injected record IDs, classes, and pre-tamper source rows. | Evaluator only; never detector, API, or UI input. |
| `evaluation.json` | Computed record-level detection metrics and run summary. | Synthetic evaluation result. |
| `doom.sqlite3` | Observed records, materialized reconstructed manifest, incidents, decisions, stream events, and summary metrics. | Local evidence store; no hidden injection log. |

## Incident

`record_id`, `tampering_type`, `risk_score` (0–100), `confidence` (0–1), `evidence` (code/detail/severity objects), `detectors` (names), `related_records`, and `record_missing`.

Batch labels include `MODIFIED`, `DELETED`, `DUPLICATE`, `FABRICATED`, `TIMESTAMP_MANIPULATION`, `IMPOSSIBLE_MOVEMENT`, and `RELATIONAL_INCONSISTENCY`. Open-set schema findings use `UNKNOWN_ANOMALY`.

## Reconstruction decision

`record_id`, `status` (`ORIGINAL`, `REPAIRED`, `REMOVED`, or `UNRECOVERABLE`), human-readable `explanation`, explicit `changes` (`field`, `from`, `to`), and `tampering_type` when applicable. A deleted record has a decision but no source payload in the reconstructed dataframe.

## Evaluation

Record-level true/false positives and negatives, precision, recall, F1, and detected-record type accuracy are computed against the isolated injection log for a synthetic run. They are not validated production performance estimates.
