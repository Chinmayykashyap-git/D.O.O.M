# FRONTEND_AUDIT.md — D.O.O.M. UI Step 0 Critique

**Audit Date:** 2026-10-09  
**Viewport targets:** 1920×1080 and 1366×768  
**Auditor:** Antigravity / Team LATVERIAN

---

## 1. TYPOGRAPHY VIOLATIONS

| Location | Current size | Problem |
|---|---|---|
| `.nav-section-label` | 9px | Below minimum; unreadable on projector |
| `.brand-sub` | 8px | Invisible label |
| `.nav-item small` | 8px | Illegible detail text |
| `.nav-count` | 8px | Badge text invisible |
| `.metric-top` | 8px | KPI labels disappear at distance |
| `.metric-card small` | 9px | Detail copy too small |
| `.panel-heading small` | 8px | Kicker line unreadable |
| `.breadcrumb` | 9px | Header navigation too small |
| `.system-status` | 8px | Status text below minimum |
| `.evidence-table td` | 9px | Dense forensic data illegible |
| `.diff-row` | 8px | Reconstruction diff invisible |
| `.timeline-event b/small` | 8px/7px | Timeline unreadable |
| `.footer` | 7px | Footer text non-functional |
| `.reconstruction-summary b` | 7px | Status labels invisible |
| `.unknown-scores span` | 7px | Novelty labels invisible |

**Verdict:** Pervasive sub-12px text throughout. Minimum body must be 13px, minimum label 12px.

---

## 2. UNEXPLAINED NUMBERS

- **"93.1% integrity"** — no formula shown. Formula is `100 × (1 − incidents / records)`. No hover or explanation anywhere.
- **"CRITICAL posture"** — derived from `critical_count > 0` (risk_score ≥ 90) with no visible threshold.
- **Risk scores** (e.g., "95 RISK") — no formula, no tooltip, no breakdown.
- **Confidence %** — shown as a raw number with no calibration context.
- **Novelty score** — shown as a percentage with no distance-metric explanation.
- **Reconstruction counts** — ORIGINAL/REPAIRED/REMOVED/UNRECOVERABLE shown as numbers with no clickable drill-down.

---

## 3. INFORMATION ARCHITECTURE GAPS

### Missing Screens (6)
1. **Route Map** — no geographic visualization of port paths or impossible movements.
2. **Chain of Custody Ledger** — no hash-chain view, no broken-link visualization.
3. **Attack Timeline** — no temporal view of when attacks landed vs were detected.
4. **Unknown Anomaly dedicated screen** — relegated to a sidebar panel in Live Watch.
5. **Evaluation Metrics** — no rendering of `reports/metrics.json` data (precision, recall, F1, confusion matrix).
6. **Tamper Lab** — no interactive record-tampering demonstration.

### Missing Navigation Features
- No command palette (Ctrl+K)
- No keyboard shortcuts or `?` overlay
- No URL-persisted filters or deep-linkable views
- No presentation mode
- No breadcrumb drill-down beyond one level
- No UTC clock (shows static string, not live-updating)
- No WebSocket connection state in header

---

## 4. VISUAL DESIGN PROBLEMS

### Color/Contrast
- **Brass (`#b29a64`)** too faint against panel backgrounds — fails AA on dark panel `#191f1b`.
- **Green (`#92a583`)** used as primary text color is muted, not a premium emerald.
- **Severity marks** (6px dots) — too small, color is the only signal (no icon or text).
- **Critical state styling** barely distinguishable from elevated.
- **Active nav item** — right-edge bar is 2px; invisible on projector.

### Layout
- **Integrity Seal card** — 156px circle is 70% empty space. No ring segmentation by record status. Static, no animation, no click behavior.
- **Threat posture gauge** — plain CSS circle, not a naval radial sweep or meaningful gauge. `OPEN FINDINGS` count repeats the metric strip above.
- **Incident list** — repeated rows with same type (e.g., multiple "PORT SKIP") are not grouped. A juror sees noise, not signal.
- **Record Forensics split** — left case list and right detail are disconnected. No sticky scroll on detail. Evidence table requires horizontal scroll on 1366px.
- **Live Watch** — events are a flat grid, not a smooth live feed. UNKNOWN ANOMALY is a small right-column sidebar, not a distinctive moment.

