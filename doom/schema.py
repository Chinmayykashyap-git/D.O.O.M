"""Canonical manifest fields, synthetic fleet registry, and route geometry."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


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
CONTAINER_LIMITS_KG = {"20FT": (1000.0, 24000.0), "40FT": (1000.0, 30000.0)}
VESSELS = {
    "Aster Maritime": ("AST-ORION", "AST-VEGA"),
    "Crown Meridian": ("CRM-ATHENA", "CRM-ATLAS"),
    "Northstar Freight": ("NSF-KESTREL", "NSF-POLARIS"),
    "Pelagic Union": ("PLU-TIDAL", "PLU-CURRENTS"),
    "Ironclad Logistics": ("IRN-FORGE", "IRN-BASTION"),
    "Sable Oceanic": ("SAB-SELENE", "SAB-NEREID"),
}
VESSEL_SPEED_KNOTS = {"ECONOMY": 15.0, "STANDARD": 18.0, "EXPRESS": 22.0}

MANIFEST_COLUMNS = [
    "record_id", "shipment_id", "owner", "owner_id", "container_id",
    "container_type", "container_owner", "vessel_id", "origin", "destination",
    "planned_route", "route_distance_nm", "speed_class", "quantity",
    "unit_price_usd", "declared_value_usd", "weight_kg", "status",
    "current_location", "departure_ts", "arrival_ts", "event_ts",
    "ledger_sequence", "previous_hash", "payload_hash", "ledger_hash",
]
HASH_COLUMNS = {
    "ledger_sequence", "previous_hash", "payload_hash", "ledger_hash",
}
SURFACE_COLUMNS = {"record_id", "shipment_id", "departure_ts", "arrival_ts", "event_ts"}


def route_distance_nm(route: list[str] | tuple[str, ...]) -> float:
    total = 0.0
    for first, second in zip(route, route[1:]):
        _, lat1, lon1 = PORTS[first]
        _, lat2, lon2 = PORTS[second]
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        haversine = math.sin(delta_phi / 2) ** 2 + (
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        kilometers = 6371.0 * 2 * math.asin(math.sqrt(haversine))
        total += kilometers / 1.852
    return round(total, 2)


def canonical_payload(row: dict[str, Any]) -> str:
    return json.dumps(
        {key: row[key] for key in sorted(row) if key not in HASH_COLUMNS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def payload_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(row).encode("utf-8")).hexdigest()


def chain_hash(sequence: int, previous_hash: str, content_hash: str) -> str:
    return hashlib.sha256(
        f"{sequence}|{previous_hash}|{content_hash}".encode("utf-8")
    ).hexdigest()


def seal_manifest(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous = "DOOM-GENESIS-v1"
    sealed: list[dict[str, Any]] = []
    for sequence, original in enumerate(records, start=1):
        row = dict(original)
        row["ledger_sequence"] = sequence
        row["previous_hash"] = previous
        row["payload_hash"] = payload_hash(row)
        row["ledger_hash"] = chain_hash(
            sequence, row["previous_hash"], row["payload_hash"]
        )
        previous = row["ledger_hash"]
        sealed.append(row)
    return sealed
