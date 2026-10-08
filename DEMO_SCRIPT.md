# Three-minute D.O.O.M. demo script

Start the full demo before presenting:

```powershell
python -m doom.demo
```

If network access or browser presentation is unavailable, first generate a
recording with `python -m doom.demo --no-server`, then replay it with
`.\make.ps1 demo-offline`.

| Time | Operator action | Narration |
|---|---|---|
| 0:00–0:20 | Open the dashboard overview at <http://127.0.0.1:8000>. | “This is D.O.O.M.—Detection, Observation & Operational Manifest Reconstruction. It treats a manifest as evidence to verify, not as truth to assume.” |
| 0:20–0:45 | Point out the manifest integrity seal, threat posture, and incident summary. | “The overview reads the local API. Its counts and evaluations come from the current seeded run; aggregate evaluation claims are in the generated metrics report.” |
| 0:45–1:20 | Open an incident and show detector evidence, expected versus observed values, related records, and counterfactual. | “A finding is explainable: which invariant failed, which detector supplied the evidence, and what the system expected compared with what arrived.” |
| 1:20–1:50 | Show the reconstruction disposition and before/after explanation. | “D.O.O.M. distinguishes original, repaired, removed, and unrecoverable records. It only repairs fields supported by independent witnesses; partial evidence is not presented as a complete recovery.” |
| 1:50–2:25 | Open Live Watch and wait for the schema-extension event. | “The live feed adds a field absent from the batch schema. The detector does not force this into a known attack label; it raises UNKNOWN ANOMALY and shows the invariant and novelty evidence.” |
| 2:25–2:45 | Show the event evidence and its reconstruction outcome. | “An unknown alert is not a claim that the payload can be restored. The result remains explicit about what can and cannot be proven.” |
| 2:45–3:00 | Show [`reports/EVAL.md`](./reports/EVAL.md) or `reports/metrics.json`. | “The evaluation separates known attacks from holdouts, reports reconstruction coverage, and states where the system performs poorly. Every result is synthetic and the holdout is intentionally small.” |

Stop the local server with **Ctrl+C** after the presentation.
