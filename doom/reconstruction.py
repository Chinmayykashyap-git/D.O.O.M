"""Auditable reconstruction backed by control-ledger and synthetic witness evidence."""

from __future__ import annotations

from typing import Any

import pandas as pd

from doom.schema import OWNERS

REPAIRABLE_WITNESSES = {
    "control_ledger", "customs_witness", "movement_history", "relational_analysis",
}
REMOVABLE_TYPES = {
    "DUPLICATE_EXACT", "DUPLICATE_NEAR", "FABRICATED",
}


def reconstruct_manifest(
    records: pd.DataFrame, incidents: list[dict[str, Any]]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    by_id = {str(item["record_id"]): item for item in incidents}
    output = records.copy(deep=True)
    decisions: list[dict[str, Any]] = []
    remove_ids: set[str] = set()
    owner_ids = set(OWNERS.values())

    for index, row in output.iterrows():
        record_id = str(row["record_id"])
        incident = by_id.get(record_id)
        before = row.to_dict()
        changes: list[dict[str, Any]] = []
        method = "integrity_checks"
        evidence_relied_on: list[str] = []
        explanation = "No detector found a supported invariant or witness violation."
        status = "ORIGINAL"
        confidence = 1.0

        if incident:
            kind = str(incident["tampering_type"])
            confidence = float(incident["confidence"])
            evidence_relied_on = sorted({
                f"{item['detector_id']}:{item['evidence_code']}"
                for item in incident["evidence"]
            })
            if kind in REMOVABLE_TYPES:
                status = "REMOVED"
                method = "duplicate_collapse" if kind.startswith("DUPLICATE") else "control_ledger_absence"
                remove_ids.add(record_id)
                if kind.startswith("DUPLICATE"):
                    retained = next(iter(incident["related_records"]), "unknown canonical record")
                    explanation = (
                        f"Only the duplicate entry is removed; ledger sequence and retained-record evidence "
                        f"identify {retained} as the canonical shipment."
                    )
                else:
                    explanation = (
                        "The row is absent from the expected record-ID ledger and independent schedule/container "
                        "witnesses; its plausible-looking payload is not treated as authentic."
                    )
            else:
                repair_candidates = [
                    item for item in incident["evidence"]
                    if item["detector_id"] in REPAIRABLE_WITNESSES
                    and item["field"] in before
                    and item["expected"] is not None
                    and item["observed"] != item["expected"]
                ]
                repair_item = None
                if kind == "RELATIONAL_ORPHAN":
                    repair_item = next(
                        (item for item in repair_candidates if item["evidence_code"] == "CONTAINER_OWNER_MISMATCH"),
                        None,
                    )
                if repair_item is None:
                    repair_item = next(iter(repair_candidates), None)
                if repair_item:
                    field = str(repair_item["field"])
                    original_value = output.at[index, field]
                    corrected = repair_item["expected"]
                    output.at[index, field] = corrected
                    changes.append({
                        "field": field,
                        "from": _safe(original_value),
                        "to": corrected,
                    })
                    method = repair_item["detector_id"]
                    status = "REPAIRED"
                    explanation = (
                        f"{field} was restored from {repair_item['detector_id']} evidence: "
                        f"{repair_item['explanation']}"
                    )
                    if field == "declared_value_usd":
                        quantity = float(output.at[index, "quantity"])
                        unit_price = round(float(corrected) / quantity, 2)
                        old_price = output.at[index, "unit_price_usd"]
                        output.at[index, "unit_price_usd"] = unit_price
                        if old_price != unit_price:
                            changes.append({
                                "field": "unit_price_usd",
                                "from": _safe(old_price),
                                "to": unit_price,
                            })
                    if field == "owner_id" and str(corrected) in owner_ids:
                        output.at[index, "owner"] = next(
                            name for name, owner_id in OWNERS.items()
                            if owner_id == str(corrected)
                        )
                        output.at[index, "container_owner"] = output.at[index, "owner"]
                        for owner_field in ("owner", "container_owner"):
                            if before[owner_field] != output.at[index, owner_field]:
                                changes.append({
                                    "field": owner_field,
                                    "from": before[owner_field],
                                    "to": output.at[index, owner_field],
                                })
                    if field == "current_location":
                        route = str(output.at[index, "planned_route"]).split("|")
                        if str(corrected) not in route:
                            output.at[index, field] = str(output.at[index, "origin"])
                            changes[-1]["to"] = output.at[index, field]
                    if field == "planned_route":
                        from doom.schema import route_distance_nm

                        output.at[index, "route_distance_nm"] = route_distance_nm(
                            str(corrected).split("|")
                        )
                        changes.append({
                            "field": "route_distance_nm",
                            "from": _safe(before["route_distance_nm"]),
                            "to": _safe(output.at[index, "route_distance_nm"]),
                        })
                elif kind in {"SLOW_DRIFT", "MODIFIED_VALUE"}:
                    customs = next(
                        (item for item in incident["evidence"] if item["detector_id"] == "customs_witness"),
                        None,
                    )
                    if customs and customs["field"] == "declared_value_usd":
                        expected_value = float(customs["expected"])
                        old_value = output.at[index, "declared_value_usd"]
                        old_price = output.at[index, "unit_price_usd"]
                        quantity = float(output.at[index, "quantity"])
                        output.at[index, "declared_value_usd"] = expected_value
                        output.at[index, "unit_price_usd"] = round(expected_value / quantity, 2)
                        changes.extend([
                            {"field": "declared_value_usd", "from": _safe(old_value), "to": expected_value},
                            {"field": "unit_price_usd", "from": _safe(old_price), "to": output.at[index, "unit_price_usd"]},
                        ])
                        method = "customs_constraint_solver"
                        status = "REPAIRED"
                        explanation = (
                            "Declared value and unit price were restored to the independent customs amount "
                            "and quantity-derived formula."
                        )
                    else:
                        status = "UNRECOVERABLE"
                        method = "insufficient_independent_value_witness"
                        explanation = "The value anomaly is supported, but there is no independent witness for the authentic amount."
                else:
                    status = "UNRECOVERABLE"
                    method = "no_sufficient_independent_witness"
                    explanation = (
                        "An integrity anomaly is supported, but available evidence does not establish a unique "
                        "authentic value. The observation is preserved without a guessed repair."
                    )

        after = output.loc[index].to_dict()
        decisions.append({
            "record_id": record_id,
            "status": status,
            "method": method,
            "evidence_relied_on": evidence_relied_on,
            "confidence": confidence,
            "before_after": _diff(before, after),
            "explanation": explanation,
            "why": explanation,
            "changes": changes,
            "tampering_type": incident["tampering_type"] if incident else None,
        })

    if remove_ids:
        output = output.loc[~output["record_id"].astype(str).isin(remove_ids)].reset_index(drop=True)

    for incident in incidents:
        if incident.get("record_missing"):
            explanation = (
                "Expected record and sequence are missing. The event and customs witnesses do not include "
                "a complete source row, so exact payload restoration would be speculation."
            )
            decisions.append({
                "record_id": incident["record_id"],
                "status": "UNRECOVERABLE",
                "method": "sequence_gap_without_payload_copy",
                "evidence_relied_on": sorted({
                    f"{item['detector_id']}:{item['evidence_code']}"
                    for item in incident["evidence"]
                }),
                "confidence": incident["confidence"],
                "before_after": {},
                "explanation": explanation,
                "why": explanation,
                "changes": [],
                "tampering_type": incident["tampering_type"],
            })
    return output, decisions


def _safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for field, value in before.items():
        current = _safe(after.get(field))
        previous = _safe(value)
        if previous != current:
            changed[field] = {"before": previous, "after": current}
    return changed
