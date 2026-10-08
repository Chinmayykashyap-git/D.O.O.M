# Autonomous level-up progress

## Current phase
Phase 6 — Multi-seed evaluation and regression targets: **complete**.
Next: Phase 3 — Independent holdout attacks and open-set evaluation.

## Completed phases
- Phase 0: baseline tests (6 passed), measured seed-1907 2,400-record run (168 attacks; 168 TP; 0 FP; 0 FN), generator surface-leakage test (97.72% accuracy, 0.8663 ROC AUC), and three repeated same-seed byte-hash comparisons (all identical). Audited missing coverage tooling and test gaps.
- Phase 1: deterministic realistic generator, 12 attack families, separate evaluator-only oracle SQLite, ID/sequence/hash control ledger, owner/container/vessel/customs/movement witnesses, structured evidence and counterfactuals, auditable reconstruction diffs, per-type/confusion/reconstruction metrics, and UI evidence-contract alignment. Standard seed 1907 produced 168 injected attacks, 168 TP, 0 FP, 0 FN, 1.0 type accuracy, 1.0 status accuracy (168/168), and 1.0 field accuracy (210/210). Five surface-only balanced splits using the suite's RF120 configuration produced mean accuracy 0.5064 and mean ROC AUC 0.4837. These are synthetic in-distribution results, not a deployment claim.
- Phase 2: fitted transparent logistic calibration models on seeds 113/401/809/1301; evaluated on disjoint seeds 1501/1907. Detection Brier score was 0.000099 raw and 0.000000 rounded calibrated, ECE 0.002351 raw and 0.000093 calibrated; type accuracy was 1.0, multiclass Brier 0.000061, and top-label ECE 0.006851. Added reliability bins, calibrated probabilities to batch incidents, and exposed class estimates in incident UI. One-factor ablations are in `reports/ablation.json`; removing control-ledger evidence reduced recall to 0.9167, while removing relational checks lowered type accuracy to 0.7143. Results only measure this synthetic generator.
- Phase 4: reconstruction now accepts operational witnesses and the control ledger. Missing sequences gain a provenance-labelled partial field recovery from movement, schedule, owner/container registry, customs, and ledger evidence, while remaining `UNRECOVERABLE` if a complete row cannot be proven. Reconstruction evaluation reports status accuracy, field accuracy and coverage by attack type and disposition; removals are scored as removals rather than as field repairs. The standard 2,400-row seed-1907 gate produced 168/168 expected dispositions, 392/392 correct attempted target fields, and 87.50% field coverage overall. Deleted-row recovery covered 238/294 target fields (80.95%); unsupported fields were not guessed. Full tests: 11 passed, with one upstream Starlette/httpx deprecation warning.
- Phase 6: `doom.evaluation` now evaluates five fixed seeds (19, 41, 75, 2222, 31415), 1,200 records each, disjoint from the calibration training and evaluation seeds. `reports/metrics.json` keeps the known evaluation and three-case isolated holdout in separate sections; `reports/EVAL.md` reports per-attack precision/recall/F1, confusion matrix, reconstruction accuracy/coverage by attack and disposition, mean ± standard deviation, and Phase 2 calibration/ablation results. `TARGETS.md` and a regression test enforce conservative floors derived from those results. Measured known means: precision/recall/F1/type accuracy/status accuracy/attempted-field accuracy = 1.0; field coverage = 0.875. Holdout: 3 TP, 0 FP, 0 FN, explicitly labeled a narrow smoke test. Full tests: 12 passed, with one upstream Starlette/httpx deprecation warning.

## Open issues
- Streaming latency/throughput and late/out-of-order semantics have not been measured or implemented.
- UI remains broader than the requested focused workflows and has no record-tampering interaction or custody screen.
- Final demo, make targets, coverage, frontend tests, limitations, and timed demo script remain outstanding.
- Phase 3 holdout-family code and a smoke report are present but uncommitted; the families have not been trained on, but holdout isolation tests and novelty/similarity output remain to be completed in the mandated order.
- Last observed full test run: 11 passed, with one Starlette/httpx upstream deprecation warning.

## Next step
Implement the mandated Phase 6 multi-seed evaluation report and regression targets. Keep the holdout set fully separate from fitting and tuning.

## Commit log
| Phase | Commit |
|---|---|
| 0 | `1f1b40b` |
| 1 | `487f238` |
| 2 | `f88dcef` |
| 4 | `be2a113` |
| 6 | pending |
