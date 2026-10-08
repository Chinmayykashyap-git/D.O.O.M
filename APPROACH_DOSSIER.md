# Approach dossier

## Design objective

Demonstrate a defensible local forensic flow rather than claim an oracle can infer lost truth. Every detector finding carries an evidence code, detail, severity, detector provenance, score contribution, and confidence. Every observed or ledger-expected record receives an explicit reconstruction disposition.

## Detection approach

1. **Duplicates:** group by shipment, compare exact/near payloads, and use the expected record ID/sequence ledger to identify the anchored row.
2. **Ledger integrity:** recompute canonical payload and sequence-linked hashes and compare IDs, sequences, and digests with a separately generated control ledger.
3. **Relational consistency:** compare owner, container, and vessel references against independent generated registries and schedules.
4. **Route validation:** derive great-circle itinerary length, compare schedule/port logs, and verify observed waypoints against event-sourced movement history.
5. **Temporal analysis:** verify ordered UTC timestamps and plausible route transit for the vessel speed class.
6. **Customs/value consistency:** derive `declared_value_usd = quantity × unit_price_usd` and compare with an independent synthetic customs entry.
7. **Deletion/fabrication:** compare record IDs and sequence with the expected ledger; never infer or recover deleted values from attack labels.
8. **Open-set streaming:** flag unrecognized fields with schema-novelty evidence. `policy_epoch` exists in the stream demo but not in batch injection.

Evidence contributions and `type_probabilities` are rule strengths, not probabilities. The demo also reports `detection_probability` and `type_probabilities_calibrated`, produced by standardized logistic models fitted on synthetic seeds 113/401/809/1301 and evaluated on separate seeds 1501/1907. On those two evaluation seeds, detection Brier score changed from 0.000099 (raw strongest-rule score) to 0.000000 (calibrated, rounded), ECE from 0.002351 to 0.000093, and type accuracy was 1.0; full results are in `reports/calibration.json`. This demonstrates calibration only within this generator's synthetic evidence distribution. Confidence remains distinct from incident risk.

## Reconstruction doctrine

- `ORIGINAL`: no supported finding.
- `REPAIRED`: a value can be restored from independently corroborated evidence. The witness, changed field, before/after values, and reason are recorded.
- `REMOVED`: a high-confidence fabricated row or duplicate extra is excluded from the reconstructed view.
- `UNRECOVERABLE`: tampering is supported but authentic content is not evidenced, or an expected payload is absent. The system does not silently rewrite it.

The clean reference and hidden attack log do not participate in detection or reconstruction. Exact restoration of a deleted payload is impossible with only its identifier; the system exposes this limitation rather than pretending otherwise.

## Evaluation discipline

The demonstration computes record-level and per-type detection, type confusion, and reconstruction measures by comparing the detector output to the isolated synthetic oracle only after detection. It reports false positives and false negatives and labels metrics as synthetic. These scores describe a controlled, seed-specific scenario—not production effectiveness.

## Demonstration boundaries

All names, shipments, times, amounts, routes, hashes, customs entries, witnesses, anomalies, and results are synthetic. The route catalog is intentionally small. The control ledger is not cryptographically signed; its hash chain alone does not protect against an attacker who can replace both data and ledger. The stream is a local simulation without an external broker, authenticated producer, durable queue, or high-availability guarantees.

The fixed seed-1907 one-factor ablation retained 1.0 F1 with all detector groups enabled. Removing the control ledger reduced recall to 0.9167; removing duplicate detection, relational analysis, and temporal analysis reduced type accuracy to 0.8333, 0.7143, and 0.9167 respectively. Several checks are redundant on these injected cases; see `reports/ablation.json`. This diagnostic does not establish general detector value outside this suite.
