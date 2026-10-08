"""Synthetic attack injection. Ground-truth output is evaluator-only data."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

import pandas as pd

from doom.schema import OWNERS, VESSELS, chain_hash, payload_hash

ATTACK_TYPES = (
    "MODIFIED_VALUE",
    "DELETED",
    "DUPLICATE_EXACT",
    "DUPLICATE_NEAR",
    "FABRICATED",
    "TIMESTAMP_SHIFT",
    "TELEPORTATION",
    "PORT_SKIP",
    "NEGATIVE_TRANSIT",
    "RELATIONAL_ORPHAN",
    "VESSEL_MISMATCH",
    "SLOW_DRIFT",
)


def inject_attacks(
    clean: pd.DataFrame,
    seed: int = 1908,
    attack_fraction: float = 0.07,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not 0 < attack_fraction <= 0.25:
        raise ValueError("attack_fraction must be in the interval (0, 0.25]")
    rng = random.Random(seed)
    per_type = max(1, round(len(clean) * attack_fraction / len(ATTACK_TYPES)))
    total = min(len(clean), per_type * len(ATTACK_TYPES))
    selected = rng.sample(list(clean.index), total)
    attack_sequence = [attack for attack in ATTACK_TYPES for _ in range(per_type)]
    rng.shuffle(attack_sequence)
    rows = clean.to_dict(orient="records")
    index_by_id = {str(row["record_id"]): index for index, row in enumerate(rows)}
    removals: set[str] = set()
    truth: list[dict[str, Any]] = []
    next_identifier = rng.randrange(1_000_000, 9_999_999)
    maximum_sequence = max(int(row["ledger_sequence"]) for row in rows)
    final_hash = max(rows, key=lambda row: int(row["ledger_sequence"]))["ledger_hash"]

    def new_id(prefix: str) -> str:
        nonlocal next_identifier
        while True:
            candidate = f"{prefix}-{next_identifier:07d}"
            next_identifier = (next_identifier + rng.randrange(31, 997)) % 9_000_000 + 1_000_000
            if candidate not in index_by_id:
                return candidate

    for attack, source_index in zip(attack_sequence, selected):
        original = dict(rows[source_index])
        original_id = str(original["record_id"])
        target_index = index_by_id[original_id]
        entry: dict[str, Any] = {
            "record_id": original_id,
            "source_record_id": original_id,
            "tampering_type": attack,
            "original": original,
            "modified_fields": {},
        }
        if attack == "MODIFIED_VALUE":
            modified = rows[target_index]
            modified["unit_price_usd"] = round(float(modified["unit_price_usd"]) * 1.025, 2)
            modified["declared_value_usd"] = round(
                float(modified["quantity"]) * float(modified["unit_price_usd"]), 2
            )
        elif attack == "DELETED":
            removals.add(original_id)
        elif attack in {"DUPLICATE_EXACT", "DUPLICATE_NEAR"}:
            duplicate = dict(original)
            duplicate["record_id"] = new_id("MF")
            if attack == "DUPLICATE_NEAR":
                duplicate["declared_value_usd"] = round(
                    float(duplicate["declared_value_usd"]) * 1.002, 2
                )
                duplicate["unit_price_usd"] = round(
                    duplicate["declared_value_usd"] / int(duplicate["quantity"]), 2
                )
            duplicate["payload_hash"] = payload_hash(duplicate)
            duplicate["ledger_hash"] = chain_hash(
                int(duplicate["ledger_sequence"]),
                str(duplicate["previous_hash"]),
                str(duplicate["payload_hash"]),
            )
            entry["record_id"] = duplicate["record_id"]
            entry["source_record_id"] = original_id
            entry["modified_fields"] = {
                key: {"original": original[key], "observed": duplicate[key]}
                for key in original
                if key not in {"record_id", "previous_hash", "payload_hash", "ledger_hash"}
                and original[key] != duplicate[key]
            }
            rows.append(duplicate)
            index_by_id[str(duplicate["record_id"])] = len(rows) - 1
        elif attack == "FABRICATED":
            fabricated = dict(original)
            fabricated["record_id"] = new_id("MF")
            fabricated["shipment_id"] = new_id("SHP")
            fabricated["container_id"] = (
                f"{fabricated['owner_id']}U{rng.randrange(1_000_000, 9_999_999):07d}"
            )
            fabricated["ledger_sequence"] = maximum_sequence + 1
            fabricated["previous_hash"] = str(final_hash)
            fabricated["payload_hash"] = payload_hash(fabricated)
            fabricated["ledger_hash"] = chain_hash(
                int(fabricated["ledger_sequence"]),
                str(fabricated["previous_hash"]),
                str(fabricated["payload_hash"]),
            )
            entry["record_id"] = fabricated["record_id"]
            entry["source_record_id"] = original_id
            entry["modified_fields"] = {
                key: {"original": original[key], "observed": fabricated[key]}
                for key in original
                if key not in {"record_id", "previous_hash", "payload_hash", "ledger_hash"}
                and original[key] != fabricated[key]
            }
            rows.append(fabricated)
            index_by_id[str(fabricated["record_id"])] = len(rows) - 1
            maximum_sequence += 1
            final_hash = fabricated["ledger_hash"]
        elif attack == "TIMESTAMP_SHIFT":
            modified = rows[target_index]
            modified["arrival_ts"] = (
                pd.Timestamp(modified["arrival_ts"]).to_pydatetime()
                + timedelta(hours=6)
            ).isoformat()
        elif attack == "TELEPORTATION":
            modified = rows[target_index]
            route = str(modified["planned_route"]).split("|")
            modified["current_location"] = next(
                port for port in ("NLRTM", "SGSIN", "USLAX", "AEJEA", "CNSHA", "DEHAM", "BRSSZ", "JPTYO", "GBFXT", "INNSA")
                if port not in route
            )
        elif attack == "PORT_SKIP":
            modified = rows[target_index]
            route = str(modified["planned_route"]).split("|")
            if len(route) > 2:
                modified["planned_route"] = "|".join([route[0], *route[2:]])
                modified["route_distance_nm"] = max(
                    float(modified["route_distance_nm"]) * 0.7, 1.0
                )
            else:
                modified["current_location"] = "GBFXT"
        elif attack == "NEGATIVE_TRANSIT":
            modified = rows[target_index]
            modified["arrival_ts"] = (
                pd.Timestamp(modified["departure_ts"]).to_pydatetime()
                - timedelta(minutes=11)
            ).isoformat()
        elif attack == "RELATIONAL_ORPHAN":
            modified = rows[target_index]
            other_codes = [code for code in OWNERS.values() if code != modified["owner_id"]]
            modified["owner_id"] = rng.choice(other_codes)
        elif attack == "VESSEL_MISMATCH":
            modified = rows[target_index]
            candidates = [
                vessel
                for vessels in VESSELS.values()
                for vessel in vessels
                if vessel != modified["vessel_id"]
            ]
            modified["vessel_id"] = rng.choice(candidates)
        elif attack == "SLOW_DRIFT":
            modified = rows[target_index]
            modified["unit_price_usd"] = round(float(modified["unit_price_usd"]) * 1.008, 2)
            modified["declared_value_usd"] = round(
                float(modified["quantity"]) * float(modified["unit_price_usd"]), 2
            )
        if attack not in {"DELETED", "DUPLICATE_EXACT", "DUPLICATE_NEAR", "FABRICATED"}:
            modified_row = rows[target_index]
            entry["modified_fields"] = {
                key: {"original": original[key], "observed": modified_row[key]}
                for key in original
                if key not in {"record_id", "previous_hash", "payload_hash", "ledger_hash"}
                and original[key] != modified_row[key]
            }
        truth.append(entry)

    result = pd.DataFrame(
        [row for row in rows if str(row["record_id"]) not in removals]
    )
    result = result.sample(frac=1, random_state=seed).reset_index(drop=True)
    return result, truth


def valid_original_ids(clean: pd.DataFrame) -> list[str]:
    """IDs in the independently generated manifest control ledger."""
    return clean["record_id"].astype(str).tolist()
