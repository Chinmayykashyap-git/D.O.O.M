"""One-command local demonstration: generate, evaluate, stream, and serve."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from doom.api import create_app
from doom.detectors import ManifestDetector
from doom.generator import generate_batch, write_batch
from doom.metrics import evaluate_detection
from doom.reconstruction import reconstruct_manifest
from doom.store import EvidenceStore
from doom.streaming import StreamingService


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DOOM_DATA_DIR", str(ROOT / "data"))).resolve()


def prepare_demo(count: int = 2400) -> dict:
    batch = generate_batch(count=count)
    write_batch(batch, DATA_DIR)
    detector = ManifestDetector()
    incidents = detector.detect(
        batch.corrupted,
        expected_record_ids=batch.expected_record_ids,
    )
    repaired, decisions = reconstruct_manifest(batch.corrupted, incidents)
    metrics = evaluate_detection(batch.hidden_injection_log, incidents)
    EvidenceStore(DATA_DIR / "doom.sqlite3").replace_batch(
        batch.corrupted, repaired, incidents, decisions, metrics
    )
    summary = {
        **metrics,
        "generated_records": len(batch.clean),
        "corrupted_records": len(batch.corrupted),
        "reconstructed_rows": len(repaired),
        "reconstruction_decisions": len(decisions),
        "incident_types": dict(sorted({
            kind: sum(item["tampering_type"] == kind for item in incidents)
            for kind in {item["tampering_type"] for item in incidents}
        }.items())),
    }
    (DATA_DIR / "evaluation.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


async def exercise_stream() -> dict:
    store = EvidenceStore(DATA_DIR / "doom.sqlite3")
    stream = StreamingService(store)
    row = generate_batch(count=10).clean.iloc[0].to_dict()
    row["record_id"] = "LIVE-UNKNOWN-0001"
    row["policy_epoch"] = "OMEGA-7"
    row["routing_signature"] = "UNSEEN-FUTURE-FORMAT"
    event = await stream.publish(row)
    return event


def serve() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "dist" / "index.html").exists():
        completed = subprocess.run(
            ["npm.cmd" if sys.platform == "win32" else "npm", "run", "build"],
            cwd=frontend,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError("Frontend build failed; run npm install in frontend and retry.")

    app = create_app(DATA_DIR / "doom.sqlite3", start_stream=True)
    host = os.environ.get("DOOM_API_HOST", "127.0.0.1")
    port = int(os.environ.get("DOOM_API_PORT", "8000"))
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    if not server.started:
        raise RuntimeError(f"D.O.O.M. API failed to start on http://{host}:{port}")

    app_url = f"http://{host}:{port}"
    print(f"\n  D.O.O.M. command console: {app_url}")
    print("  Local API:               http://127.0.0.1:8000/docs")
    print("  Live unknown attack:     injected after the third simulated stream event")
    print("  Press Ctrl+C to end the demonstration.\n")
    webbrowser.open(app_url)
    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the D.O.O.M. local forensic demo.")
    parser.add_argument(
        "--records", type=int,
        default=int(os.environ.get("DOOM_RECORD_COUNT", "2400")),
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Generate, evaluate, and exercise streaming without launching the dashboard.",
    )
    args = parser.parse_args()
    if args.records < 30:
        parser.error("--records must be at least 30 for meaningful anomaly detection.")
    summary = prepare_demo(args.records)
    print("D.O.O.M. / FORENSIC RUN")
    print(json.dumps(summary, indent=2))
    if args.no_server:
        import asyncio
        event = asyncio.run(exercise_stream())
        print("\nLIVE UNKNOWN ATTACK")
        print(json.dumps({
            "record_id": event["record_id"],
            "status": event["status"],
            "tampering_type": (event["incident"] or {}).get("tampering_type"),
            "evidence": (event["incident"] or {}).get("evidence"),
        }, indent=2))
    else:
        serve()


if __name__ == "__main__":
    main()
