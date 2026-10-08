# Autonomous level-up progress

## Current phase
Phase 2 — Calibrated evidence fusion and ablation: **complete**.
Next: Phase 3 — Independent holdout attacks and open-set evaluation.

## Completed phases
- Phase 0: baseline tests (6 passed), measured seed-1907 2,400-record run (168 attacks; 168 TP; 0 FP; 0 FN), generator surface-leakage test (97.72% accuracy, 0.8663 ROC AUC), and three repeated same-seed byte-hash comparisons (all identical). Audited missing coverage tooling and test gaps.
- Phase 1: deterministic realistic generator, 12 attack families, separate evaluator-only oracle SQLite, ID/sequence/hash control ledger, owner/container/vessel/customs/movement witnesses, structured evidence and counterfactuals, auditable reconstruction diffs, per-type/confusion/reconstruction metrics, and UI evidence-contract alignment. Standard seed 1907 produced 168 injected attacks, 168 TP, 0 FP, 0 FN, 1.0 type accuracy, 1.0 status accuracy (168/168), and 1.0 field accuracy (210/210). Five surface-only balanced splits using the suite's RF120 configuration produced mean accuracy 0.5064 and mean ROC AUC 0.4837. These are synthetic in-distribution results, not a deployment claim.
- Phase 2: fitted transparent logistic calibration models on seeds 113/401/809/1301; evaluated on disjoint seeds 1501/1907. Detection Brier score was 0.000099 raw and 0.000000 rounded calibrated, ECE 0.002351 raw and 0.000093 calibrated; type accuracy was 1.0, multiclass Brier 0.000061, and top-label ECE 0.006851. Added reliability bins, calibrated probabilities to batch incidents, and exposed class estimates in incident UI. One-factor ablations are in `reports/ablation.json`; removing control-ledger evidence reduced recall to 0.9167, while removing relational checks lowered type accuracy to 0.7143. Results only measure this synthetic generator.

## Open issues
- No independent holdout-attack module or holdout-family evaluation exists yet.
- Streaming latency/throughput and late/out-of-order semantics have not been measured or implemented.
- Evaluation still lacks a reproducible five-seed report and regression targets.
- UI remains broader than the requested focused workflows and has no record-tampering interaction or custody screen.
- Final demo, make targets, coverage, frontend tests, limitations, and timed demo script remain outstanding.
- Last observed test run: 9 passed, with one Starlette/httpx upstream deprecation warning.

## Next step
Implement calibration without fitting to holdout families, measure held-out calibration reliability, and report ablation results. Preserve evidence provenance and make calibration claims auditable.

## Commit log
| Phase | Commit |
|---|---|
| 0 | `1f1b40b` |
| 1 | `487f238` |
| 2 | pending |
