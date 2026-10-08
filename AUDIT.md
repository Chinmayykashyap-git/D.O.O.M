# Phase 0 — Honest audit

Audit date: 2026-10-09. The workspace originally contained a usable first implementation but no Git repository or prior commits. A local Git repository was initialized for phase checkpoints.

## Implemented versus claimed

| Module | Observed implementation | Gap to request |
|---|---|---|
| Generation / injection — [`doom/generator.py`](./doom/generator.py) | Fixed-seed pandas generator, 10 ports, six owners, six routes, deterministic attack labels and CSV output. | IDs encode generation order; attacks are heavily class-patterned; duplicate/fabrication IDs and owner text are detectable; value tampering is extreme; no witness tables or events. |
| Detection — [`doom/detectors.py`](./doom/detectors.py) | Duplicate ID, hard-coded owner, route-membership, temporal, schema, and one-feature Isolation Forest checks. | Missing hash-chain/graph/cross-table checks; IF is combined with a value fence; scores are hand-coded, not probabilities; attack label picks maximum heuristic; no counterfactuals or standardized evidence. |
| Reconstruction — [`doom/reconstruction.py`](./doom/reconstruction.py) | Removes duplicate extras and obvious fabricated rows; repairs owner from container owner and invalid location to route origin; explains decisions. | No hash/events/constraints; non-independent witnesses; removal lacks a retained-record justification object; sparse field-level accuracy. |
| Evaluation — [`doom/metrics.py`](./doom/metrics.py), [`doom/demo.py`](./doom/demo.py) | Seed 1907 evaluator compares record IDs/type and computes precision/recall/F1/type accuracy. | Metrics are only one seed in `data/evaluation.json`; no multi-seed stats, per-class confusion, calibration, reconstruction metrics, ablation, holdout, or stream latency. |
| Streaming — [`doom/streaming.py`](./doom/streaming.py) | WebSocket fan-out, SQLite event log, per-record call into batch detector, unknown schema event on third generated event. | No bounded detector state, dedupe/out-of-order/late semantics, timing/throughput metrics, or meaningful live reconstruction. |
| API/store — [`doom/api.py`](./doom/api.py), [`doom/store.py`](./doom/store.py) | Local FastAPI, SQLite evidence tables, incident details, record and reconstructed manifest endpoints. | Hidden log file was written beside operator data; no custody API or chain-break view. |
| UI — [`frontend/src/App.tsx`](./frontend/src/App.tsx), [`frontend/src/styles.css`](./frontend/src/styles.css) | Premium dark-green/iron/brass console, ten navigation modules, API-backed overview, incident drawer, route schematic and websocket events. | Broad shallow module set; no exact-vs-expected evidence rows, counterfactual, custody ledger, editable tamper flow, keyboard-specific workflow, frontend tests. |
| Tests/docs — [`tests/test_forensics.py`](./tests/test_forensics.py), project docs | Six pytest tests covering deterministic generation, seven attacks, reconstruction, one synthetic evaluation, schema stream finding, and API path. Vite TS build passes. | No measured source coverage (tool missing), regression thresholds, frontend test, holdout/no-leak isolation, E2E interaction, type/lint gates. |

## Baseline measured metrics

The standard seeded 2,400-record run was rerun through `python -m doom.demo --no-server` before phase 1 changes. Its attack fraction is 7%; rounding and balancing across seven classes yields **24 examples/class (168 total)**.

| Seed | Injected | Detected TP | FP | FN | Precision | Recall | F1 | Type accuracy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1907 | 168 | 168 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 2024 | 168 | 168 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 17 | 168 | 168 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

These are **invalid as evidence of robust detection quality** because generated attack artifacts leak labels. All quantities are synthetic, not real-world security performance. The older seven-example test had produced another apparently perfect score and materially underrepresented the standard run.

## Generator leakage check

