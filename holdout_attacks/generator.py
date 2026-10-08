"""Independent unseen attack family generator; not imported by fitting code."""

from __future__ import annotations

import hashlib
import random

import pandas as pd

from doom.schema import chain_hash

HOLDOUT_ATTACKS = (
    "LEDGER_FORK",
    "WEIGHT_WITNESS_DRIFT",
    "UNREGISTERED_EXTENSION_FIELD",
)


def inject_holdout_attacks(
    clean: pd.DataFrame, seed: int = 2291,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    if len(clean) < len(HOLDOUT_ATTACKS):
        raise ValueError(f"at least {len(HOLDOUT_ATTACKS)} clean records are required")
    rng = random.Random(seed)
    rows = clean.copy(deep=True).reset_index(drop=True)
    positions = rng.sample(range(len(rows)), len(HOLDOUT_ATTACKS))
    findings: list[dict[str, str]] = []
    for attack, position in zip(HOLDOUT_ATTACKS, positions):
        row = rows.loc[position]
        record_id = str(row["record_id"])
        if attack == "LEDGER_FORK":
            fork = hashlib.sha256(f"fork:{seed}:{record_id}".encode()).hexdigest()
            rows.at[position, "previous_hash"] = fork
            rows.at[position, "ledger_hash"] = chain_hash(
                int(row["ledger_sequence"]), fork, str(row["payload_hash"])
            )
        elif attack == "WEIGHT_WITNESS_DRIFT":
            rows.at[position, "weight_kg"] = round(float(row["weight_kg"]) + 1.25, 2)
        else:
            if "future_custody_mode" not in rows:
                rows["future_custody_mode"] = pd.Series(
                    [None] * len(rows), dtype="object"
                )
            rows.at[position, "future_custody_mode"] = "SEALED_CUSTODY_V2"
        findings.append({"record_id": record_id, "holdout_attack": attack})
    return rows, findings
