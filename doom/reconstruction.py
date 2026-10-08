"""Auditable reconstruction backed by control-ledger and synthetic witness evidence."""

from __future__ import annotations

from typing import Any

import pandas as pd

from doom.schema import MANIFEST_COLUMNS, OWNERS

REPAIRABLE_WITNESSES = {
    "control_ledger", "customs_witness", "movement_history", "relational_analysis",
}
REMOVABLE_TYPES = {
    "DUPLICATE_EXACT", "DUPLICATE_NEAR", "FABRICATED",
}


def reconstruct_manifest(
    records: pd.DataFrame,
    incidents: list[dict[str, Any]],
    witnesses: Any = None,
    expected_ledger: pd.DataFrame | list[dict[str, Any]] | None = None,
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
                "The sequence gap and event history identify the missing shipment. Independent schedule, "
                "registry, customs, movement, and ledger witnesses recover the listed fields, but the "
                "original weight, status, current location, and exact event timestamp are not independently "
                "attested. "
                "The full manifest row therefore remains unrecoverable rather than being guessed."
            )
            recovered, provenance = _recover_missing_fields(
                str(incident["record_id"]), witnesses, expected_ledger
            )
            recovery_diff = {
                field: {"before": "ABSENT", "after": value}
                for field, value in recovered.items()
                if field != "record_id"
            }
            decisions.append({
                "record_id": incident["record_id"],
                "status": "UNRECOVERABLE",
                "method": "sequence_gap_without_payload_copy",
                "evidence_relied_on": sorted({
                    f"{item['detector_id']}:{item['evidence_code']}"
                    for item in incident["evidence"]
                }),
                "confidence": incident["confidence"],
                "before_after": recovery_diff,
                "explanation": explanation,
                "why": explanation,
                "changes": [],
                "recovered_fields": recovered,
                "field_provenance": provenance,
                "unrecoverable_fields": [
                    field for field in MANIFEST_COLUMNS if field not in recovered
                ],
                "tampering_type": incident["tampering_type"],
            })
    return output, decisions


def _recover_missing_fields(
    record_id: str,
    witnesses: Any,
    expected_ledger: pd.DataFrame | list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if witnesses is None:
        witness_rows: dict[str, list[dict[str, Any]]] = {}
    elif hasattr(witnesses, "as_dict"):
        witness_rows = witnesses.as_dict()
    elif isinstance(witnesses, dict):
        witness_rows = {
            key: _records(value) for key, value in witnesses.items()
        }
    else:
        raise TypeError("witnesses must be a mapping or WitnessTables value")

    recovered: dict[str, Any] = {"record_id": record_id}
    provenance: dict[str, str] = {"record_id": "control_ledger:expected_record_id"}
    ledger_by_id = {
        str(row["record_id"]): row for row in _records(expected_ledger)
    }
    ledger = ledger_by_id.get(record_id)
    if ledger:
        for field in (
            "ledger_sequence", "previous_hash", "payload_hash", "ledger_hash",
        ):
            recovered[field] = _plain(ledger.get(field))
            provenance[field] = f"control_ledger:{field}"

    movements = [
        row for row in witness_rows.get("movement_history", [])
        if str(row.get("record_id")) == record_id
    ]
    if not movements:
        return recovered, provenance
    movements.sort(key=lambda row: str(row.get("event_sequence", "")))
    movement = movements[0]
    shipment_id = str(movement.get("shipment_id", ""))
    container_id = str(movement.get("container_id", ""))
    recovered.update({"shipment_id": shipment_id, "container_id": container_id})
    provenance.update({
        "shipment_id": "movement_history:shipment_id",
        "container_id": "movement_history:container_id",
    })

    schedules = {
        str(row.get("shipment_id")): row
        for row in witness_rows.get("vessel_schedule", [])
    }
    schedule = schedules.get(shipment_id)
    if schedule:
        for field, source in (
            ("vessel_id", "vessel_id"),
            ("planned_route", "route"),
            ("departure_ts", "departure_ts"),
            ("arrival_ts", "arrival_ts"),
            ("speed_class", "speed_class"),
        ):
            if schedule.get(source) is not None:
                recovered[field] = _plain(schedule[source])
                provenance[field] = f"vessel_schedule:{source}"
        if schedule.get("route"):
            from doom.schema import route_distance_nm

            recovered["route_distance_nm"] = route_distance_nm(
                str(schedule["route"]).split("|")
            )
            provenance["route_distance_nm"] = "derived:vessel_schedule.route"
            recovered["origin"] = str(schedule["route"]).split("|")[0]
            recovered["destination"] = str(schedule["route"]).split("|")[-1]
            provenance["origin"] = "derived:vessel_schedule.route"
            provenance["destination"] = "derived:vessel_schedule.route"

    containers = {
        str(row.get("container_id")): row
        for row in witness_rows.get("container_registry", [])
    }
    container = containers.get(container_id)
    if container:
        for field in ("container_type", "owner_id"):
            if container.get(field) is not None:
                recovered[field] = _plain(container[field])
                provenance[field] = f"container_registry:{field}"
        owner_id = str(container.get("owner_id", ""))
        owners = {
            str(row.get("owner_id")): row.get("owner_name")
            for row in witness_rows.get("owner_registry", [])
        }
        if owners.get(owner_id):
            recovered["owner"] = str(owners[owner_id])
            recovered["container_owner"] = str(owners[owner_id])
            provenance["owner"] = "owner_registry:owner_name"
            provenance["container_owner"] = "owner_registry:owner_name"

    customs = {
        str(row.get("shipment_id")): row
        for row in witness_rows.get("customs_entries", [])
    }.get(shipment_id)
    if customs:
        for field in ("declared_value_usd", "quantity", "destination"):
            if customs.get(field) is not None:
                recovered[field] = _plain(customs[field])
                provenance[field] = f"customs_entries:{field}"
        quantity = float(customs.get("quantity") or 0)
        value = float(customs.get("declared_value_usd") or 0)
        if quantity > 0:
            recovered["unit_price_usd"] = round(value / quantity, 2)
            provenance["unit_price_usd"] = "derived:customs_entries.value_and_quantity"

    return recovered, provenance


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    return list(value)


def _plain(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


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
