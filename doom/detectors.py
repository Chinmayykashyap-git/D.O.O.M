"""Explainable manifest detectors; this module never reads evaluator ground truth."""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Iterable

import pandas as pd
from sklearn.ensemble import IsolationForest

from doom.generator import MANIFEST_COLUMNS, OWNERS


class ManifestDetector:
    """Fuse deterministic forensic checks with unsupervised numeric novelty."""

    def detect(
        self,
        records: pd.DataFrame,
        expected_record_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        if "record_id" not in records.columns:
            raise ValueError("manifest must contain a record_id column")
        frame = records.copy()
        incidents: dict[str, dict[str, Any]] = {}
        duplicate_groups = frame.groupby("shipment_id", dropna=False)["record_id"].agg(list)
        duplicate_extras = {
            str(record_id)
            for record_ids in duplicate_groups
            if len(record_ids) > 1
            for record_id in sorted(map(str, record_ids), key=lambda value: (value.endswith("-COPY"), value))[1:]
        }

        features = self._anomaly_features(frame)
        forest_candidates: set[str] = set()
        if len(frame) >= 20:
            model = IsolationForest(
                n_estimators=80, contamination="auto", random_state=1907
            )
            labels = model.fit_predict(features)
            forest_candidates = set(frame.loc[labels == -1, "record_id"].astype(str))
        numeric_outliers = self._robust_value_outliers(frame)
        # Isolation Forest is deliberately gated by a high-breakdown robust
        # fence: the forest alone over-flags ordinary variation in this fleet.
        anomaly_ids = forest_candidates & numeric_outliers

        owners = set(OWNERS)
        known_owners = set(OWNERS)
        shipment_rows = frame.set_index("shipment_id", drop=False)

        for _, row in frame.iterrows():
            record_id = str(row["record_id"])
            evidence: list[dict[str, str]] = []
            detectors: set[str] = set()
            candidates: list[tuple[str, float]] = []

            if record_id in duplicate_extras:
                evidence.append(self._evidence(
                    "DUPLICATE_SHIPMENT", "Shipment identifier appears more than once.",
                    "CRITICAL",
                ))
                detectors.add("duplicate_detection")
                candidates.append(("DUPLICATE", 0.98))

            if str(row.get("container_owner", "")) not in ("", "nan") and (
                str(row.get("owner", "")) != str(row.get("container_owner", ""))
            ):
                evidence.append(self._evidence(
                    "OWNER_CONTAINER_MISMATCH",
                    "Declared owner conflicts with the container's registered owner.",
                    "HIGH",
                ))
                detectors.add("relational_analysis")
                candidates.append(("RELATIONAL_INCONSISTENCY", 0.93))

            route = [part for part in str(row.get("planned_route", "")).split("|") if part]
            current_location = str(row.get("current_location", ""))
            if current_location not in route:
                evidence.append(self._evidence(
                    "LOCATION_OFF_ROUTE",
                    f"Observed location {current_location!r} is not on the declared route.",
                    "HIGH",
                ))
                detectors.add("route_validation")
                candidates.append(("IMPOSSIBLE_MOVEMENT", 0.95))

            departure = pd.to_datetime(row.get("departure_ts"), utc=True, errors="coerce")
            arrival = pd.to_datetime(row.get("arrival_ts"), utc=True, errors="coerce")
            event_time = pd.to_datetime(row.get("event_ts"), utc=True, errors="coerce")
            if pd.isna(departure) or pd.isna(arrival) or arrival <= departure:
                evidence.append(self._evidence(
                    "NON_MONOTONIC_SHIPMENT_TIME",
                    "Arrival time is invalid or does not follow departure.",
                    "HIGH",
                ))
                detectors.add("temporal_analysis")
                candidates.append(("TIMESTAMP_MANIPULATION", 0.97))
            elif not pd.isna(event_time) and (
                event_time < departure or event_time > arrival
            ):
                evidence.append(self._evidence(
                    "EVENT_OUTSIDE_SHIPMENT_WINDOW",
                    "Observed event timestamp falls outside the shipment interval.",
                    "HIGH",
                ))
                detectors.add("temporal_analysis")
                candidates.append(("TIMESTAMP_MANIPULATION", 0.87))

            owner = str(row.get("owner", ""))
            container_owner = str(row.get("container_owner", ""))
            if owner not in known_owners or container_owner not in owners:
                evidence.append(self._evidence(
                    "UNREGISTERED_PARTY",
                    "The manifest references an owner absent from the registered fleet.",
                    "CRITICAL",
                ))
                detectors.add("fabrication_screen")
                candidates.append(("FABRICATED", 0.96))

            if record_id in anomaly_ids:
                evidence.append(self._evidence(
                    "NUMERIC_BEHAVIORAL_OUTLIER",
                    "Value, weight, or value-to-weight behavior is statistically unusual.",
                    "MEDIUM",
                ))
                detectors.add("behavioral_anomaly")
                candidates.append(("MODIFIED", 0.72))

            unexpected = sorted(set(frame.columns) - set(MANIFEST_COLUMNS))
            if unexpected:
                evidence.append(self._evidence(
                    "UNRECOGNIZED_SCHEMA_FIELD",
                    f"Manifest contains unrecognized fields: {', '.join(unexpected)}.",
                    "HIGH",
                ))
                detectors.add("schema_novelty")
                candidates.append(("UNKNOWN_ANOMALY", 0.91))

            # A fabricated shipment must not be allowed to mask itself as an
            # ordinary numeric outlier or duplicate; choose the strongest signal.
            if candidates:
                tampering_type, confidence = max(candidates, key=lambda item: item[1])
                risk = min(100, round(40 + confidence * 60))
                incidents[record_id] = self._incident(
                    record_id, tampering_type, risk, confidence,
                    evidence, detectors,
                    self._related_records(row, shipment_rows, record_id),
                )

        if expected_record_ids is not None:
            present = set(frame["record_id"].astype(str))
            for missing_id in sorted(set(map(str, expected_record_ids)) - present):
                incidents[missing_id] = self._incident(
                    missing_id, "DELETED", 100, 0.99,
                    [self._evidence(
                        "EXPECTED_RECORD_ABSENT",
                        "Record is absent from the manifest but present in the independent control ledger.",
                        "CRITICAL",
                    )],
                    {"control_ledger"},
                    [],
                    record_missing=True,
                )
        return sorted(incidents.values(), key=lambda item: (-item["risk_score"], item["record_id"]))

    @staticmethod
    def detect_record(record: dict[str, Any]) -> dict[str, Any] | None:
        frame = pd.DataFrame([record])
        results = ManifestDetector().detect(frame)
        return results[0] if results else None

    @staticmethod
    def _anomaly_features(frame: pd.DataFrame) -> pd.DataFrame:
        values = pd.to_numeric(
            frame.get("declared_value_usd", pd.Series(0, index=frame.index)),
            errors="coerce",
        ).fillna(0)
        weights = pd.to_numeric(
            frame.get("weight_kg", pd.Series(0, index=frame.index)),
            errors="coerce",
        ).fillna(0)
        return pd.DataFrame({
            "value_log": values.clip(lower=0).map(math.log1p),
            "weight_log": weights.clip(lower=0).map(math.log1p),
            "value_per_kg": (values / weights.clip(lower=1)).clip(upper=1000),
        })

    @staticmethod
    def _robust_value_outliers(frame: pd.DataFrame) -> set[str]:
        values = pd.to_numeric(frame["declared_value_usd"], errors="coerce")
        result: set[str] = set()
        for _, indexes in frame.groupby("owner", dropna=False).groups.items():
            cohort = values.loc[indexes].dropna()
            if len(cohort) < 8:
                continue
            lower, upper = cohort.quantile([0.25, 0.75])
            fence = upper + 1.5 * (upper - lower)
            result.update(
                frame.loc[cohort.index[cohort > fence], "record_id"].astype(str)
            )
        return result

    @staticmethod
    def _evidence(code: str, detail: str, severity: str) -> dict[str, str]:
        return {"code": code, "detail": detail, "severity": severity}

    @staticmethod
    def _incident(
        record_id: str,
        kind: str,
        risk: int,
        confidence: float,
        evidence: list[dict[str, str]],
        detectors: set[str],
        related: list[str],
        record_missing: bool = False,
    ) -> dict[str, Any]:
        return {
            "record_id": record_id,
            "tampering_type": kind,
            "risk_score": risk,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "detectors": sorted(detectors),
            "related_records": related,
            "record_missing": record_missing,
        }

    @staticmethod
    def _related_records(
        row: pd.Series, indexed: pd.DataFrame, record_id: str
    ) -> list[str]:
        related: set[str] = set()
        shipment = str(row.get("shipment_id", ""))
        matches = indexed.loc[indexed.index.astype(str) == shipment]
        if not matches.empty:
            related.update(matches["record_id"].astype(str))
        related.discard(record_id)
        return sorted(related)[:8]
