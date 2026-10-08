"""One-command local demonstration: generate, evaluate, stream, and serve."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from doom.api import create_app
from doom.calibration import apply_calibration, fit_calibration_study, load_calibrator
from doom.corruption import ATTACK_TYPES, inject_attacks
from doom.detectors import ManifestDetector
from doom.generator import (
    generate_dataset,
    make_control_ledger,
    write_manifest,
    write_witness_tables,
)
from doom.metrics import evaluate_detection
from doom.oracle import OracleStore
from doom.reconstruction import reconstruct_manifest
from doom.store import EvidenceStore
from doom.streaming import StreamingService

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DOOM_DATA_DIR", str(ROOT / "data"))).resolve()
CALIBRATION_PATH = ROOT / "reports" / "calibration.json"


def prepare_demo(count: int = 2400, seed: int = 1907) -> dict:
    clean, witnesses = generate_dataset(count=count, seed=seed)
    corrupted, hidden_truth = inject_attacks(clean, seed=seed + 1)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_manifest(clean, DATA_DIR / "clean_manifest.csv")
    write_manifest(corrupted, DATA_DIR / "corrupted_manifest.csv")
    control_ledger = make_control_ledger(clean)
    control_ledger.to_csv(DATA_DIR / "control_ledger.csv", index=False, lineterminator="\n")
    write_witness_tables(witnesses, DATA_DIR)
    OracleStore(DATA_DIR / "oracle" / "attack_truth.sqlite3").replace(hidden_truth)
    detector = ManifestDetector()
    incidents = detector.detect(
        corrupted,
        expected_record_ids=clean["record_id"].astype(str).tolist(),
        expected_ledger=control_ledger,
        witnesses=witnesses,
    )
    calibrator = load_calibrator(CALIBRATION_PATH)
    if calibrator is None:
        fit_calibration_study(CALIBRATION_PATH)
        calibrator = load_calibrator(CALIBRATION_PATH)
    if calibrator is None:
        raise RuntimeError(f"Calibration artifact was not created at {CALIBRATION_PATH}")
    incidents = apply_calibration(incidents, calibrator)
    repaired, decisions = reconstruct_manifest(
        corrupted, incidents, witnesses, control_ledger
    )
    evaluator_truth = OracleStore(DATA_DIR / "oracle" / "attack_truth.sqlite3").entries()
    metrics = evaluate_detection(
        evaluator_truth, incidents, decisions, repaired.to_dict(orient="records")
    )
    EvidenceStore(DATA_DIR / "doom.sqlite3").replace_batch(
        corrupted, repaired, incidents, decisions, metrics
    )
    summary = {
        **metrics,
        "generated_records": len(clean),
        "corrupted_records": len(corrupted),
        "reconstructed_rows": len(repaired),
        "reconstruction_decisions": len(decisions),
        "incident_types": dict(sorted({
            kind: sum(item["tampering_type"] == kind for item in incidents)
            for kind in {item["tampering_type"] for item in incidents}
        }.items())),
        "attack_types": list(ATTACK_TYPES),
        "calibration": calibrator["study"]["evaluation"],
        "calibration_training_seeds": calibrator["study"]["training_seeds"],
        "calibration_evaluation_seeds": calibrator["study"]["evaluation_seeds"],
    }
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "demo-run.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


async def exercise_stream() -> dict:
    store = EvidenceStore(DATA_DIR / "doom.sqlite3")
    stream = StreamingService(store)
    from doom.generator import generate_clean_manifest
    row = generate_clean_manifest(1, seed=83001).iloc[0].to_dict()
    row["record_id"] = "MF-8300001"
    row["policy_epoch"] = "OMEGA-7"
    row["routing_signature"] = "UNSEEN-FUTURE-FORMAT"
    event = await stream.publish(row)
    return event


def _assert_local_port_available(host: str, port: int) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("D.O.O.M. demo must bind to a loopback host.")
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid API port: {port}")
    address_family = socket.AF_INET6 if host == "::1" else socket.AF_INET
    try:
        with socket.socket(address_family, socket.SOCK_STREAM) as listener:
            listener.bind((host, port))
    except OSError as error:
        raise RuntimeError(
            f"Cannot start D.O.O.M.: {host}:{port} is unavailable (possibly already in use)."
        ) from error


def serve() -> None:
    host = os.environ.get("DOOM_API_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("DOOM_API_PORT", "8000"))
    except ValueError as error:
        raise ValueError("DOOM_API_PORT must be an integer between 1 and 65535.") from error
    _assert_local_port_available(host, port)
    frontend = ROOT / "frontend"
    if not (frontend / "dist" / "index.html").exists():
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        if shutil.which(npm) is None:
            raise RuntimeError("Node.js/npm is required to build the dashboard.")
        completed = subprocess.run(
            [npm, "run", "build"],
            cwd=frontend,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError("Frontend build failed; install frontend dependencies and retry.")

    app = create_app(DATA_DIR / "doom.sqlite3", start_stream=True)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        if not thread.is_alive():
            break
        time.sleep(0.1)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError(f"D.O.O.M. API failed to start on http://{host}:{port}")

    app_url = f"http://{host}:{port}"
    print(f"\n  D.O.O.M. command console: {app_url}")
    print(f"  Local API:               {app_url}/docs")
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
    parser.add_argument("--seed", type=int, default=1907)
    args = parser.parse_args()
    if args.records < 30:
        parser.error("--records must be at least 30 for meaningful anomaly detection.")
    summary = prepare_demo(args.records, args.seed)
    print("D.O.O.M. / FORENSIC RUN")
    print(json.dumps(summary, indent=2))
    if args.no_server:
        import asyncio
        event = asyncio.run(exercise_stream())
        offline_run = {
            "run_seed": args.seed,
            "metrics": summary,
            "live_events": [{
                "record_id": event["record_id"],
                "status": event["status"],
                "incident": event["incident"],
            }],
        }
        (ROOT / "reports" / "demo-offline-run.json").write_text(
            json.dumps(offline_run, indent=2), encoding="utf-8"
        )
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
