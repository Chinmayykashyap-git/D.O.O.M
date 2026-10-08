# Demo runbook

## Prerequisites and install

Use Python 3.11+, Node.js, npm, and Windows PowerShell (or GNU Make on other
platforms).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix frontend install
```

## Full local demo

```powershell
python -m doom.demo
```

The command deterministically regenerates the local manifest, independent
synthetic witnesses, control ledger, oracle fixture, detector findings,
reconstruction decisions, and per-run metrics; it replaces prior batch data
instead of appending duplicate rows. It persists operator evidence, starts the
API/dashboard on loopback, and starts the simulated stream. The third simulated
event introduces an unknown schema extension and should appear as `UNKNOWN
ANOMALY`. Use **Ctrl+C** to stop the server.

To evaluate without launching a server:

```powershell
python -m doom.demo --no-server
```

This writes the current per-run metrics and a recorded live unknown event.
Replay that recording without services:

```powershell
.\make.ps1 demo-offline
```

The replay command fails clearly if the recording is missing, incomplete, or
does not contain the expected unknown event.

## Evaluation and gates

```powershell
.\make.ps1 eval
.\make.ps1 verify
```

The equivalents with GNU Make are `make eval` and `make verify`. Evaluation
writes `reports/metrics.json` and `reports/EVAL.md`. The report separately
labels the known multi-seed results and small holdout smoke result; treat those
synthetic measurements as demo evidence, not field performance.

## Inspection

- Dashboard/API: <http://127.0.0.1:8000>
- API reference: <http://127.0.0.1:8000/docs>
- API health: `GET /api/health`
- Batch metrics: `GET /api/metrics`
- Live event snapshot: `GET /api/stream/events`
- Live event socket: `ws://127.0.0.1:8000/api/stream`

The hidden oracle is evaluator-only. It must never be passed to detectors,
served by the API, or exposed in the UI.
