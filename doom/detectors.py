"""Explainable integrity checks; this module never imports evaluator or attack code."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import pandas as pd

from doom.schema import (
    CONTAINER_LIMITS_KG,
    HASH_COLUMNS,
    MANIFEST_COLUMNS,
    VESSEL_SPEED_KNOTS,
    chain_hash,
    payload_hash,
    route_distance_nm,
)

TYPE_FOR_EVIDENCE = {
    "DUPLICATE_SHIPMENT": "DUPLICATE_EXACT",
    "DUPLICATE_NEAR_MATCH": "DUPLICATE_NEAR",
    "EXPECTED_PAYLOAD_HASH_MISMATCH": "UNKNOWN ANOMALY",
    "LEDGER_PREVIOUS_HASH_MISMATCH": "UNKNOWN ANOMALY",
    "EXPECTED_LEDGER_HASH_MISMATCH": "UNKNOWN ANOMALY",
    "DECLARED_VALUE_FORMULA": "MODIFIED_VALUE",
    "CUSTOMS_VALUE_MISMATCH": "MODIFIED_VALUE",
    "OWNER_REGISTRY_MISMATCH": "RELATIONAL_ORPHAN",
    "CONTAINER_OWNER_MISMATCH": "RELATIONAL_ORPHAN",
    "VESSEL_SCHEDULE_MISMATCH": "VESSEL_MISMATCH",
    "UNSCHEDULED_VESSEL": "VESSEL_MISMATCH",
    "ROUTE_SCHEDULE_MISMATCH": "PORT_SKIP",
    "PORT_LOG_SEQUENCE_MISMATCH": "PORT_SKIP",
    "LOCATION_OFF_ROUTE": "TELEPORTATION",
    "LOCATION_EVENT_MISMATCH": "TELEPORTATION",
    "NON_MONOTONIC_SHIPMENT_TIME": "NEGATIVE_TRANSIT",
    "EVENT_OUTSIDE_SHIPMENT_WINDOW": "TIMESTAMP_SHIFT",
    "SCHEDULE_TIME_MISMATCH": "TIMESTAMP_SHIFT",
    "EXPECTED_RECORD_ABSENT": "DELETED",
    "LEDGER_SEQUENCE_GAP": "DELETED",
    "UNREGISTERED_RECORD_ID": "FABRICATED",
    "UNRECOGNIZED_SCHEMA_FIELD": "UNKNOWN ANOMALY",
}

KNOWN_EVIDENCE_SIGNATURES = {
    "MODIFIED_VALUE": {
        "EXPECTED_PAYLOAD_HASH_MISMATCH", "DECLARED_VALUE_FORMULA",
        "CUSTOMS_VALUE_MISMATCH",
    },
    "DELETED": {"EXPECTED_RECORD_ABSENT", "LEDGER_SEQUENCE_GAP"},
    "DUPLICATE_EXACT": {"DUPLICATE_SHIPMENT"},
    "DUPLICATE_NEAR": {"DUPLICATE_NEAR_MATCH"},
    "FABRICATED": {"UNREGISTERED_RECORD_ID", "UNREGISTERED_CONTAINER"},
    "TIMESTAMP_SHIFT": {"EVENT_OUTSIDE_SHIPMENT_WINDOW", "SCHEDULE_TIME_MISMATCH"},
    "TELEPORTATION": {"LOCATION_OFF_ROUTE", "LOCATION_EVENT_MISMATCH"},
    "PORT_SKIP": {"ROUTE_SCHEDULE_MISMATCH", "PORT_LOG_SEQUENCE_MISMATCH"},
    "NEGATIVE_TRANSIT": {"NON_MONOTONIC_SHIPMENT_TIME"},
    "RELATIONAL_ORPHAN": {"OWNER_REGISTRY_MISMATCH", "CONTAINER_OWNER_MISMATCH"},
    "VESSEL_MISMATCH": {"VESSEL_SCHEDULE_MISMATCH", "UNSCHEDULED_VESSEL"},
    "SLOW_DRIFT": {"EXPECTED_PAYLOAD_HASH_MISMATCH", "CUSTOMS_VALUE_MISMATCH"},
}


class ManifestDetector:
    """Produce row-level evidence, classification hypotheses, and counterfactuals."""

    def detect(
        self,
        records: pd.DataFrame,
        expected_record_ids: Iterable[str] | None = None,
        expected_ledger: pd.DataFrame | list[dict[str, Any]] | None = None,
        witnesses: dict[str, list[dict[str, Any]]] | Any | None = None,
        active_detectors: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if "record_id" not in records.columns:
            raise ValueError("manifest must contain a record_id column")
        enabled = active_detectors
        frame = records.copy().reset_index(drop=True)
        known_ids = (
            set(map(str, expected_record_ids))
            if expected_record_ids is not None else set()
        )
        ledger_rows = self._records(expected_ledger)
        ledger_by_id = {str(item["record_id"]): item for item in ledger_rows}
        if not known_ids and ledger_by_id:
            known_ids = set(ledger_by_id)
        witness_rows = self._witness_rows(witnesses)
        owner_by_id = {
            str(item["owner_id"]): str(item["owner_name"])
            for item in witness_rows.get("owner_registry", [])
        }
        container_by_id = {
            str(item["container_id"]): item
            for item in witness_rows.get("container_registry", [])
        }
        schedule_by_shipment = {
            str(item["shipment_id"]): item
            for item in witness_rows.get("vessel_schedule", [])
        }
        customs_by_shipment = {
            str(item["shipment_id"]): item
            for item in witness_rows.get("customs_entries", [])
        }
        history_by_record: dict[str, list[dict[str, Any]]] = {}
        for event in witness_rows.get("movement_history", []):
            history_by_record.setdefault(str(event["record_id"]), []).append(event)
        for events in history_by_record.values():
            events.sort(key=lambda item: str(item["event_ts"]))

        evidence_by_id: dict[str, list[dict[str, Any]]] = {}
        related_by_id: dict[str, set[str]] = {}
        candidate_by_id: dict[str, dict[str, float]] = {}

        def add(
            record_id: str,
            detector_id: str,
            code: str,
            field: str,
            expected: Any,
            observed: Any,
            contribution: float,
            explanation: str,
            classification: str | None = None,
            related: Iterable[str] = (),
        ) -> None:
            if enabled is not None and detector_id not in enabled:
                return
            evidence_by_id.setdefault(record_id, []).append({
                "detector_id": detector_id,
                "evidence_code": code,
                "record_ids": [record_id, *sorted(set(map(str, related)) - {record_id})],
                "field": field,
                "expected": _safe(expected),
                "observed": _safe(observed),
                "score_contribution": round(contribution, 4),
                "severity": "CRITICAL" if contribution >= 0.9 else (
                    "HIGH" if contribution >= 0.7 else "MEDIUM"
                ),
                "explanation": explanation,
            })
            if classification:
                scores = candidate_by_id.setdefault(record_id, {})
                scores[classification] = scores.get(classification, 0.0) + contribution
            related_by_id.setdefault(record_id, set()).update(map(str, related))

        if enabled is None or "duplicate_detection" in enabled:
            self._duplicates(frame, add, known_ids)

        if enabled is None or "integrity_hash" in enabled:
            for row in frame.to_dict(orient="records"):
                record_id = str(row["record_id"])
                observed_digest = payload_hash(row)
                ledger = ledger_by_id.get(record_id)
                if ledger:
                    expected_digest = str(ledger["payload_hash"])
                    if observed_digest != expected_digest:
                        field, expected, observed = self._first_witness_difference(
                            row, record_id, customs_by_shipment, schedule_by_shipment,
                            container_by_id, owner_by_id,
                        )
                        add(
                            record_id, "integrity_hash", "EXPECTED_PAYLOAD_HASH_MISMATCH",
                            field or "payload_hash",
                            expected if field else expected_digest,
                            observed if field else observed_digest,
                            0.96,
                            "The manifest payload does not match the independently anchored ledger digest.",
                            (
                                _value_type(field, expected, observed)
                                if field in {"unit_price_usd", "declared_value_usd", "quantity"}
                                else None
                            ),
                        )
                    actual_sequence = int(row.get("ledger_sequence", 0))
                    if actual_sequence != int(ledger["ledger_sequence"]):
                        add(
                            record_id, "integrity_hash", "LEDGER_SEQUENCE_MISMATCH",
                            "ledger_sequence", ledger["ledger_sequence"], actual_sequence,
                            0.96, "The entry sequence conflicts with the trusted ledger witness.",
                        )
                    observed_chain = chain_hash(
                        actual_sequence,
                        str(row.get("previous_hash", "")),
                        str(row.get("payload_hash", "")),
                    )
                    if observed_chain != str(row.get("ledger_hash", "")):
                        add(
                            record_id, "integrity_hash", "LEDGER_HASH_CHAIN_BREAK",
                            "ledger_hash", observed_chain, row.get("ledger_hash"),
                            0.98, "The sequence-linked entry hash does not verify.",
                        )
                    if str(row.get("previous_hash", "")) != str(ledger["previous_hash"]):
                        add(
                            record_id, "integrity_hash", "LEDGER_PREVIOUS_HASH_MISMATCH",
                            "previous_hash", ledger["previous_hash"],
                            row.get("previous_hash"), 0.98,
                            "The row's chain pointer differs from the independently anchored ledger.",
                        )
                    if str(row.get("ledger_hash", "")) != str(ledger["ledger_hash"]):
                        add(
                            record_id, "integrity_hash", "EXPECTED_LEDGER_HASH_MISMATCH",
                            "ledger_hash", ledger["ledger_hash"], row.get("ledger_hash"),
                            0.98,
                            "The row's entry hash differs from the independently anchored ledger.",
                        )

        frame_ids = set(frame["record_id"].astype(str))
        if enabled is None or "control_ledger" in enabled:
            for missing_id in sorted(known_ids - frame_ids):
                ledger = ledger_by_id.get(missing_id, {})
                sequence = int(ledger.get("ledger_sequence", -1))
                successor = next(
                    (
                        str(item["record_id"])
                        for item in ledger_rows
                        if int(item["ledger_sequence"]) == sequence + 1
                    ),
                    "",
                )
                add(
                    missing_id, "control_ledger", "EXPECTED_RECORD_ABSENT",
                    "record_id", missing_id, None, 0.99,
                    "The expected record is absent from the manifest and its ledger sequence is missing.",
                    "DELETED", [successor] if successor else (),
                )
                add(
                    missing_id, "control_ledger", "LEDGER_SEQUENCE_GAP",
                    "ledger_sequence", sequence, None, 0.95,
                    "A missing expected sequence creates a visible gap in the append-only ledger.",
                    "DELETED", [successor] if successor else (),
                )
            for row in frame.to_dict(orient="records"):
                record_id = str(row["record_id"])
                if known_ids and record_id not in known_ids:
                    add(
                        record_id, "control_ledger", "UNREGISTERED_RECORD_ID",
                        "record_id", "present in expected ledger", record_id, 0.9,
                        "Record identity is not present in the independently generated expected-ID ledger.",
                        "FABRICATED",
                    )

        for row in frame.to_dict(orient="records"):
            record_id = str(row["record_id"])
            shipment_id = str(row.get("shipment_id", ""))
            route = [part for part in str(row.get("planned_route", "")).split("|") if part]
            owner_name = str(row.get("owner", ""))
            owner_id = str(row.get("owner_id", ""))
            container_id = str(row.get("container_id", ""))

            if enabled is None or "relational_analysis" in enabled:
                expected_owner = owner_by_id.get(owner_id)
                if expected_owner and expected_owner != owner_name:
                    add(
                        record_id, "relational_analysis", "OWNER_REGISTRY_MISMATCH",
                        "owner", expected_owner, owner_name, 0.92,
                        "Owner identity conflicts with the synthetic owner registry.",
                        "RELATIONAL_ORPHAN",
                    )
                container = container_by_id.get(container_id)
                if container and str(container["owner_id"]) != owner_id:
                    add(
                        record_id, "relational_analysis", "CONTAINER_OWNER_MISMATCH",
                        "owner_id", container["owner_id"], owner_id, 0.93,
                        "Container ownership conflicts with the independent container registry.",
                        "RELATIONAL_ORPHAN",
                    )
                schedule = schedule_by_shipment.get(shipment_id)
                if schedule is None and witness_rows.get("vessel_schedule"):
                    add(
                        record_id, "relational_analysis", "UNSCHEDULED_VESSEL",
                        "shipment_id", "scheduled shipment", shipment_id, 0.93,
                        "No vessel schedule witness exists for this shipment.",
                        "VESSEL_MISMATCH",
                    )
                elif schedule:
                    for field in ("vessel_id", "route", "departure_ts", "arrival_ts"):
                        observed_field = "planned_route" if field == "route" else field
                        observed = row.get(observed_field)
                        expected = schedule.get(field)
                        if field == "route" and expected != observed:
                            add(
                                record_id, "relational_analysis", "ROUTE_SCHEDULE_MISMATCH",
                                "planned_route", expected, observed, 0.89,
                                "Declared itinerary differs from the independent vessel schedule.",
                                "PORT_SKIP",
                            )
                        elif field == "vessel_id" and expected != observed:
                            add(
                                record_id, "relational_analysis", "VESSEL_SCHEDULE_MISMATCH",
                                "vessel_id", expected, observed, 0.94,
                                "Assigned vessel differs from the independent sailing schedule.",
                                "VESSEL_MISMATCH",
                            )
                        elif field in {"departure_ts", "arrival_ts"} and expected != observed:
                            add(
                                record_id, "relational_analysis", "SCHEDULE_TIME_MISMATCH",
                                field, expected, observed, 0.83,
                                "Shipment timestamp differs from the independent vessel schedule.",
                                "TIMESTAMP_SHIFT",
                            )
                if container is None and witness_rows.get("container_registry"):
                    add(
                        record_id, "relational_analysis", "UNREGISTERED_CONTAINER",
                        "container_id", "registered container", container_id, 0.89,
                        "No matching container registry witness exists.",
                        "FABRICATED",
                    )
                if container:
                    low, high = CONTAINER_LIMITS_KG.get(
                        str(container["container_type"]), (0.0, float("inf"))
                    )
                    weight = float(row.get("weight_kg", 0) or 0)
                    if not low <= weight <= high:
                        add(
                            record_id, "relational_analysis", "CONTAINER_WEIGHT_BOUND",
                            "weight_kg", f"{low}..{high}", weight, 0.9,
                            "Cargo weight exceeds the registered container-type range.",
                            "MODIFIED_VALUE",
                        )

            distance = route_distance_nm(route) if len(route) >= 2 else 0.0
            if enabled is None or "route_validation" in enabled:
                current_location = str(row.get("current_location", ""))
                if route and current_location not in route:
                    add(
                        record_id, "route_validation", "LOCATION_OFF_ROUTE",
                        "current_location", route, current_location, 0.95,
                        "Observed location is not an endpoint or waypoint on the declared route.",
                        "TELEPORTATION",
                    )
                observed_distance = float(row.get("route_distance_nm", 0) or 0)
                if distance and abs(distance - observed_distance) > max(5.0, distance * 0.03):
                    add(
                        record_id, "route_validation", "PORT_LOG_SEQUENCE_MISMATCH",
                        "route_distance_nm", round(distance, 2), observed_distance, 0.87,
                        "Derived route distance disagrees with the declared itinerary.",
                        "PORT_SKIP",
                    )

            if enabled is None or "temporal_analysis" in enabled:
                departure = pd.to_datetime(row.get("departure_ts"), utc=True, errors="coerce")
                arrival = pd.to_datetime(row.get("arrival_ts"), utc=True, errors="coerce")
                event_time = pd.to_datetime(row.get("event_ts"), utc=True, errors="coerce")
                if pd.isna(departure) or pd.isna(arrival) or arrival <= departure:
                    add(
                        record_id, "temporal_analysis", "NON_MONOTONIC_SHIPMENT_TIME",
                        "arrival_ts", "later than departure_ts", row.get("arrival_ts"),
                        0.99, "Arrival timestamp is invalid or precedes departure.",
                        "NEGATIVE_TRANSIT",
                    )
                elif not pd.isna(event_time) and (
                    event_time < departure or event_time > arrival
                ):
                    add(
                        record_id, "temporal_analysis", "EVENT_OUTSIDE_SHIPMENT_WINDOW",
                        "event_ts", f"{departure.isoformat()}..{arrival.isoformat()}",
                        row.get("event_ts"), 0.88,
                        "Observed event time lies outside the shipment interval.",
                        "TIMESTAMP_SHIFT",
                    )
                schedule = schedule_by_shipment.get(shipment_id)
                if schedule:
                    expected_arrival = pd.to_datetime(
                        schedule["arrival_ts"], utc=True, errors="coerce"
                    )
                    if not pd.isna(arrival) and abs(
                        (arrival - expected_arrival).total_seconds()
                    ) > 60:
                        # Schedule mismatch was already emitted above; this check
                        # independently validates physically impossible transit.
                        pass
                speed = VESSEL_SPEED_KNOTS.get(str(row.get("speed_class", "")))
                if speed and distance:
                    minimum_hours = distance / (speed * 1.35)
                    transit_hours = (
                        (arrival - departure).total_seconds() / 3600
                        if not pd.isna(arrival) and not pd.isna(departure) else -1
                    )
                    if transit_hours >= 0 and transit_hours < minimum_hours * 0.55:
                        add(
                            record_id, "temporal_analysis", "IMPOSSIBLE_TRANSIT_SPEED",
                            "arrival_ts", f">={minimum_hours * 0.55:.1f} h",
                            round(transit_hours, 2), 0.89,
                            "Transit time requires an implausible speed for the route and vessel class.",
                            "NEGATIVE_TRANSIT",
                        )

            if enabled is None or "movement_history" in enabled:
                events = history_by_record.get(record_id, [])
                if events and not pd.isna(pd.to_datetime(row.get("event_ts"), utc=True, errors="coerce")):
                    cutoff = pd.to_datetime(row["event_ts"], utc=True)
                    state_events = [
                        event for event in events
                        if pd.to_datetime(event["event_ts"], utc=True) <= cutoff
                    ]
                    if state_events:
                        expected_location = str(state_events[-1]["port_code"])
                        actual_location = str(row.get("current_location", ""))
                        if expected_location != actual_location:
                            add(
                                record_id, "movement_history", "LOCATION_EVENT_MISMATCH",
                                "current_location", expected_location, actual_location, 0.9,
                                "Current location is inconsistent with the event-sourced movement history.",
                                "TELEPORTATION",
                            )

            if enabled is None or "customs_witness" in enabled:
                customs = customs_by_shipment.get(shipment_id)
                if customs:
                    for field in ("declared_value_usd", "quantity", "destination"):
                        expected = customs.get(field)
                        observed = row.get(field)
                        if expected != observed:
                            observed_number = _number(observed)
                            expected_number = _number(expected)
                            relative_delta = (
                                abs(observed_number - expected_number) / max(abs(expected_number), 1)
                                if observed_number is not None and expected_number is not None
                                else float("inf")
                            )
                            tampering_type = (
                                "SLOW_DRIFT" if field == "declared_value_usd" and relative_delta < 0.015
                                else "MODIFIED_VALUE" if field in {"declared_value_usd", "quantity"}
                                else "PORT_SKIP"
                            )
                            add(
                                record_id, "customs_witness", "CUSTOMS_VALUE_MISMATCH",
                                field, expected, observed, 0.91,
                                "Manifest field differs from the independent customs declaration.",
                                tampering_type,
                            )

        unexpected = sorted(set(frame.columns) - set(MANIFEST_COLUMNS))
        if unexpected:
            populated_rows = frame[unexpected].notna().any(axis=1)
            for record_id in frame.loc[populated_rows, "record_id"].astype(str):
                add(
                    record_id, "schema_novelty", "UNRECOGNIZED_SCHEMA_FIELD",
                    "schema", sorted(MANIFEST_COLUMNS), unexpected, 0.91,
                    "Record contains fields absent from the registered batch schema.",
                    "UNKNOWN ANOMALY",
                )

        return self._incidents(evidence_by_id, candidate_by_id, related_by_id)

    @staticmethod
    def detect_record(record: dict[str, Any]) -> dict[str, Any] | None:
        found = ManifestDetector().detect(pd.DataFrame([record]))
        return found[0] if found else None

    @staticmethod
    def _records(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, pd.DataFrame):
            return value.to_dict(orient="records")
        return list(value)

    @staticmethod
    def _witness_rows(value: Any) -> dict[str, list[dict[str, Any]]]:
        if value is None:
            return {}
        if hasattr(value, "as_dict"):
            return value.as_dict()
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _duplicates(frame: pd.DataFrame, add: Any, known_ids: set[str]) -> None:
        if "shipment_id" not in frame:
            return
        for _, group in frame.groupby("shipment_id", dropna=False):
            if len(group) <= 1:
                continue
            row_ids = group["record_id"].astype(str).tolist()
            expected_rows = group.loc[group["record_id"].astype(str).isin(known_ids)]
            if not expected_rows.empty:
                canonical = expected_rows.sort_values("ledger_sequence", kind="stable").iloc[0]
            else:
                canonical = group.sort_values("ledger_sequence", kind="stable").iloc[0]
            reference = canonical.to_dict()
            compared = HASH_COLUMNS | {"record_id", "ledger_sequence"}
            for _, duplicate in group.iterrows():
                if str(duplicate["record_id"]) == str(canonical["record_id"]):
                    continue
                current = duplicate.to_dict()
                differing = [
                    key for key in current
                    if key not in compared and _safe(current[key]) != _safe(reference.get(key))
                ]
                exact = not differing
                evidence_code = "DUPLICATE_SHIPMENT" if exact else "DUPLICATE_NEAR_MATCH"
                attack_type = "DUPLICATE_EXACT" if exact else "DUPLICATE_NEAR"
                add(
                    str(duplicate["record_id"]), "duplicate_detection", evidence_code,
                    differing[0] if differing else "shipment_id",
                    reference.get(differing[0]) if differing else reference.get("shipment_id"),
                    current.get(differing[0]) if differing else current.get("shipment_id"),
                    0.97 if exact else 0.99,
                    "Shipment identity duplicates a retained row; canonical entry is selected by ledger sequence.",
                    attack_type,
                    [value for value in row_ids if value != str(duplicate["record_id"])],
                )

    @staticmethod
    def _first_witness_difference(
        row: dict[str, Any], record_id: str, customs: dict[str, Any],
        schedules: dict[str, Any], containers: dict[str, Any], owners: dict[str, str],
    ) -> tuple[str | None, Any, Any]:
        shipment = str(row.get("shipment_id", ""))
        if shipment in customs:
            for field in ("declared_value_usd", "quantity", "destination"):
                if _safe(customs[shipment].get(field)) != _safe(row.get(field)):
                    return field, customs[shipment].get(field), row.get(field)
        schedule = schedules.get(shipment)
        if schedule:
            for field, expected_field in (
                ("vessel_id", "vessel_id"), ("planned_route", "route"),
                ("departure_ts", "departure_ts"), ("arrival_ts", "arrival_ts"),
            ):
                if _safe(schedule.get(expected_field)) != _safe(row.get(field)):
                    return field, schedule.get(expected_field), row.get(field)
        container = containers.get(str(row.get("container_id", "")))
        if container and str(container.get("owner_id")) != str(row.get("owner_id")):
            return "owner_id", container.get("owner_id"), row.get("owner_id")
        owner = owners.get(str(row.get("owner_id", "")))
        if owner and owner != str(row.get("owner", "")):
            return "owner", owner, row.get("owner")
        return None, None, None

    @staticmethod
    def _incidents(
        evidence_by_id: dict[str, list[dict[str, Any]]],
        candidate_by_id: dict[str, dict[str, float]],
        related_by_id: dict[str, set[str]],
    ) -> list[dict[str, Any]]:
        incidents = []
        for record_id, evidence in evidence_by_id.items():
            candidates = candidate_by_id.get(record_id, {})
            if candidates:
                tampering_type = max(candidates, key=lambda name: candidates[name])
            elif evidence:
                tampering_type = TYPE_FOR_EVIDENCE.get(
                    str(evidence[0]["evidence_code"]), "UNKNOWN ANOMALY"
                )
            else:
                continue
            best = max((item["score_contribution"] for item in evidence), default=0.5)
            total = sum(item["score_contribution"] for item in evidence)
            risk = min(100, round(100 * (1 - math.exp(-total))))
            denominator = sum(candidates.values()) or best
            probabilities = {
                name: round(score / denominator, 4) for name, score in candidates.items()
            }
            probabilities[tampering_type] = round(
                max(probabilities.get(tampering_type, 0.0), 0.5 + min(best, 0.49)), 4
            )
            counterfactual = _counterfactual(tampering_type, evidence)
            incidents.append({
                "record_id": record_id,
                "tampering_type": tampering_type,
                "unknown_analysis": (
                    _unknown_analysis(evidence)
                    if tampering_type == "UNKNOWN ANOMALY" else None
                ),
                "type_probabilities": probabilities,
                "risk_score": risk,
                "confidence": round(best, 2),
                "evidence": evidence,
                "detectors": sorted({item["detector_id"] for item in evidence}),
                "related_records": sorted(related_by_id.get(record_id, set()))[:12],
                "counterfactual": counterfactual,
                "record_missing": any(
                    item["evidence_code"] == "EXPECTED_RECORD_ABSENT" for item in evidence
                ),
            })
        return sorted(incidents, key=lambda item: (-item["risk_score"], item["record_id"]))


def _unknown_analysis(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    observed_codes = {
        str(item["evidence_code"]) for item in evidence
    }
    similarities = {
        attack: len(observed_codes & signature) / len(observed_codes | signature)
        if observed_codes | signature else 0.0
        for attack, signature in KNOWN_EVIDENCE_SIGNATURES.items()
    }
    nearest = sorted(
        similarities,
        key=lambda attack: (-similarities[attack], attack),
    )[0]
    return {
        "invariant_violations": [
            {
                "detector_id": str(item["detector_id"]),
                "evidence_code": str(item["evidence_code"]),
                "field": str(item["field"]),
                "explanation": str(item["explanation"]),
            }
            for item in evidence
        ],
        "nearest_known_attack_type": nearest,
        "nearest_similarity": round(similarities[nearest], 4),
        "novelty_score": round(1.0 - similarities[nearest], 4),
        "nearest_match_meaningful": similarities[nearest] > 0.0,
        "novelty_method": "Jaccard distance from fixed known-attack evidence signatures",
    }


def _safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return None
    return value


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _value_type(field: str, expected: Any, observed: Any) -> str:
    expected_number, observed_number = _number(expected), _number(observed)
    if expected_number and observed_number is not None:
        relative_delta = abs(observed_number - expected_number) / max(abs(expected_number), 1)
        if relative_delta < 0.015:
            return "SLOW_DRIFT"
    return "MODIFIED_VALUE"


def _counterfactual(tampering_type: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if tampering_type in {"DUPLICATE_EXACT", "DUPLICATE_NEAR"}:
        return {
            "action": "remove_duplicate",
            "field": "record_id",
            "expected": "retain the lowest-sequence canonical shipment row",
            "observed": "additional row duplicates the same shipment",
            "explanation": "Remove only the non-canonical duplicate; preserve the referenced retained record.",
        }
    selected = next(
        (item for item in evidence if item.get("field") not in {"payload_hash", "ledger_hash"}),
        evidence[0],
    )
    return {
        "action": "restore_field" if selected.get("expected") is not None else "quarantine",
        "field": selected.get("field"),
        "expected": selected.get("expected"),
        "observed": selected.get("observed"),
        "explanation": selected.get("explanation"),
    }