A 250-tree `RandomForestClassifier` was trained and stratified 70/30 split on clean rows vs. injected/corrupted rows using only surface features: row position, identifier length/prefix/copy suffix, owner/container string length, timestamp minute/hour/second/serialized lengths, value/weight string lengths, route length, and location length.

| Accuracy | ROC AUC | Interpretation |
|---:|---:|---|
| 0.9772 | 0.8663 | Not near chance. Majority-class accuracy is already 0.9701, but AUC shows a clear surface signal. |

Top importances: row order 0.3988, arrival hour 0.1058, departure hour 0.1015, event hour 0.1004, record ID length 0.0833, owner length 0.0648, value string length 0.0390, copy suffix 0.0359.

Leak sources confirmed by code: duplicate `-COPY` suffix, `MF-FAB-...` fabricated IDs, unregistered verbose owner/container strings, 30x value edits, appended extra rows, simple sequential IDs correlated with time/route, and attack families ordered in injection batches. The sampled row-order feature was especially informative.

## Phase 1 follow-up

The generator and detector were replaced with seeded manifests whose identifiers and rows are randomized, twelve attack families use plausible-format identifiers, and synthetic owner/container/vessel/customs/port/movement witnesses are generated separately. Detection uses an ID/sequence/hash control ledger and never receives clean rows or attack labels. Oracle labels and original fields are persisted in `data/oracle/attack_truth.sqlite3`, separate from the operator evidence database.

The surface-only classifier gate was rerun on five deterministic balanced splits using the suite's RF120 parameters: mean accuracy **0.5064**, mean ROC AUC **0.4837**. Per-seed accuracy: 0.3617, 0.4894, 0.5106, 0.6170, 0.5532. Per-seed AUC: 0.2717, 0.5000, 0.5127, 0.6377, 0.4964. This gate checks a bounded list of generated surface features; it does not prove the absence of every possible data leak.

The current seed-1907, 2,400-row synthetic run reports 168 injected attacks, 168 TP, 0 FP, 0 FN, 1.0 type accuracy, 168/168 status decisions correct, and 210/210 modified fields restored. These results are not independent external validation and should not be interpreted as production performance. The full current pytest result is 9 passed. See [`reports/metrics.json`](./reports/metrics.json).

## Determinism check

Three independent `generate_batch(300, 88)` runs produced identical SHA-256 digests for the corrupted CSV (`a2680408f69d0e68fcd38c0e0798842a5202ed7ed0050f1963b4bb8622b4f557`) and sorted-JSON injection log (`4df6483910aeb4840b9843c70e068e0beca0d20869ae983cfbdf6d0f143f4a53`). This establishes deterministic serialization for that generator call, not an end-to-end export/import byte contract.

## Test coverage and untested critical paths

Baseline: **6 pytest tests passed**. Vite `npm run build` passed. Python source coverage was not measured because `coverage` was not installed in the environment. Critical untested paths include hash verification, event reconciliation, independent witnesses, calibration holdout discipline, holdout attack isolation, per-attack precision/recall, reconstruction field accuracy, ablation contributions, streaming late/out-of-order processing and latency, frontend accessibility, and tamper interaction.

## Prioritized phase gaps

1. Remove label side channels; add normalized random-format identifiers, balanced attack strata, movement history, cryptographic sequence chain, value derivation and cross-table witnesses.
2. Replace heuristic-only fusion with separately reported class probabilities and calibrated evidence fusion; standardize evidence and counterfactual output; measure ablations.
3. Add isolated, never-tuned holdout families and unknown novelty explanation.
4. Record reconstruction method/witness/confidence/before-after per field and evaluate accuracy by class/status.
5. Add bounded incremental ordering/late handling and measured latency/throughput.
6. Make repeatable multi-seed evaluation, regression targets, per-class/confusion/calibration/ablation reports.
7. Consolidate UI and implement chain of custody and real-API interactive tamper workflow.
8. Add `make eval`, `make verify`, reliable demo/fast-offline modes, documented limitations and timed demo script.
