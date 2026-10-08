# Regression targets

Thresholds are conservative floors derived from the measured multi-seed synthetic evaluation in [`reports/metrics.json`](./reports/metrics.json). They are regression guards, not production service-level objectives.

| Metric | Measured mean | Minimum accepted |
|---|---:|---:|
| Known precision | 1.0000 | 0.9500 |
| Known recall | 1.0000 | 0.9500 |
| Known F1 | 1.0000 | 0.9500 |
| Known type accuracy | 1.0000 | 0.9000 |
| Reconstruction status accuracy | 1.0000 | 0.9500 |
| Reconstruction field accuracy | 1.0000 | 0.9800 |
| Reconstruction field coverage | 0.8750 | 0.8000 |

A regression test enforces every listed floor against the checked-in measured evaluation artifact. Holdout results are reported independently and are not used to choose or tune these thresholds.
