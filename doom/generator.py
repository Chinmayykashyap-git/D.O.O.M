"""Deterministic, plausible synthetic shipments and independent witness ledgers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from doom.schema import (
    CONTAINER_LIMITS_KG,
    MANIFEST_COLUMNS,
    OWNERS,
    ROUTES,
    VESSEL_SPEED_KNOTS,
    VESSELS,
    route_distance_nm,
    seal_manifest,
)

SEED = 1907


@dataclass
class WitnessTables:
    owner_registry: pd.DataFrame
    container_registry: pd.DataFrame
    vessel_schedule: pd.DataFrame
    movement_history: pd.DataFrame
    port_logs: pd.DataFrame
    customs_entries: pd.DataFrame

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            name: frame.to_dict(orient="records")
            for name, frame in self.__dict__.items()
        }


def generate_dataset(
    count: int = 2400, seed: int = SEED
) -> tuple[pd.DataFrame, WitnessTables]:
    """Generate a stable manifest and correlated but separately queryable witnesses."""
    if count < 1:
        raise ValueError("count must be at least 1")
    rng = random.Random(seed)
    owner_names = tuple(OWNERS)
    identifier_pool = rng.sample(range(1_000_000, 9_999_999), count * 3)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    records: list[dict[str, Any]] = []
    schedules: list[dict[str, Any]] = []
    container_rows: list[dict[str, Any]] = []

    for index in range(count):
        owner = rng.choice(owner_names)
        owner_id = OWNERS[owner]
        route = rng.choice(ROUTES)
        distance = route_distance_nm(route)
        vessel = rng.choice(VESSELS[owner])
        speed_class = rng.choice(tuple(VESSEL_SPEED_KNOTS))
        speed = VESSEL_SPEED_KNOTS[speed_class]
        quantity = rng.randint(20, 980)
        price = round(rng.uniform(45.0, 1750.0), 2)
        value = round(quantity * price, 2)
        container_type = rng.choice(tuple(CONTAINER_LIMITS_KG))
        low, high = CONTAINER_LIMITS_KG[container_type]
        weight = round(rng.uniform(low, high), 1)
        departure = start + timedelta(
            days=rng.randint(0, 270),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
        )
        sea_hours = distance / speed
        dwell_hours = 9.0 * (len(route) - 2)
        transit_hours = sea_hours + dwell_hours + rng.uniform(8.0, 40.0)
        arrival = departure + timedelta(hours=transit_hours)
        position = rng.randrange(max(1, len(route) - 1))
        event_time = departure + (arrival - departure) * (
            position / max(len(route) - 1, 1)
        )
        record_id = f"MF-{identifier_pool[index * 3]:07d}"
        shipment_id = f"SHP-{identifier_pool[index * 3 + 1]:07d}"
        container_id = f"{owner_id}U{identifier_pool[index * 3 + 2]:07d}"
        record = {
            "record_id": record_id,
            "shipment_id": shipment_id,
            "owner": owner,
            "owner_id": owner_id,
            "container_id": container_id,
            "container_type": container_type,
            "container_owner": owner,
            "vessel_id": vessel,
            "origin": route[0],
            "destination": route[-1],
            "planned_route": "|".join(route),
            "route_distance_nm": distance,
            "speed_class": speed_class,
            "quantity": quantity,
            "unit_price_usd": price,
            "declared_value_usd": value,
            "weight_kg": weight,
            "status": "IN_TRANSIT",
            "current_location": route[position],
            "departure_ts": departure.isoformat(),
            "arrival_ts": arrival.isoformat(),
            "event_ts": event_time.isoformat(),
        }
        records.append(record)
        schedules.append({
            "shipment_id": shipment_id,
            "vessel_id": vessel,
            "owner_id": owner_id,
            "speed_class": speed_class,
            "speed_knots": speed,
            "route": "|".join(route),
            "departure_ts": departure.isoformat(),
            "arrival_ts": arrival.isoformat(),
        })
        container_rows.append({
            "container_id": container_id,
            "container_type": container_type,
            "owner_id": owner_id,
            "maximum_weight_kg": high,
        })

    rng.shuffle(records)
    manifest = pd.DataFrame(seal_manifest(records), columns=MANIFEST_COLUMNS)
    witnesses = build_witness_tables(manifest, schedules, container_rows)
    return manifest, witnesses


def generate_clean_manifest(count: int = 2400, seed: int = SEED) -> pd.DataFrame:
    """Compatibility helper returning the manifest component of generated data."""
    return generate_dataset(count, seed)[0]


def build_witness_tables(
    manifest: pd.DataFrame,
    schedules: list[dict[str, Any]] | None = None,
    container_rows: list[dict[str, Any]] | None = None,
) -> WitnessTables:
    """Build synthetic cross-table witnesses and event-sourced route histories."""
    if schedules is None:
        schedules = []
    if container_rows is None:
        container_rows = []
    existing_schedules = {row["shipment_id"] for row in schedules}
    existing_containers = {row["container_id"] for row in container_rows}
    if len(schedules) != len(manifest) or not existing_schedules:
        schedules = manifest[[
            "shipment_id", "vessel_id", "owner_id", "speed_class",
            "planned_route", "departure_ts", "arrival_ts",
        ]].rename(columns={"planned_route": "route"}).to_dict(orient="records")
        for row in schedules:
            row["speed_knots"] = VESSEL_SPEED_KNOTS[str(row["speed_class"])]
    if len(container_rows) != len(manifest) or not existing_containers:
        container_rows = manifest[[
            "container_id", "container_type", "owner_id",
        ]].to_dict(orient="records")
        for row in container_rows:
            row["maximum_weight_kg"] = CONTAINER_LIMITS_KG[str(row["container_type"])][1]

    owner_rows = [
        {"owner_id": code, "owner_name": name, "active": True}
        for name, code in OWNERS.items()
    ]
    event_records: list[dict[str, Any]] = []
    customs: list[dict[str, Any]] = []
    port_logs: list[dict[str, Any]] = []
    event_sequence = 0
    for row in manifest.to_dict(orient="records"):
        route = str(row["planned_route"]).split("|")
        departure = datetime.fromisoformat(str(row["departure_ts"]))
        arrival = datetime.fromisoformat(str(row["arrival_ts"]))
        duration = arrival - departure
        shipment_id = str(row["shipment_id"])
        movements: list[tuple[str, str, float]] = [("LOAD", route[0], 0.0)]
        for position in range(1, len(route)):
            fraction = position / max(len(route) - 1, 1)
            movements.append(("PORT_ARRIVAL", route[position], fraction))
            if position < len(route) - 1:
                movements.extend([
                    ("TRANSFER", route[position], fraction + 0.001),
                    ("PORT_DEPARTURE", route[position], fraction + 0.002),
                ])
            else:
                movements.extend([
                    ("CUSTOMS", route[position], fraction + 0.001),
                    ("DISCHARGE", route[position], fraction + 0.002),
                ])
        for event_type, port, fraction in movements:
            event_sequence += 1
            timestamp = departure + duration * min(fraction, 0.999)
            event = {
                "event_id": f"EV-{event_sequence:010d}",
                "event_sequence": event_sequence,
                "shipment_id": shipment_id,
                "record_id": row["record_id"],
                "container_id": row["container_id"],
                "event_type": event_type,
                "port_code": port,
                "event_ts": timestamp.isoformat(),
            }
            event_records.append(event)
            if event_type in {"PORT_ARRIVAL", "PORT_DEPARTURE", "TRANSFER"}:
                port_logs.append({
                    "port_code": port,
                    "event_type": event_type,
                    "event_ts": timestamp.isoformat(),
                    "shipment_id": shipment_id,
                    "container_id": row["container_id"],
                    "record_id": row["record_id"],
                })
        customs.append({
            "customs_id": f"CU-{event_sequence:010d}",
            "shipment_id": shipment_id,
            "container_id": row["container_id"],
            "destination": row["destination"],
            "declared_value_usd": row["declared_value_usd"],
            "quantity": row["quantity"],
            "clearance_ts": arrival.isoformat(),
        })

    return WitnessTables(
        owner_registry=pd.DataFrame(owner_rows),
        container_registry=pd.DataFrame(container_rows),
        vessel_schedule=pd.DataFrame(schedules),
        movement_history=pd.DataFrame(event_records),
        port_logs=pd.DataFrame(port_logs),
        customs_entries=pd.DataFrame(customs),
    )


def output_hashes(manifest: pd.DataFrame) -> dict[str, str]:
    """Stable deterministic serialization digests used by the generator gate."""
    import hashlib

    csv = manifest.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return {"manifest_sha256": hashlib.sha256(csv).hexdigest()}


def make_control_ledger(manifest: pd.DataFrame) -> pd.DataFrame:
    return manifest[[
        "record_id", "ledger_sequence", "previous_hash", "payload_hash", "ledger_hash",
    ]].copy()


def write_manifest(manifest: pd.DataFrame, output_path: str | Path) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        manifest.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
        newline="",
    )


def write_witness_tables(witnesses: WitnessTables, output_dir: str | Path) -> None:
    destination = Path(output_dir) / "witnesses"
    destination.mkdir(parents=True, exist_ok=True)
    for name, frame in witnesses.__dict__.items():
        frame.to_csv(destination / f"{name}.csv", index=False, lineterminator="\n")
