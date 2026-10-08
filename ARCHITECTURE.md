# Architecture

```text
Seeded generator ──> manifest + synthetic operational witnesses
      │
      ├── isolated corruption module ──> observed manifest
      │              └── oracle.sqlite3 (labels/originals; evaluator only)
      └── control ledger (expected IDs/sequences/hashes; no source field values)
                                             │
                                             v
                            batch detector <─ witnesses
                           evidence + counterfactuals
                                             │
                                             v
                       witness-backed reconstruction
                                │        │
                                v        v
                  evidence.sqlite3   reconstructed manifest
                          ├── FastAPI /api/*
                          ├── WebSocket /api/stream
                          └── React + TypeScript console

Fixed training seeds ──> calibration artifact
Isolated holdout generator ──> holdout evaluator only
Known/holdout evaluators ──> reports/metrics.json ──> reports/EVAL.md
Simulated live feed ──> bounded event history + incremental detector
```

## Components

- `doom.schema`: canonical manifest/witness schema, route geometry, canonical
  payload hash, and ledger hashes.
- `doom.generator`: fixed-seed manifest, movement-event, control-ledger, and
  cross-table witness generation.
- `doom.corruption`: seeded batch attack injection and oracle-label generation;
  it is not imported by detector or calibration code.
- `doom.oracle`: evaluator-only store for attack labels and original values.
- `doom.detectors`: duplicate, ledger, relational, route, temporal, witness,
  and schema-novelty evidence. It imports neither corruption, oracle, nor
  evaluation modules.
- `doom.reconstruction`: explicit dispositions, evidence-backed field recovery,
  and before/after audit trails.
- `doom.metrics`: evaluator-only comparison of findings and reconstruction
  decisions with isolated synthetic truth.
- `doom.calibration`: seed-separated logistic calibration and ablation
  measurements; holdout attack data is excluded.
- `doom.holdout_eval` and `holdout_attacks`: isolated unknown-family
  generation/evaluation path; the known evaluation reads its saved result and
  does not generate holdout examples.
- `doom.store`: local SQLite operator evidence database with no ground-truth
  table.
- `doom.streaming`: in-process event ingestion, bounded recent-event history,
  incremental detector call, and WebSocket fan-out.
- `doom.api`: local FastAPI read API, incident detail, and WebSocket endpoint.
- `frontend`: Vite/React/TypeScript operator console with API-backed overview,
  filterable/sortable incident register, case forensics, and live unknown-event
  views.
- `doom.demo`: generate → corrupt → detect → reconstruct → evaluate → persist →
  serve dashboard and simulated stream.
- `doom.e2e`: starts a temporary local API and exercises its real HTTP routes
  against a freshly built dashboard.

## Trust boundaries

The detector accepts the observed frame, expected-ID/sequence/hash ledger, and
synthetic witness tables. It receives neither the clean manifest nor attack
labels. Oracle truth is stored separately and is consumed only by evaluation.
The operator database has no ground-truth table. Structural tests reject
detector imports of corruption, oracle, and metrics modules and ensure holdout
families remain isolated from training and tuning.

The canonical payload hash covers non-ledger fields. The entry hash commits the
sequence, previous hash, and payload hash. The generated control ledger is a
synthetic independent anchor. Hashes are unkeyed and are not signatures; a real
deployment needs separately protected anchors and authenticated source systems.

## Local execution

The API and demo bind only to loopback. The Vite development server proxies API
and WebSocket requests locally. SQLite, manifests, and reports remain on the
machine; there are no cloud services or external runtime dependencies.
