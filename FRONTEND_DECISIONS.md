# D.O.O.M. FRONTEND DECISIONS LOG
**Team LATVERIAN — Cargo Manifest Forensic Platform**

## 1. Aesthetic Direction & Design System
- **Philosophy:** Sovereign naval command center aesthetic inspired by Victor von Doom. Industrial, forensic, precise, authoritative, maritime.
- **Palette Tokens (`src/theme.ts` & `src/styles.css`):**
  - Dark Iron `#0B0E0D`, Panel `#121816`, Raised `#18211E`
  - Doom Green `#0F3D2E`, Emerald `#1F7A5A` / `#3FB68A`
  - Oxidized Steel `#7C8A87`, Brass `#B8963E` / bright `#D9C98F`, Ivory `#EDE6D3`
  - Amber `#C98A2B` (elevated)
  - **Crimson `#B3262B` strictly reserved for critical incidents, broken hash links, and tampered records.**
- **Typography:**
  - Display: Classical engraved display serif for titles and key numerals (Cinzel/Playfair display aesthetic).
  - Body: High-legibility grotesk (Inter / System Grotesk), strictly minimum 12px for micro-labels, 14px for body.
  - Monospace: JetBrains Mono / IBM Plex Mono for digests, hashes, container IDs, coordinates, and formulas. Tabular figures (`tnum`) enabled on all numerical data.
- **Surface Materials:**
  - Chamfered corner panels (`clip-path` bevels).
  - Brushed steel hairline borders (`1px solid rgba(184, 150, 62, 0.2)`).
  - Subtle nautical chart coordinate grid in background (`radial-gradient` + fine grid rules).
  - High-contrast projector-ready Presentation Mode toggle (`Ctrl+P`).

## 2. Architecture & Data Integration
- **Strict Hard Constraint: 100% Real API Data.**
  - Zero mock data or fabricated numbers in production views.
  - Consumes `/api/overview`, `/api/incidents`, `/api/incidents/:id`, `/api/reconstruction`, `/api/routes`, and the WebSocket stream at `/api/stream` (with `/api/stream/events` bootstrap fallback).
  - Mathematical derivations (Integrity score, Threat Posture, Calibrated Confidence, Novelty distance) have transparent hover cards/tooltips exposing formula inputs and source evidence.
- **Routing & Navigation:**
  - 10 distinct, deep-linkable views via React Router:
    1. `/` — Overview (Hero Integrity Seal, Threat Posture gauge, KPI strip, attack breakdown, incident summary)
    2. `/incidents` — Incident Register (multi-filter, search, risk/confidence sorting, CSV export)
    3. `/forensics` — Record Forensics (evidence matrix, counterfactual callouts, side-by-side reconstruction diff, linked records graph/list, audit timeline)
    4. `/live` — Live Watch (real-time WebSocket feed, pause/resume, latency telemetry, streaming unknown anomaly alerts)
    5. `/route-map` — Route Map (nautical chart projection with port nodes and impossible transit vectors)
    6. `/custody` — Chain of Custody (hash-linked ledger with broken link detection and jump-to-break action)
    7. `/timeline` — Attack Timeline (landed vs detected time, detection lag, hash-chain overlays)
    8. `/anomaly` — Unknown Anomaly Analysis (open-set novelty score distribution, invariant violation matrices, nearest-known comparison)
    9. `/metrics` — Evaluation Metrics (precision, recall, F1, latency, ablation, reproducibility command)
    10. `/tamper-lab` — Tamper Demonstration Lab (interactive injection, real-time detector firing, automated reconstruction diff)
    - Bonus `/dev/components` — Living design system component gallery.
- **Global Command Palette:**
  - Accessible via `Ctrl+K` or `Cmd+K`.
  - Instant navigation across all 10 screens and direct search for incident record IDs and attack categories.
- **Keyboard Help Overlay:**
  - Accessible via `?` key. Focus management and `Escape` support throughout.

## 3. Verification & Compliance
- `tsc -b` compiles without errors.
- `vite build` bundles production assets cleanly (`dist/` directory generated).
- Frontend Vitest suite (`npm test`) passes 100% (4/4 tests).
- Backend Pytest suite (`python -m pytest`) passes 100% (15/15 tests).

