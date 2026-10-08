# Data dictionary

## Manifest record

| Field | Type | Meaning |
|---|---|---|
| `record_id` | string | Unique manifest row identifier. |
| `shipment_id` | string | Shipment identity; duplicates are checked across rows. |
| `owner` | string | Declared shipment owner. |
| `container_id` | string | Container identifier. |
| `container_owner` | string | Registered owner associated with the container. |
| `origin` | string | Planned first port code. |
| `destination` | string | Planned final port code. |
| `planned_route` | string | Ordered, pipe-delimited port codes. |
| `route_distance_nm` | number | Great-circle waypoint distance, nautical miles. |
| `speed_class` | enum | Synthetic vessel speed class. |
| `quantity` | integer | Synthetic declared unit count. |
| `unit_price_usd` | number | Declared unit price, USD. |
| `departure_ts` | ISO-8601 string | Planned departure time in UTC. |
| `arrival_ts` | ISO-8601 string | Planned arrival time in UTC. |
| `declared_value_usd` | number | Synthetic declared cargo value, USD. |
| `weight_kg` | number | Synthetic cargo weight, kilograms. |
| `status` | string | Synthetic manifest status. |
| `current_location` | string | Observed location in shipment history. |
| `event_ts` | ISO-8601 string | Observed event time, UTC. |
| `ledger_sequence` | integer | Position in the manifest integrity ledger. |
| `previous_hash` | hex string | Previous chained entry hash, or genesis marker. |
| `payload_hash` | hex string | SHA-256 digest of canonical record fields excluding ledger fields. |
| `ledger_hash` | hex string | SHA-256 over sequence, previous hash, and payload hash. |

The streaming-only `policy_epoch` and `routing_signature` extension fields are
not part of the registered batch manifest schema.

## Batch and report artifacts

| File | Contents | Trust boundary |
|---|---|---|
| `clean_manifest.csv` | Seeded generated reference manifest. | Evaluation/setup only; never passed to detectors. |
| `corrupted_manifest.csv` | Manifest after seeded batch attack injection. | Detector input. |
| `control_ledger.csv` | Expected IDs, sequences, payload digests, and chained hashes. | Detector input; no expected source field values or attack labels. |
| `witnesses/*.csv` | Synthetic owner/container registry, vessel schedule, movement, port, and customs records. | Detector/reconstruction witnesses; not authenticated external evidence. |
| `oracle/attack_truth.sqlite3` | Attack labels and original values for evaluation. | Evaluator only; never detector/API/UI input. |
| `../reports/calibration.json` | Seed-separated logistic calibration model and reliability/type measurements. | Synthetic training/evaluation data; not holdout data. |
| `../reports/ablation.json` | One-factor detector ablation measurements. | Synthetic diagnostic; not a real-world benchmark. |
| `../reports/metrics.json` | Multi-seed known, isolated holdout, calibration, ablation, streaming performance, and regression-target measurements. | Machine-readable evaluation source of truth. |
| `../reports/EVAL.md` | Human-readable rendering of the measured evaluation report. | Generated from evaluation artifacts. |
| `demo-run.json` | Latest one-run metrics snapshot. | Synthetic local demonstration output. |
| `../reports/demo-offline-run.json` | Recorded metrics and live unknown event used by offline replay. | Synthetic demonstration fixture; not used for detector training. |
| `doom.sqlite3` | Observed/reconstructed rows, incidents, decisions, stream events, and metrics. | Operator store; contains no ground truth. |

## Incident

An incident contains `record_id`, `tampering_type`, `risk_score`, confidence,
detection probability, type hypotheses, detector evidence, detector names,
related records, counterfactual, and whether the source record is missing.
Evidence items identify the detector, related records, field, expected and
observed values, score contribution, evidence code, and explanation.

Known batch labels are enumerated in [ATTACKS.md](./ATTACKS.md). Open-set
findings retain `UNKNOWN ANOMALY` and include invariant violations,
nearest-known evidence-signature similarity, and novelty score. A zero-overlap
nearest category is a deterministic tie-break, not a semantic attribution.

## Live event and reconstruction

Each WebSocket event includes its sequence, observed record, optional incident,
and a live reconstruction decision. A repeated record ID with changed fields
within the retained window is an `UNKNOWN ANOMALY`; if the first observed event
passed available checks, changed fields are provisionally restored from that
snapshot. The explanation marks that basis as untrusted external evidence.
Other anomalies without an independent live witness remain `UNRECOVERABLE`.
Event history, recent events, client queues, and first-observation snapshots
have explicit finite retention limits, including a capped concurrent WebSocket
client count.

## Reconstruction decision

Each decision includes the record identifier, disposition, method, relied-on
evidence, confidence, field-level before/after diff, explanation, explicit
changes, and known tampering type where applicable. A deleted record can have
an `UNRECOVERABLE` decision with a partial recovery candidate, but no complete
payload is added to the reconstructed manifest without independent evidence.

## Evaluation

`reports/metrics.json` is the numeric source of truth for aggregate and
per-attack precision/recall/F1, confusion counts, reconstruction status/field
accuracy and coverage, calibration, ablations, isolated holdout measurements,
stream latency/throughput, and regression floors. Stream performance measures
are synthetic single-host observations, not production capacity estimates.
