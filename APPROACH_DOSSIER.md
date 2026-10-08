# Approach dossier

## Design objective

D.O.O.M. demonstrates a defensible local forensic flow rather than claiming an
oracle can infer lost truth. Each finding carries detector provenance,
evidence, score contribution, confidence, and a counterfactual. Every observed
or ledger-expected record receives an explicit reconstruction disposition.

## Detection approach

- **Duplicates:** compare exact and near duplicates and use the expected ID and
  sequence ledger to identify the anchored row.
- **Ledger integrity:** recompute canonical payload and sequence-linked hashes
  and compare IDs, sequences, and digests with the separate control ledger.
- **Relational consistency:** check owner, container, and vessel references
  against synthetic registries and schedules.
- **Route validation:** compare derived route geometry and observed waypoints
  with schedule and movement-event witnesses.
- **Temporal analysis:** verify UTC timestamp ordering and plausible transit
  times for the declared speed class.
- **Customs/value consistency:** derive declared value from quantity and unit
  price and compare against a synthetic customs entry.
- **Deletion/fabrication:** compare manifest IDs and sequences with the control
  ledger; never recover deleted values from evaluator labels.
- **Open-set analysis:** preserve the `UNKNOWN ANOMALY` label and expose broken
  invariants, novelty score, and nearest known evidence signature.

Rule contributions and raw type hypotheses are not probabilities. The batch
demo also applies separately trained logistic calibration artifacts whose
training and evaluation seeds are documented in
[`reports/metrics.json`](./reports/metrics.json). The isolated holdout is not
used for fitting or threshold selection. Consult the measured reliability
curve and ablation table in [`reports/EVAL.md`](./reports/EVAL.md); do not
interpret synthetic calibration as field validation.

## Reconstruction doctrine

- `ORIGINAL`: no supported change is required.
- `REPAIRED`: independent evidence supports a restored field. The evidence,
  field, before/after values, and explanation are retained.
- `REMOVED`: a supported fabricated row or duplicate extra is excluded from
  the reconstructed view, with the retained-row justification recorded.
- `UNRECOVERABLE`: tampering is supported but authentic content is not
  sufficiently evidenced, or the expected payload is absent.

The clean reference and hidden attack log do not participate in detection or
reconstruction. A missing row cannot be fully restored if independent sources
do not attest all required values. Partial field recovery remains explicitly
partial and does not change the disposition to `REPAIRED`.

## Evaluation discipline

The known multi-seed evaluator and the isolated holdout evaluator compare
outputs to the synthetic oracle only after analysis. Known and holdout results
remain separately reported. The numeric source of truth is
[`reports/metrics.json`](./reports/metrics.json), rendered in
[`reports/EVAL.md`](./reports/EVAL.md). The three holdout families have only
one generated example each; their result is a narrow smoke test, not evidence
of generalized open-set performance.

## Demonstration boundaries

All manifests, names, routes, hashes, witness rows, attacks, and outcomes are
synthetic. Witnesses are generated with the clean manifest and are not
authenticated carrier, customs, or port feeds. The control ledger is not
signed; an attacker able to replace both data and ledger can defeat the
assumption. Novelty is a fixed evidence-signature distance rather than a
learned general-purpose novelty detector.

The live feed is in-process with bounded recent-event and client-queue state,
SQLite event history, and WebSocket fan-out. It has no external broker,
distributed state, authenticated producer, durable queue guarantee, or
high-availability behavior. For measured latency/throughput and skipped event
semantics, see [`LIMITATIONS.md`](./LIMITATIONS.md) and the corresponding
stream metrics in the evaluation report when present.

The operator UI reads the local API for its overview, incident register, batch
case detail, and stream events. A streaming-only incident can be inspected from
its WebSocket evidence but does not claim a batch reconstruction decision.
