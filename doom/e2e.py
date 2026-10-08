"""Exercise the packaged UI and API over a real local HTTP socket."""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import uvicorn

from doom.api import create_app
from doom.corruption import inject_attacks
from doom.detectors import ManifestDetector
from doom.generator import generate_dataset, make_control_ledger
from doom.metrics import evaluate_detection
from doom.reconstruction import reconstruct_manifest
from doom.store import EvidenceStore


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _get_json(url: str) -> Any:
    with urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"E2E request failed: GET {url} returned {response.status}")
        return json.loads(response.read().decode("utf-8"))


def run_end_to_end() -> dict[str, Any]:
    clean, witnesses = generate_dataset(180, seed=8181)
    observed, truth = inject_attacks(clean, seed=8182)
    ledger = make_control_ledger(clean)
    incidents = ManifestDetector().detect(
        observed,
        expected_record_ids=clean["record_id"].astype(str).tolist(),
        expected_ledger=ledger,
        witnesses=witnesses,
    )
    reconstructed, decisions = reconstruct_manifest(
        observed, incidents, witnesses, ledger
    )
    metrics = evaluate_detection(
        truth, incidents, decisions, reconstructed.to_dict(orient="records")
    )

    with tempfile.TemporaryDirectory(prefix="doom-e2e-") as temp_dir:
        database = Path(temp_dir) / "evidence.sqlite3"
        EvidenceStore(database).replace_batch(
            observed, reconstructed, incidents, decisions, metrics
        )
        app = create_app(database, start_stream=False)
        port = _free_local_port()
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error",
        ))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("E2E API server did not start on its loopback port.")

            base_url = f"http://127.0.0.1:{port}"
            health = _get_json(f"{base_url}/api/health")
            overview = _get_json(f"{base_url}/api/overview")
            api_incidents = _get_json(f"{base_url}/api/incidents?limit=20")
            api_metrics = _get_json(f"{base_url}/api/metrics")
            with urlopen(base_url, timeout=5) as response:
                html = response.read().decode("utf-8")
                if response.status != 200 or "<html" not in html.lower():
                    raise RuntimeError("E2E dashboard route did not return the built UI.")
            if health.get("status") != "operational":
                raise RuntimeError(f"Unexpected E2E health response: {health}")
            if overview.get("record_count") != len(observed):
                raise RuntimeError("E2E overview did not return the persisted manifest count.")
            if not api_incidents or not api_metrics.get("injected_attacks"):
                raise RuntimeError("E2E API did not return persisted incidents and metrics.")
            return {
                "status": "passed",
                "base_url": base_url,
                "record_count": overview["record_count"],
                "incident_count": overview["incident_count"],
            }
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("E2E API server did not shut down cleanly.")


def main() -> None:
    print(json.dumps(run_end_to_end(), indent=2))


if __name__ == "__main__":
    main()
