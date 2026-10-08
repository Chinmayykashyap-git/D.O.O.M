"""Replay a recorded, seeded local D.O.O.M. demonstration without services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPLAY_PATH = ROOT / "reports" / "demo-offline-run.json"


def replay(path: Path = REPLAY_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Recorded demo replay is missing: {path}")
    run = json.loads(path.read_text(encoding="utf-8"))
    if not run.get("metrics") or not run.get("live_events"):
        raise ValueError(f"Recorded demo replay is incomplete: {path}")
    if not any(
        item.get("status") == "ANOMALY"
        and (item.get("incident") or {}).get("tampering_type") == "UNKNOWN ANOMALY"
        for item in run["live_events"]
    ):
        raise ValueError(f"Recorded demo replay has no unknown-attack event: {path}")
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay the recorded offline D.O.O.M. run.")
    parser.add_argument("--file", type=Path, default=REPLAY_PATH)
    args = parser.parse_args()
    run = replay(args.file)
    summary = run["metrics"]
    print("D.O.O.M. / RECORDED OFFLINE RUN")
    print(json.dumps({
        "run_seed": run["run_seed"],
        "generated_records": summary["generated_records"],
        "injected_attacks": summary["injected_attacks"],
        "precision": summary["precision"],
        "recall": summary["recall"],
        "reconstruction": summary["reconstruction"],
    }, indent=2))
    print("\nRECORDED LIVE EVENTS")
    for event in run["live_events"]:
        incident = event["incident"]
        analysis = (incident or {}).get("unknown_analysis") or {}
        print(json.dumps({
            "record_id": event["record_id"],
            "status": event["status"],
            "tampering_type": (incident or {}).get("tampering_type"),
            "invariant_violations": analysis.get("invariant_violations", []),
            "novelty_score": analysis.get("novelty_score"),
        }, indent=2))


if __name__ == "__main__":
    main()
