# D.O.O.M.

**Detection, Observation & Operational Manifest Reconstruction**  
**LATVERIAN** — *When the manifest cannot be trusted, reconstruct the truth.*

D.O.O.M. is a local-first cargo-manifest forensic demonstrator. It generates a repeatable maritime manifest, introduces seven batch tampering scenarios, detects suspicious records with explainable checks, records explicit reconstruction decisions, and serves a React/TypeScript operations console and live event stream.

> The generated records and scores are synthetic hackathon-demo evidence. They are not real shipment records or a production security benchmark.

## Start here (Windows PowerShell)

Prerequisites: Python 3.11+, Node.js 20+, and npm.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Set-Location frontend
npm install
Set-Location ..
python -m doom.demo
```

The demo creates `data/`, prints the measured batch evaluation, builds the frontend if needed, starts the local dashboard at <http://127.0.0.1:8000>, and injects a previously unseen schema attack into its simulated live stream. Stop it with **Ctrl+C**.

Run the generator, detectors, reconstruction, evaluator, and one live unknown-attack event without starting the servers:

```powershell
python -m doom.demo --no-server
```

Select a batch size (at least 30 records):

```powershell
python -m doom.demo --records 5000 --no-server
```

## Development

Run the API after generating a batch:

```powershell
python -m doom.demo --no-server
python -m doom.server
```

In another PowerShell terminal, run the Vite UI with API/WebSocket proxy:

```powershell
Set-Location frontend
npm run dev
```

Open <http://127.0.0.1:5173>. API documentation is at <http://127.0.0.1:8000/docs>.

## Verification

```powershell
python -m pytest
Set-Location frontend
npm run build
```

## Forensic trust boundary

The batch detector receives only a corrupted manifest and an independently maintained expected-record-ID control ledger. It does **not** receive the clean manifest or hidden injection log. The latter is created separately and consumed only by `doom.metrics.evaluate_detection` for this synthetic run's evaluation. It is neither loaded into the evidence database nor exposed by the API or UI. Missing IDs can be identified through the control ledger; absent payloads are marked `UNRECOVERABLE`, never fabricated.

Detectors combine duplicate analysis, registered-owner/container consistency, route membership, time ordering, open-set schema novelty, and an Isolation Forest over numeric shipping behavior. Finding confidence, risk, evidence codes, detector provenance, and related-record links accompany every incident. Reconstruction emits a materialized manifest output and one explicit decision for every present row and every ledger-confirmed missing ID: `ORIGINAL`, `REPAIRED`, `REMOVED`, or `UNRECOVERABLE`. A repair includes the changed field, prior value, recovered value, and evidence-based explanation.

## Product modules

The console includes Command overview, Manifest integrity, Active incidents, Record forensics, Reconstruction, Attack timeline, Route intelligence, Live event stream, Unknown anomaly watch, and Evaluation metrics. Select a case to inspect its evidence, detectors, confidence, record fields, reconstruction decision, related records, and timeline.

## Generated artifacts

The ignored local `data/` directory contains the clean reference manifest, corrupted input, independent control ledger, evaluator-only hidden injection log, measured evaluation summary, and SQLite evidence database. Keep the injection log out of detector inputs and production systems. See [DATA_DICTIONARY.md](./DATA_DICTIONARY.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [APPROACH_DOSSIER.md](./APPROACH_DOSSIER.md), and [DEMO.md](./DEMO.md).

## Known limitations

- Synthetically generated data and injected attack mechanisms do not establish effectiveness on real-world manifests.
- Record deletion detection depends on the integrity of the independent expected-ID ledger. The missing record's contents cannot be recovered without a second trusted copy.
- Some suspicious values cannot be confidently reconstructed from the remaining evidence and are explicitly quarantined as `UNRECOVERABLE`.
- Route validation uses a small, static demonstration port registry; it is not a live AIS, customs, or carrier integration.
- Streaming is a local simulated feed with an in-memory WebSocket fan-out and SQLite event history. It is not a high-availability ingestion service.
- Authentication, multi-user authorization, production secrets management, and operational hardening are outside this local demo's scope.
