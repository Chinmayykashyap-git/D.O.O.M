# Approach dossier

## Design objective

Demonstrate a defensible local forensic flow rather than claim an oracle can infer lost truth. Every detector finding carries an evidence code, detail, severity, detector provenance, score, and confidence. Every observed or ledger-expected record receives an explicit reconstruction disposition.

## Detection approach

1. **Duplicate:** count repeated shipment IDs and flag only extra rows, retaining a deterministic canonical record.
2. **Relational consistency:** compare the declared owner against the registered container owner.
3. **Route validation:** check that the observed location exists on the declared itinerary.
4. **Temporal analysis:** parse UTC timestamps, verify arrival follows departure, and ensure event time lies within the shipment interval.
5. **Fabrication screen:** check parties against the generated known-fleet registry.
6. **Behavioral novelty:** fit a seeded Isolation Forest on log value, log weight, and value/weight features; use its outlier indication as supporting evidence.
7. **Deletion:** compare record IDs with the independent expected-ID ledger; never infer or recover deleted payload fields from attack labels.
8. **Open-set streaming:** reject unrecognized record fields as schema novelty. The `policy_epoch` streaming attack does not exist in batch injection.

Scores reflect detector rule confidence and evidence severity; they are operational prioritization values, not calibrated probabilities. Confidence is kept distinct from risk. Fused findings retain every supporting observation and detector, and the strongest supported rule selects the displayed class.

## Reconstruction doctrine

- `ORIGINAL`: no supported finding.
- `REPAIRED`: a value can be restored from independently corroborated manifest evidence. The change and reason are recorded.
- `REMOVED`: a high-confidence fabricated row or duplicate extra is excluded from the reconstructed view.
- `UNRECOVERABLE`: tampering is supported but the authentic value is not evidenced, or expected record contents are absent. The row is not silently rewritten.

The clean reference and hidden injection log do not participate in detection or reconstruction. Exact restoration of a deleted row is impossible with only its identifier; the system exposes this limitation instead of pretending otherwise.

## Evaluation discipline

The demonstration computes record-level precision, recall, F1, and attack-type accuracy by comparing detector output to the hidden synthetic injection log only after detection. It reports false positives and false negatives and explicitly labels the result synthetic. It does not present an invented benchmark or imply field effectiveness.

## Demonstration boundaries

All names, shipments, times, amounts, routes, anomalies, and results are synthetic. The route catalog is intentionally small. The model is fit per batch and does not learn a persistent production baseline. The stream is simulated for product demonstration; it has no external broker, authenticated producer, durable queue, or back-pressure policy beyond bounded client queues.
