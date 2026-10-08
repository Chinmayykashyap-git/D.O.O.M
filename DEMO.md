# Demo runbook

## First run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Set-Location frontend
npm install
Set-Location ..
python -m doom.demo
```

The one-command demo:

1. Generates 2,400 reproducible shipping records with fixed seeds.
2. Writes a clean reference, corrupted manifest, expected-ID ledger, and isolated evaluator log.
3. Injects modified, deleted, duplicated, fabricated, timestamp, movement, and relational inconsistencies.
4. Detects anomalies using only the corrupted manifest and expected-ID ledger.
5. Makes an explicit reconstruction decision for every observed/expected ID.
6. Calculates and prints synthetic record-level evaluation metrics.
7. Saves the evidence ledger and evaluation summary under `data/`.
8. Builds the UI when no local build exists, launches the API and dashboard on loopback, and opens the dashboard.
9. Starts a simulated live stream and emits a previously unseen schema-novelty attack on the third event.

The command remains running to serve the console; press **Ctrl+C** to stop. The live WebSocket endpoint is `ws://127.0.0.1:8000/api/stream`.

## Offline pipeline check

```powershell
python -m doom.demo --no-server
```

This runs all generation, batch analysis, evaluation, persistence, and one unknown live attack without starting a web server.

## Targeted investigation

```powershell
python -m doom.demo --records 5000 --no-server
python -m pytest
Set-Location frontend
npm run build
```

Inspect real run metrics in `data/evaluation.json`; the web interface and `/api/metrics` read the same persisted values. The hidden log is solely an evaluation artifact. Never pass it to the detector or expose it as an operational endpoint.
