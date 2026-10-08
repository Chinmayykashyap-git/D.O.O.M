"""Deterministic synthetic shipping manifests and isolated attack injection."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SEED = 1907
OWNERS = {
    "Aster Maritime": "AST",
    "Crown Meridian": "CRM",
    "Northstar Freight": "NSF",
    "Pelagic Union": "PLU",
    "Ironclad Logistics": "IRN",
    "Sable Oceanic": "SAB",
}
PORTS = {
    "NLRTM": ("Rotterdam", 51.95, 4.14),
    "SGSIN": ("Singapore", 1.26, 103.82),
    "USLAX": ("Los Angeles", 33.74, -118.27),
    "AEJEA": ("Jebel Ali", 24.99, 55.06),
    "CNSHA": ("Shanghai", 31.23, 121.47),
    "DEHAM": ("Hamburg", 53.55, 9.99),
    "BRSSZ": ("Santos", -23.96, -46.33),
    "JPTYO": ("Tokyo", 35.65, 139.84),
    "GBFXT": ("Felixstowe", 51.96, 1.35),
    "INNSA": ("Nhava Sheva", 18.95, 72.95),
}
ROUTES = [
    ("CNSHA", "SGSIN", "AEJEA", "NLRTM"),
    ("SGSIN", "JPTYO", "USLAX"),
    ("BRSSZ", "NLRTM", "GBFXT"),
    ("INNSA", "AEJEA", "DEHAM"),
    ("USLAX", "SGSIN", "CNSHA"),
    ("DEHAM", "NLRTM", "GBFXT"),
]

MANIFEST_COLUMNS = [
    "record_id", "shipment_id", "owner", "container_id", "container_owner",
    "origin", "destination", "planned_route", "departure_ts", "arrival_ts",
    "declared_value_usd", "weight_kg", "status", "current_location",
    "event_ts",
]


@dataclass
class GeneratedBatch:
    clean: pd.DataFrame
    corrupted: pd.DataFrame
    expected_record_ids: list[str]
    hidden_injection_log: list[dict[str, Any]]


def generate_clean_manifest(count: int = 2400, seed: int = SEED) -> pd.DataFrame:
    """Create a repeatable, internally consistent manifest with route histories."""
    if count < 1:
        raise ValueError("count must be at least 1")
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, Any]] = []
    owner_names = list(OWNERS)

    for index in range(count):
        owner = owner_names[index % len(owner_names)]
        route = ROUTES[index % len(ROUTES)]
        origin, destination = route[0], route[-1]
        departure = start + timedelta(hours=index * 3 + rng.randint(0, 2))
        transit_hours = 24 * (len(route) - 1) + rng.randint(12, 60)
        arrival = departure + timedelta(hours=transit_hours)
        container = f"{OWNERS[owner]}U{index:07d}"
        value = round(rng.uniform(12_000, 185_000), 2)
        weight = round(rng.uniform(2_000, 28_000), 1)
        route_position = rng.randrange(len(route))
        event_time = departure + (arrival - departure) * (
            route_position / max(len(route) - 1, 1)
        )
        rows.append({
            "record_id": f"MF-{index + 1:07d}",
            "shipment_id": f"SHP-{index + 1:07d}",
            "owner": owner,
            "container_id": container,
            "container_owner": owner,
            "origin": origin,
            "destination": destination,
            "planned_route": "|".join(route),
            "departure_ts": departure.isoformat(),
            "arrival_ts": arrival.isoformat(),
            "declared_value_usd": value,
            "weight_kg": weight,
            "status": "IN_TRANSIT",
            "current_location": route[route_position],
            "event_ts": event_time.isoformat(),
        })
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def inject_attacks(
    clean: pd.DataFrame, seed: int = SEED + 1, attack_fraction: float = 0.07
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Corrupt a copy and return isolated evaluator-only ground truth."""
    if not 0 < attack_fraction <= 0.25:
        raise ValueError("attack_fraction must be in the interval (0, 0.25]")
    rng = random.Random(seed)
    corrupted = clean.copy(deep=True)
    attacks = [
        "MODIFIED", "DELETED", "DUPLICATE", "FABRICATED",
        "TIMESTAMP_MANIPULATION", "IMPOSSIBLE_MOVEMENT",
        "RELATIONAL_INCONSISTENCY",
    ]
    per_attack = max(1, round(len(clean) * attack_fraction / len(attacks)))
    selected_count = min(len(clean), per_attack * len(attacks))
    indexes = rng.sample(list(clean.index), selected_count)
    attack_sequence = [attack for attack in attacks for _ in range(per_attack)]
    truth: list[dict[str, Any]] = []

    for position, (attack, source_index) in enumerate(zip(attack_sequence, indexes)):
        original = clean.loc[source_index].to_dict()
        row_id = str(original["record_id"])
        target_index = corrupted.index[
            corrupted["record_id"].astype(str) == row_id
        ]
        entry: dict[str, Any] = {
            "record_id": row_id,
            "tampering_type": attack,
            "original": original,
        }
        if attack == "MODIFIED":
            corrupted.loc[target_index[0], "declared_value_usd"] = round(
                float(original["declared_value_usd"]) * 30, 2
            )
        elif attack == "DELETED":
            corrupted = corrupted.drop(index=target_index)
        elif attack == "DUPLICATE":
            duplicate = original.copy()
            duplicate["record_id"] = f"{row_id}-COPY"
            corrupted = pd.concat([corrupted, pd.DataFrame([duplicate])], ignore_index=True)
            entry["record_id"] = duplicate["record_id"]
        elif attack == "FABRICATED":
            fabricated = original.copy()
            fabricated["record_id"] = f"MF-FAB-{seed:05d}-{position:03d}"
            fabricated["shipment_id"] = f"SHP-FAB-{seed:05d}-{position:03d}"
            fabricated["owner"] = "Unregistered Carrier"
            fabricated["container_id"] = f"VOIDU{seed:07d}"
            fabricated["container_owner"] = "Unregistered Carrier"
            corrupted = pd.concat([corrupted, pd.DataFrame([fabricated])], ignore_index=True)
            entry["record_id"] = fabricated["record_id"]
        elif attack == "TIMESTAMP_MANIPULATION":
            corrupted.loc[target_index[0], "arrival_ts"] = (
                datetime.fromisoformat(str(original["departure_ts"]))
                - timedelta(days=45)
            ).isoformat()
        elif attack == "IMPOSSIBLE_MOVEMENT":
            corrupted.loc[target_index[0], "current_location"] = "XXZZZ"
        elif attack == "RELATIONAL_INCONSISTENCY":
            alternatives = [name for name in OWNERS if name != original["owner"]]
            corrupted.loc[target_index[0], "owner"] = alternatives[0]
        truth.append(entry)

    return corrupted.reset_index(drop=True), truth


def generate_batch(
    count: int = 2400, seed: int = SEED, attack_fraction: float = 0.07
) -> GeneratedBatch:
    clean = generate_clean_manifest(count, seed)
    corrupted, truth = inject_attacks(clean, seed + 1, attack_fraction)
    return GeneratedBatch(clean, corrupted, clean["record_id"].tolist(), truth)


def write_batch(batch: GeneratedBatch, output_dir: str | Path) -> None:
    """Persist operator-facing records separately from the evaluator-only log."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    batch.clean.to_csv(destination / "clean_manifest.csv", index=False)
    batch.corrupted.to_csv(destination / "corrupted_manifest.csv", index=False)
    (destination / "control_totals.json").write_text(
        json.dumps({"expected_record_ids": batch.expected_record_ids}, indent=2),
        encoding="utf-8",
    )
    (destination / "hidden_injection_log.json").write_text(
        json.dumps(batch.hidden_injection_log, indent=2, default=str),
        encoding="utf-8",
    )
