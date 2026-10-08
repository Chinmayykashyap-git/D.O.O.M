# Architecture

```text
Seeded data generator
  ├── clean reference ──────────────────────┐
  ├── corrupted manifest ──┐                ├── evaluator only ──> measured metrics
  ├── expected-ID ledger ──┼─> batch detector
  └── hidden injection log ─────────────────┘
                             │ incidents + evidence
                             v
                      reconstruction
                             │
                             v
                     local SQLite store
                       ├── FastAPI /api/*
                       ├── WebSocket /api/stream
                       └── React + TypeScript console

Simulated live feed ──> per-event detector ──> SQLite + WebSocket clients
                              └── schema novelty (batch-absent attack)
```

## Components

- `doom.generator`: deterministic local synthetic fleet, port, route, and record generation; seeded batch corruption and separate artifact writing.
- `doom.detectors`: evidence-producing rule checks and scikit-learn Isolation Forest. Accepts only records and optional expected record IDs.
- `doom.reconstruction`: explicit, auditable row dispositions; only makes field repairs when corroborating row evidence exists.
- `doom.metrics`: isolated synthetic ground-truth evaluator, outside the detector and persistence interfaces.
- `doom.store`: standard-library SQLite evidence database; serializes records and decisions but no injection log.
- `doom.streaming`: event evaluation, bounded in-process WebSocket fan-out, and unknown-schema event simulation.
- `doom.api`: local FastAPI read API, route metadata, incident evidence detail, and WebSocket endpoint.
- `frontend`: Vite/React/TypeScript local console, same-origin API and WebSocket access.
- `doom.demo`: generate → corrupt → detect → reconstruct → evaluate → persist → build and start the local dashboard.

## Trust boundaries

The detector is structurally passed only a pandas frame and optional ID ledger. The clean manifest and hidden log are held by `GeneratedBatch` at orchestration level but never passed to `ManifestDetector`. The metrics evaluator is the sole code path that accepts the hidden log. SQLite persistence receives corrupted observations, incidents, reconstruction decisions, and summary metrics only. No endpoint or static asset serves the hidden log.

## Local execution

The backend binds to loopback on port 8000. Vite binds to loopback on port 5173 and proxies local API/WebSocket requests to 8000. SQLite, manifests, and reports are written below `data/`. There are no cloud resources or external runtime services.
