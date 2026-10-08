# D.O.O.M.

**Detection, Observation & Operational Manifest Reconstruction**  
**LATVERIAN** — *When the manifest cannot be trusted, reconstruct the truth.*

D.O.O.M. is a local-first cargo-manifest forensics demonstrator. It generates a
seeded maritime manifest and synthetic operational witnesses, injects batch
tampering, detects and explains anomalies, records explicit reconstruction
decisions, and serves a React/TypeScript operations console with a simulated
live stream.

> All data, witnesses, and measured results are synthetic. They do not establish
> detection quality on real shipping records.

## Requirements

- Python 3.11 or newer
- Node.js and npm
- Windows PowerShell for the `make.ps1` commands, or GNU Make for the Makefile

## Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix frontend install
python -m doom.demo
```

The demo deterministically regenerates its batch artifacts, evaluates them,
persists evidence locally, starts the API on `127.0.0.1:8000`, opens the
dashboard, and produces a streaming-only unknown-schema alert. Stop the server
with **Ctrl+C**. A busy port or missing runtime dependency is reported as an
error; the app does not silently choose another port.

## Verify and evaluate

On Windows PowerShell, use the included target runner:

```powershell
.\make.ps1 verify
.\make.ps1 eval
.\make.ps1 e2e
```

With GNU Make installed, the equivalent targets are:

```sh
make verify
make eval
make e2e
```

`verify` runs the multi-seed known and isolated holdout evaluation, frontend
TypeScript/production build, Ruff, mypy, offline demo, full pytest suite, live
HTTP E2E, and explicit leakage/isolation/metric regression checks. The
authoritative measured metrics are in [`reports/metrics.json`](./reports/metrics.json)
and the rendered tables and scope notes are in [`reports/EVAL.md`](./reports/EVAL.md).

## Offline fallback

Generate and save a real seeded run and its live unknown event:

```powershell
python -m doom.demo --no-server
```

Replay the saved report without starting the API or UI:

```powershell
.\make.ps1 demo-offline
```

The equivalent module command is `python -m doom.offline_demo`. To change the
batch size or seed for a fresh local run:

```powershell
python -m doom.demo --records 5000 --seed 1907 --no-server
```

## Development

Start the API after generating the batch:

```powershell
python -m doom.server
```

In another terminal, start the Vite development server:

```powershell
npm --prefix frontend run dev
```

The dashboard is at <http://127.0.0.1:5173>; API documentation is at
<http://127.0.0.1:8000/docs>.

## Forensic trust boundary

The batch detector receives only the observed manifest, an independently
generated ID/sequence/hash control ledger, and synthetic operational witnesses.
It never receives the clean manifest or hidden injection log. Attack labels and
original field values are held in a separate evaluator-only SQLite database;
the operator evidence database and API contain no oracle table or endpoint.
Structural tests enforce detector import isolation and holdout separation.

Incidents retain detector evidence, expected-versus-observed values,
counterfactuals, related records, and reconstruction explanations. Each
present or ledger-expected record receives an explicit `ORIGINAL`, `REPAIRED`,
`REMOVED`, or `UNRECOVERABLE` disposition. A partial recovery does not become a
complete repair when independent evidence cannot establish every required
field.

## Project documentation

- [Architecture](./ARCHITECTURE.md)
- [Data dictionary](./DATA_DICTIONARY.md)
- [Approach dossier](./APPROACH_DOSSIER.md)
- [Demo runbook](./DEMO.md)
- [Three-minute demo script](./DEMO_SCRIPT.md)
- [Limitations](./LIMITATIONS.md)
- [Attack taxonomy](./ATTACKS.md)
- [Measured evaluation](./reports/EVAL.md)

Generated local manifests, witness tables, and SQLite databases live in the
ignored `data/` directory. Tracked evaluation reports are reproducible outputs;
do not put the oracle database into detector inputs, operational deployments,
or API responses.
