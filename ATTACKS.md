# Batch attack catalog

The seeded batch injector creates twelve attack families. The evaluator-only oracle records attack labels and original values in a database separate from the operator evidence store. Neither labels nor original values are detector inputs.

| Family | Injected behavior | Primary evidence | Reconstruction policy |
|---|---|---|---|
| `MODIFIED_VALUE` | Alters a declared amount, quantity, or price while keeping the record plausible. | Payload hash, quantity/price formula, customs witness. | Repair only when independent customs/formula evidence supplies the corrected amount; otherwise unrecoverable. |
| `DELETED` | Removes an expected manifest row. | Missing ID/sequence in control ledger. | Unrecoverable without a separate payload witness. |
| `DUPLICATE_EXACT` | Adds an exact copy under another plausible row identity. | Repeated shipment/payload and ledger sequence/hash. | Remove the unanchored duplicate. |
| `DUPLICATE_NEAR` | Adds a slightly changed copy of an existing shipment. | Shipment grouping, payload similarity, ledger witness. | Remove only when evidence identifies an unanchored extra. |
| `FABRICATED` | Adds an otherwise plausible row not present in the anchored ID ledger. | Unregistered ID and missing control-ledger entry. | Remove the unsupported row. |
| `TIMESTAMP_SHIFT` | Changes an event or schedule timestamp. | Payload hash, schedule, time-window evidence. | Repair only from a corroborating schedule/event witness. |
| `TELEPORTATION` | Moves the observed location away from supported movement history. | Port log, route, and movement-event disagreement. | Restore only from supported event evidence. |
| `PORT_SKIP` | Alters route/event sequencing to omit a scheduled stop. | Route schedule and ordered port-event witnesses. | Repair only if the independent schedule determines the route. |
| `NEGATIVE_TRANSIT` | Produces impossible temporal ordering or transit. | UTC ordering and route-distance/speed constraints. | Unrecoverable absent a source schedule value. |
| `RELATIONAL_ORPHAN` | Breaks an owner/container relationship. | Owner and container registries. | Restore the corroborated registered owner when available. |
| `VESSEL_MISMATCH` | Associates a shipment with an inconsistent vessel/schedule. | Vessel registry and schedule witness. | Unrecoverable absent a trusted assignment source. |
| `SLOW_DRIFT` | Gradually changes plausible values across repeated observations. | Customs/formula constraints and ledger hash. | Restore only with an independent customs witness. |

## Scope and limits

These are controlled synthetic transformations, not a complete taxonomy of maritime fraud. A detection rule is not proof of malicious intent. A fabricated ledger, colluding witnesses, or compromised source credentials can defeat the assumptions. See [LIMITATIONS.md](./LIMITATIONS.md) when available for the operational threat model and measured evaluation boundaries.
