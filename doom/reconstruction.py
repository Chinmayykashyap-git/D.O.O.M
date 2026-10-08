"""Auditable reconstruction decisions for every observed or expected record."""

from __future__ import annotations

from typing import Any

import pandas as pd

from doom.generator import OWNERS


def reconstruct_manifest(
    records: pd.DataFrame, incidents: list[dict[str, Any]]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    by_id = {str(item["record_id"]): item for item in incidents}
    owner_names = set(OWNERS)
    output = records.copy(deep=True)
    decisions: list[dict[str, Any]] = []
    remove_ids: set[str] = set()

    for _, row in output.iterrows():
        record_id = str(row["record_id"])
        incident = by_id.get(record_id)
        status = "ORIGINAL"
        changes: list[dict[str, str]] = []
        explanation = "No integrity anomaly was supported by the available evidence."

        if incident:
            kind = incident["tampering_type"]
            if kind == "DUPLICATE":
                status = "REMOVED"
                remove_ids.add(record_id)
                explanation = "Duplicate shipment row removed; the retained shipment record remains in the manifest."
            elif kind == "FABRICATED" and incident["confidence"] >= 0.9:
                status = "REMOVED"
                remove_ids.add(record_id)
                explanation = "Unregistered shipment removed after independent fleet-registration evidence."
            elif kind == "RELATIONAL_INCONSISTENCY":
                index = output.index[output["record_id"].astype(str) == record_id][0]
                original_owner = str(output.at[index, "owner"])
                corroborating_owner = str(output.at[index, "container_owner"])
                if corroborating_owner in owner_names:
                    output.at[index, "owner"] = corroborating_owner
                    status = "REPAIRED"
                    changes.append({
                        "field": "owner",
                        "from": original_owner,
                        "to": corroborating_owner,
                    })
                    explanation = "Owner restored from the matching registered container-owner record."
                else:
                    status = "UNRECOVERABLE"
                    explanation = "Conflicting ownership evidence has no independently corroborated value."
            elif kind == "IMPOSSIBLE_MOVEMENT":
                route = [part for part in str(row["planned_route"]).split("|") if part]
                origin = str(row["origin"])
                if origin in route:
                    index = output.index[output["record_id"].astype(str) == record_id][0]
                    previous = str(output.at[index, "current_location"])
                    output.at[index, "current_location"] = origin
                    status = "REPAIRED"
                    changes.append({
                        "field": "current_location",
                        "from": previous,
                        "to": origin,
                    })
                    explanation = "Impossible location reset to the corroborated route origin; the suspect observation is preserved in this decision."
                else:
                    status = "UNRECOVERABLE"
                    explanation = "No trustworthy location can be established from the route evidence."
            else:
                status = "UNRECOVERABLE"
                explanation = "Anomaly is supported, but no independent source can establish the original field value."

        decisions.append({
            "record_id": record_id,
            "status": status,
            "explanation": explanation,
            "changes": changes,
            "tampering_type": incident["tampering_type"] if incident else None,
        })

    if remove_ids:
        output = output.loc[~output["record_id"].astype(str).isin(remove_ids)].reset_index(drop=True)

    for incident in incidents:
        if incident.get("record_missing"):
            decisions.append({
                "record_id": incident["record_id"],
                "status": "UNRECOVERABLE",
                "explanation": "Expected record is absent and no independent copy exists to reconstruct its contents.",
                "changes": [],
                "tampering_type": incident["tampering_type"],
            })
    return output, decisions
