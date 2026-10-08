# Decisions log

| Phase | Decision | Alternatives considered | Reason |
|---|---|---|---|
| 0 | Initialize a local Git repository because the supplied workspace was not a Git repository. | Skip requested phase commits; ask the user to create a repository. | The request explicitly requires a commit at the end of every phase and explicitly says to work around setup blockers. |
| 0 | Treat the 97.72% surface-classifier accuracy as a leakage warning, not a pass, and report ROC AUC alongside accuracy. | Quote accuracy alone; call 0.8663 AUC “near chance.” | Positive labels are only 3% of the sample, so accuracy hides substantial class imbalance. |
| 0 | Preserve synthetic-run metrics but label all scores as synthetic, seed-specific observations. | Present them as production performance or suppress baseline measurements. | Neither interpretation is supported by the test setup. |
| 1 | Use synthetic witness tables, a canonical field hash, and a sequence-linked ledger as independent-but-synthetic corroboration. | Claim external carrier/customs trust without real sources. | No external feeds or real signed source systems are available in this offline demo. |
| 1 | Make attack generation a fixed seeded, stratified suite of subtle and obvious cases; use realistic identifiers for all generated entries. | Depend on malformed suffixes and conspicuous outliers. | Surface shortcuts invalidate evaluation; stable IDs and realistic distributions are more useful. |
| 2 | Keep detector output probability estimates explicitly empirical and fit calibration using only non-holdout synthetic seeds. | Describe hand-set rule confidence as calibrated probability. | Scores without a measured calibration process must not be called calibrated probabilities. |
| 3 | Keep holdout attack generators and holdout metrics in separate modules and files; never import holdouts in training/tuning paths. | Tune a novelty threshold against holdout results. | Holdout must remain an honest evaluation set. |
| 4 | Never reconstruct a missing value from its evaluator-side clean copy; use event/witness records, otherwise report unrecoverable. | Restore from the hidden attack log. | Evaluation truth is not an operational witness. |
| 5 | Keep the stream bounded and stateful in process, recording late-event classification and measured per-event latency. | Describe WebSocket fan-out alone as a production streaming system. | The local demo has no external broker, distributed state, or high-availability guarantee. |
| 7 | Reduce navigation to five operational screens plus custody and tamper-demo surfaces. | Retain the first ten-module navigation. | The requested forensic workflows deserve depth rather than a broad set of shallow panels. |
| 8 | Keep service and frontend loopback-only, fail explicitly for unavailable dependencies/ports, and provide a working CLI fallback. | Bind publicly or silently switch ports. | Local security and predictable demo instructions are preferable. |