### Material / Texture
- No brushed-metal CSS texture.
- No riveted-plate effect.
- No blueprint/nautical grid background.
- No clip-path chamfer on panels.
- No hairline brass rules.
- Panels feel generic dark-mode, not authoritative maritime intelligence.

---

## 5. MOTION / ANIMATION

- **No count-up animations** on number load.
- **No "stamp" animation** on Integrity Seal.
- **No slide-in** for live stream events.
- **No pulse** on active WebSocket indicator.
- **Loading spinner** is a plain CSS circle, not themed.
- `prefers-reduced-motion` is handled (good — keep this).

---

## 6. COMPONENT LIBRARY GAPS

No `ui/` component library exists. Everything is inline JSX. Missing:
- `Panel` with chamfer, brass hairline, inner glow
- `StatCard` with count-up animation
- `Badge` (status + severity) with icon + color
- `DataTable` (virtualized, sortable, filterable)
- `EvidenceRow` with contribution bar
- `DiffView` (side-by-side)
- `Gauge` (radial/naval sweep)
- `Seal` (segmented brass ring)
- `Sparkline` (throughput)
- `Timeline` (horizontal/vertical)
- `GraphView` (force/radial related-records)
- `CommandPalette` (Ctrl+K)
- `Drawer` (slide-in panel)
- `Tooltip` (hover explanations for all numbers)
- `Toast` (system events)

---

## 7. ACCESSIBILITY DEFICITS

- `<small>` elements used for content (semantic violation).
- Color is sole severity signal — no icons or text accompany severity marks.
- No ARIA labels on charts (the gauge ring has no role or label).
- Focus ring visible but uses wrong color (`#b8c39e` instead of brass accent).
- UTC clock shows static `new Date().toISOString()` — rendered once, never updates.
- Table headers lack `scope` attributes.

---

## 8. PERFORMANCE CONCERNS

- `App.tsx` is a 974-line monolith — all screens share one re-render cycle.
- No virtualization for incident table (5,000+ records would freeze).
- No lazy loading of heavy screens.
- Evidence table forces horizontal scroll on all viewports under 1400px.
- No `React.memo` or `useMemo` boundaries on list-heavy components.

---

## 9. WHAT'S WORKING (preserve)

- WebSocket auto-reconnect with retry logic is solid.
- API contract (`/api/overview`, `/api/incidents`, `/api/incidents/:id`, `/api/stream`) is clean.
- `types.ts` is well-structured — extend rather than rewrite.
- Filter/sort state on Incidents is logical.
- Reduced-motion handling is correct.
- Error states exist (extend with better design).
- Empty states exist (extend with better design).
- `getJson` utility is clean.

---

## 10. REBUILD PLAN SUMMARY

| Priority | Action |
|---|---|
| P0 | Establish design token file (`theme.ts`) with all palette, type scale, spacing |
| P0 | Lift minimum text size to 12px labels, 13px body, 14px+ interactive |
| P0 | Build `ui/` component library (Panel, Badge, Gauge, Seal, etc.) |
| P1 | Redesign Overview: segmented Integrity Seal SVG, naval gauge, explained numbers |
| P1 | Redesign Incidents: grouped table, severity histogram brush, clustered cases |
| P1 | Redesign Forensics: evidence contribution bars, side-by-side diff, timeline |
| P1 | Redesign Live Watch: smooth event feed, UNKNOWN ANOMALY banner treatment |
| P2 | Add Route Map screen (SVG nautical chart + port arcs) |
| P2 | Add Chain of Custody screen (hash-block ledger) |
| P2 | Add Attack Timeline screen |
| P2 | Add Unknown Anomaly dedicated screen |
| P2 | Add Evaluation Metrics screen (metrics.json via API) |
| P2 | Add Tamper Lab screen |
| P3 | Command palette, keyboard shortcuts, presentation mode |
| P3 | URL-persisted filters, deep links |
| P3 | Playwright E2E tests for all screens |
| P3 | `docs/screenshots/` captures at 1920×1080 |

---

*"EVIDENCE BEFORE ASSERTION. NO SILENT MUTATIONS."*
