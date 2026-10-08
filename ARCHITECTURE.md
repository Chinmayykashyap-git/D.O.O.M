# Architecture

```text
Seeded generator ──> manifest + owner/container/vessel/port/customs witnesses
      │
      ├── isolated corruption module ──> corrupted manifest
      │              └── oracle.sqlite3 (labels/originals; evaluator only)
      └── control ledger (IDs/sequences/hashes; no expected field values)
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

OracleStore ──> evaluator only ──> reports/metrics.json
Simulated live feed ──> incremental detector ──> event ledger / WebSocket
```

## Components

- `doom.schema`: canonical manifest/witness schema, route geometry, canonical SHA-256 payload and ledger hashes.
- `doom.generator`: fixed-seed manifest, movement-event, and cross-table witness generation.
- `doom.corruption`: seeded batch attack injection and oracle-label generation; never imported by the detector.
- `doom.oracle`: evaluator-only, separate SQLite store for attack labels and original fields.
- `doom.detectors`: hash/control-ledger, duplicate, relational, route, time, event, customs, and open-schema evidence. It imports neither corruption, oracle, nor evaluation code.
- `doom.reconstruction`: explicit witness-backed statuses, reconstructed manifest, and field audit trail.
- `doom.metrics`: evaluator-only known-attack and reconstruction comparisons.
- `doom.store`: standard-library SQLite operator evidence database; no ground-truth table.
- `doom.streaming`: bounded in-process event fan-out and unknown-schema event simulation.
- `doom.api`: local FastAPI read API, incident evidence detail, and WebSocket endpoint.
- `frontend`: Vite/React/TypeScript local console.
- `doom.demo`: generate → corrupt → detect → reconstruct → evaluate → persist → build/start dashboard.

## Trust boundaries

The detector accepts the corrupted frame, an ID/sequence/hash control ledger, and synthetic witness tables. It receives neither the clean manifest nor attack labels. Oracle truth is stored in a separate SQLite database and passed only to `doom.metrics`. The operator evidence database has no ground-truth table. A structural test rejects detector imports of `doom.corruption`, `doom.oracle`, and `doom.metrics`.

The canonical manifest payload hash covers all non-ledger fields. The entry hash commits sequence, previous hash, and payload hash. The generated control ledger provides the (synthetic) independent anchor. These hashes are unkeyed and are not signatures; real deployment requires independently protected anchors and authenticated source systems.

## Local execution

The backend binds to loopback on port 8000. Vite binds to loopback on port 5173 and proxies API/WebSocket requests to 8000. SQLite, manifests, and reports are local; there are no cloud services or external runtime dependencies.
