import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Anchor, ArrowDownRight, ArrowUpRight, Bell, Boxes, ChevronDown,
  ChevronRight, CircleAlert, Clock3, Crosshair, Database, FileSearch,
  Fingerprint, Gauge, Globe2, LayoutDashboard, Radio, RefreshCw,
  Route, ScanEye,   Search, Shield, ShieldCheck, ShieldEllipsis,
  SlidersHorizontal, Sparkles, X,
} from "lucide-react";

type Evidence = {
  detector_id: string;
  evidence_code: string;
  record_ids: string[];
  field: string;
  expected: unknown;
  observed: unknown;
  score_contribution: number;
  severity: string;
  explanation: string;
};
type Incident = {
  record_id: string; tampering_type: string; risk_score: number;
  confidence: number; evidence: Evidence[]; detectors: string[];
  related_records: string[]; record_missing?: boolean;
  type_probabilities?: Record<string, number>;
  counterfactual?: string;
};
type RecordRow = Record<string, string | number | null>;
type Decision = {
  record_id: string; status: string; explanation: string;
  changes: { field: string; from: string; to: string }[];
  tampering_type: string | null;
};
type Overview = {
  record_count: number; incident_count: number; critical_count: number;
  integrity_score: number; reconstruction_counts: Record<string, number>;
  metrics: Record<string, number | string>; stream_status: string;
};
type LiveEvent = {
  event_id: string; timestamp: string; record_id: string; status: string;
  incident: Incident | null; record: RecordRow;
};
type ModuleKey = "overview" | "integrity" | "incidents" | "forensics" |
  "reconstruction" | "timeline" | "routes" | "stream" | "unknown" | "metrics";

const NAV: { key: ModuleKey; label: string; icon: typeof Activity; group: string }[] = [
  { key: "overview", label: "Command overview", icon: LayoutDashboard, group: "COMMAND" },
  { key: "integrity", label: "Manifest integrity", icon: ShieldCheck, group: "INTELLIGENCE" },
  { key: "incidents", label: "Active incidents", icon: CircleAlert, group: "INTELLIGENCE" },
  { key: "forensics", label: "Record forensics", icon: FileSearch, group: "INTELLIGENCE" },
  { key: "reconstruction", label: "Reconstruction", icon: Boxes, group: "INTELLIGENCE" },
  { key: "timeline", label: "Attack timeline", icon: Clock3, group: "INTELLIGENCE" },
  { key: "routes", label: "Route intelligence", icon: Route, group: "OPERATIONS" },
  { key: "stream", label: "Live watch", icon: Radio, group: "OPERATIONS" },
  { key: "unknown", label: "Unknown anomaly", icon: Sparkles, group: "OPERATIONS" },
  { key: "metrics", label: "Evaluation metrics", icon: Gauge, group: "SYSTEM" },
];

const titleFor = (key: ModuleKey) => NAV.find((item) => item.key === key)?.label ?? "Command overview";
const fmt = (value: number | undefined) => value == null ? "—" : value.toLocaleString("en-US");
const pretty = (value: string) => value.replaceAll("_", " ");

export default function App() {
  const [active, setActive] = useState<ModuleKey>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [reconstructed, setReconstructed] = useState<RecordRow[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [routes, setRoutes] = useState<{ ports: { code: string; name: string; latitude: number; longitude: number }[] } | null>(null);
  const [live, setLive] = useState<LiveEvent[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [detail, setDetail] = useState<{ incident: Incident | null; record: RecordRow | null; reconstruction: Decision | null; timeline: { event: string; time: string | null }[] } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [o, i, r, d, m, p] = await Promise.all([
        fetch("/api/overview"), fetch("/api/incidents?limit=500"),
        fetch("/api/records?limit=1000"), fetch("/api/reconstruction?limit=5000"),
        fetch("/api/reconstruction/manifest?limit=5000"), fetch("/api/routes"),
      ]);
      for (const response of [o, i, r, d, m, p]) if (!response.ok) throw new Error(`API returned ${response.status}`);
      const [overviewData, incidentData, recordData, decisionData, manifestData, portData] = await Promise.all([
        o.json() as Promise<Overview>, i.json() as Promise<Incident[]>,
        r.json() as Promise<RecordRow[]>, d.json() as Promise<Decision[]>,
        m.json() as Promise<RecordRow[]>,
        p.json() as Promise<{ ports: { code: string; name: string; latitude: number; longitude: number }[] }>,
      ]);
      setOverview(overviewData); setIncidents(incidentData); setRecords(recordData);
      setDecisions(decisionData); setReconstructed(manifestData); setRoutes(portData); setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach the local evidence service.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 30_000); return () => window.clearInterval(timer); }, [refresh]);

  useEffect(() => {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/api/stream`);
    socket.onmessage = (message: MessageEvent<string>) => {
      try { const event = JSON.parse(message.data) as LiveEvent; setLive((items) => [event, ...items.filter((item) => item.event_id !== event.event_id)].slice(0, 40)); }
      catch { setError("A live event could not be parsed."); }
    };
    socket.onerror = () => setError("Live watch connection is unavailable; retrying automatically.");
    return () => socket.close();
  }, []);

  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    let cancelled = false;
    fetch(`/api/incidents/${encodeURIComponent(selected.record_id)}`)
      .then((response) => { if (!response.ok) throw new Error(`Evidence lookup failed (${response.status})`); return response.json(); })
      .then((data) => { if (!cancelled) setDetail(data); })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Evidence lookup failed."); });
    return () => { cancelled = true; };
  }, [selected]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return incidents.filter((item) => !term || `${item.record_id} ${item.tampering_type}`.toLowerCase().includes(term));
  }, [incidents, query]);
  const topGroups = [["COMMAND"], ["INTELLIGENCE"], ["OPERATIONS"], ["SYSTEM"]];
  const incidentCount = overview?.incident_count ?? 0;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Shield size={22} strokeWidth={1.6} /><span>V</span></div>
          <div><div className="brand-name">D.O.O.M.<sup>™</sup></div><div className="brand-sub">LATVERIAN INTELLIGENCE</div></div>
        </div>
        <div className="nav-section-label">OPERATIONS CONSOLE</div>
        {topGroups.map(([group]) => (
          <div className="nav-group" key={group}>
            <div className="nav-group-label">{group}</div>
            {NAV.filter((item) => item.group === group).map(({ key, label, icon: Icon }) => (
              <button className={`nav-item ${active === key ? "active" : ""}`} key={key} onClick={() => setActive(key)}>
                <Icon size={16} strokeWidth={1.7} /><span>{label}</span>
                {key === "incidents" && incidentCount > 0 && <span className="nav-count">{incidentCount}</span>}
                {key === active && <span className="nav-active-line" />}
              </button>
            ))}
          </div>
        ))}
        <div className="sidebar-bottom">
          <div className="side-seal"><Fingerprint size={16} /><span>SECURE LOCAL INSTANCE</span><span className="seal-led" /></div>
          <div className="operator"><div className="operator-avatar">L</div><div><b>LATVERIAN</b><span>FORENSICS DIVISION</span></div><ChevronDown size={14} /></div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb"><span>DOOM INTELLIGENCE</span><ChevronRight size={13} /><b>{titleFor(active).toUpperCase()}</b></div>
          <div className="top-actions"><div className="system-status"><span className="status-dot" />SYSTEM NOMINAL</div><div className="top-divider" /><button className="icon-button" aria-label="Refresh evidence" onClick={() => void refresh()}><RefreshCw size={16} /></button><button className="icon-button notification" aria-label="Active alerts" onClick={() => setActive("incidents")}><Bell size={17} />{incidentCount > 0 && <i />}</button><div className="utc-clock"><span>UTC</span>{new Date().toISOString().slice(11, 19)}</div></div>
        </header>

        <div className="workspace">
          {error && <div className="error-banner"><CircleAlert size={16} /><span>{error}</span><button onClick={() => void refresh()}>RETRY</button></div>}
          <div className="page-heading">
            <div><div className="eyebrow"><span className="eyebrow-line" />THE MANIFEST CANNOT BE TRUSTED. THE TRUTH CAN BE RECONSTRUCTED.</div><h1>{active === "overview" ? <>Command <em>overview</em></> : titleFor(active)}</h1><p className="page-subtitle">Cargo manifest forensic intelligence <span>/</span> Local evidence ledger <span>/</span> {loading ? "Synchronizing" : "Live analysis"}</p></div>
            <div className="heading-meta"><div className="meta-block"><span>OPERATIONAL THEATER</span><b><Globe2 size={14} /> GLOBAL MARITIME</b></div><div className="meta-block"><span>THREAT POSTURE</span><b className="threat-label"><span className="status-dot amber" />{incidentCount ? "ELEVATED" : "NOMINAL"}</b></div><button className="filter-button" onClick={() => void refresh()}><SlidersHorizontal size={15} /> SYNC LEDGER</button></div>
          </div>

          <section className="metric-grid">
            <MetricCard icon={Database} label="Records under watch" value={fmt(overview?.record_count)} detail="Manifest ledger" tone="steel" />
            <MetricCard icon={CircleAlert} label="Active incidents" value={fmt(incidentCount)} detail={`${fmt(overview?.critical_count)} critical posture`} tone="brass" />
            <MetricCard icon={ShieldCheck} label="Manifest integrity" value={overview ? `${overview.integrity_score.toFixed(1)}%` : "—"} detail="Observed vs. flagged" tone="green" />
            <MetricCard icon={Radio} label="Live watch" value={live.length ? "ACTIVE" : "ARMED"} detail={`${live.filter((event) => event.status === "ANOMALY").length} stream anomalies`} tone="crimson" />
          </section>

          <ModuleView active={active} incidents={filtered} records={records} decisions={decisions} reconstructed={reconstructed} live={live} routes={routes} metrics={overview?.metrics ?? {}} reconstructionCounts={overview?.reconstruction_counts ?? {}} query={query} setQuery={setQuery} selectIncident={setSelected} />
          <footer className="footer"><span><span className="status-dot" /> ENCRYPTED LOCAL EVIDENCE STORE</span><span>DOOM / LATVERIAN <i>•</i> BUILD 01.07.26</span><span>WHEN THE MANIFEST CANNOT BE TRUSTED, RECONSTRUCT THE TRUTH.</span></footer>
        </div>
      </main>
      {selected && <IncidentDrawer incident={selected} detail={detail} close={() => setSelected(null)} />}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail, tone }: { icon: typeof Activity; label: string; value: string; detail: string; tone: string }) {
  return <article className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={17} /></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail"><span className={`mini-led ${tone}`} />{detail}</div><div className={`metric-corner ${tone}`} /></article>;
}

function ModuleView(props: {
  active: ModuleKey; incidents: Incident[]; records: RecordRow[]; decisions: Decision[];
  reconstructed: RecordRow[];
  live: LiveEvent[]; routes: { ports: { code: string; name: string; latitude: number; longitude: number }[] } | null;
  metrics: Record<string, number | string>; reconstructionCounts: Record<string, number>;
  query: string; setQuery: (value: string) => void; selectIncident: (value: Incident) => void;
}) {
  const { active, incidents, records, decisions, reconstructed, live, routes, metrics, reconstructionCounts, query, setQuery, selectIncident } = props;
  const recent = incidents.slice(0, 7);
  const streamAnomalies = live.filter((item) => item.incident);
  const unknownEvents = incidents.filter((item) => item.tampering_type === "UNKNOWN ANOMALY").concat(streamAnomalies.map((item) => item.incident!).filter((item) => item.tampering_type === "UNKNOWN ANOMALY"));

  if (active === "metrics") return <section className="module-grid"><div className="panel span-2"><PanelHeading icon={Gauge} title="Evaluation metrics" kicker="SYNTHETIC BATCH / TRANSPARENT SCOPE" /><div className="evaluation-grid">{[["PRECISION", metrics.precision], ["RECALL", metrics.recall], ["F1 SCORE", metrics.f1], ["TYPE ACCURACY", metrics.type_accuracy_on_detected]].map(([label, value]) => <div className="eval-cell" key={String(label)}><span>{label}</span><b>{typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—"}</b></div>)}</div><p className="method-note">{String(metrics.evaluation_scope ?? "No evaluation has been run yet.")}</p><div className="confusion-row">{[["TRUE POSITIVE", metrics.true_positive], ["FALSE POSITIVE", metrics.false_positive], ["FALSE NEGATIVE", metrics.false_negative], ["ATTACKS INJECTED", metrics.injected_attacks]].map(([label, value]) => <div key={String(label)}><span>{label}</span><b>{fmt(typeof value === "number" ? value : undefined)}</b></div>)}</div></div><div className="panel"><PanelHeading icon={ShieldEllipsis} title="Method note" kicker="NO CLAIMS WITHOUT EVIDENCE" /><p className="body-copy">Metrics are computed from this deterministic synthetic run and isolated injection ground truth. They are not a real-world effectiveness claim.</p><div className="quiet-box">DETECTOR INPUTS DO NOT INCLUDE INJECTION LOG</div></div></section>;

  if (active === "routes") return <section className="module-grid"><div className="panel span-2"><PanelHeading icon={Route} title="Maritime route intelligence" kicker="REGISTERED PORT NODES / BATCH TOPOLOGY" /><RouteMap routes={routes?.ports ?? []} /><div className="port-grid">{(routes?.ports ?? []).map((port) => <div className="port-row" key={port.code}><span className="port-dot" /><b>{port.code}</b><span>{port.name}</span><small>{port.latitude.toFixed(2)}°, {port.longitude.toFixed(2)}°</small></div>)}</div></div><div className="panel"><PanelHeading icon={Anchor} title="Route exceptions" kicker="DETECTOR-CORROBORATED" />{incidents.filter((item) => item.tampering_type === "IMPOSSIBLE_MOVEMENT").length ? <IncidentList items={incidents.filter((item) => item.tampering_type === "IMPOSSIBLE_MOVEMENT")} onSelect={selectIncident} /> : <EmptyState title="No route exceptions" detail="No impossible movements are supported by current evidence." />}</div></section>;

  if (active === "stream" || active === "unknown") return <section className="module-grid"><div className="panel span-2"><PanelHeading icon={active === "stream" ? Radio : Sparkles} title={active === "stream" ? "Live event stream" : "Unknown anomaly watch"} kicker="WEBSOCKET / REAL-TIME DETECTION" /><div className="stream-banner"><span className="pulse-ring"><Radio size={17} /></span><div><b>STREAM INGESTION {live.length ? "CONNECTED" : "ARMED"}</b><span>New unknown schema patterns are evaluated without batch attack labels.</span></div><span className="live-tag"><i /> LIVE</span></div>{active === "unknown" && <div className="unknown-callout"><Sparkles size={18} /><div><b>OPEN-SET DETECTION ENABLED</b><span>Novel fields and unrecognized payload attributes trigger an explainable schema-novelty incident.</span></div></div>}<div className="stream-list">{(active === "unknown" ? unknownEvents.map((incident) => ({ event_id: incident.record_id, timestamp: "", record_id: incident.record_id, status: "ANOMALY", incident, record: {} })) : live).length ? (active === "unknown" ? unknownEvents.map((incident) => <IncidentRow key={incident.record_id} item={incident} onClick={() => selectIncident(incident)} />) : live.map((event) => <div className="stream-row" key={event.event_id}><span className={`stream-state ${event.status === "ANOMALY" ? "danger" : ""}`}><i />{event.status}</span><b>{event.record_id}</b><span>{event.incident?.tampering_type ? pretty(event.incident.tampering_type) : "Event cleared"}</span><small>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "Awaiting stream"}</small></div>)) : <EmptyState title="Awaiting first event" detail="The local demo stream publishes a new event every few seconds." />}</div></div><div className="panel"><PanelHeading icon={ScanEye} title="Detection stack" kicker="STREAM FORENSICS" />{["Schema novelty", "Route validation", "Temporal analysis", "Behavioral anomaly", "Relational analysis"].map((name, i) => <div className="detector-row" key={name}><span className="detector-index">0{i + 1}</span><b>{name}</b><span className="detector-online">ACTIVE</span></div>)}</div></section>;

  if (active === "reconstruction") return <><section className="panel"><PanelHeading icon={Boxes} title="Reconstruction ledger" kicker="NO SILENT MUTATIONS / CHANGE SETS EXPLAINED" /><div className="recon-summary">{["ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"].map((status) => <div key={status}><span className={`recon-dot ${status.toLowerCase()}`} /><span>{status}</span><b>{fmt(reconstructionCounts[status])}</b></div>)}</div><div className="table-wrap"><table><thead><tr><th>RECORD</th><th>DECISION</th><th>TAMPERING CLASS</th><th>JUSTIFICATION</th><th>CHANGES</th></tr></thead><tbody>{decisions.slice(0, 100).map((decision) => <tr key={decision.record_id}><td className="mono">{decision.record_id}</td><td><StatusBadge value={decision.status} /></td><td>{decision.tampering_type ? pretty(decision.tampering_type) : "—"}</td><td className="explanation-cell">{decision.explanation}</td><td>{decision.changes.length ? decision.changes.map((change) => `${change.field}: ${change.from} → ${change.to}`).join("; ") : "None"}</td></tr>)}</tbody></table></div></section><section className="panel"><PanelHeading icon={Database} title="Reconstructed manifest output" kicker={`${reconstructed.length.toLocaleString()} MATERIALIZED ROWS / FIRST 100 SHOWN`} /><div className="table-wrap"><table><thead><tr><th>RECORD</th><th>SHIPMENT</th><th>OWNER</th><th>ROUTE</th><th>LOCATION</th><th>VALUE (USD)</th><th>DISPOSITION</th></tr></thead><tbody>{reconstructed.slice(0, 100).map((row) => { const decision = decisions.find((item) => item.record_id === row.record_id); return <tr key={String(row.record_id)}><td className="mono">{row.record_id}</td><td className="mono muted">{row.shipment_id}</td><td>{row.owner}</td><td>{String(row.planned_route).replaceAll("|", " → ")}</td><td className="mono">{row.current_location}</td><td>{typeof row.declared_value_usd === "number" ? row.declared_value_usd.toLocaleString() : row.declared_value_usd}</td><td>{decision && <StatusBadge value={decision.status} />}</td></tr>; })}</tbody></table></div></section></>;

  if (active === "timeline") return <section className="module-grid"><div className="panel span-2"><PanelHeading icon={Clock3} title="Attack timeline" kicker="SORTED BY OPERATIONAL RISK / RECORD TIME" />{incidents.length ? <div className="timeline-list">{incidents.slice(0, 40).map((incident, i) => <button className="timeline-item" key={incident.record_id} onClick={() => selectIncident(incident)}><span className="timeline-line"><i /></span><span className="timeline-time">{`T+${String(i + 1).padStart(2, "0")}`}</span><span className="timeline-type">{pretty(incident.tampering_type)}</span><span className="mono">{incident.record_id}</span><RiskBadge value={incident.risk_score} /><ChevronRight size={15} /></button>)}</div> : <EmptyState title="No timeline evidence" detail="Run a batch analysis to populate the attack timeline." />}</div><ThreatPanel incidents={incidents} /></section>;

  if (active === "integrity") return <section className="module-grid"><div className="panel span-2"><PanelHeading icon={ShieldCheck} title="Manifest integrity" kicker="RECORD CONTROL / EVIDENCE-BACKED VERDICTS" /><div className="integrity-display"><div className="integrity-score"><b>{fmt(reconstructionCounts.ORIGINAL + reconstructionCounts.REPAIRED + reconstructionCounts.REMOVED + reconstructionCounts.UNRECOVERABLE)}</b><span>DECISIONS ISSUED</span></div><div className="integrity-bars">{["ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"].map((status) => { const amount = reconstructionCounts[status] ?? 0; const total = Object.values(reconstructionCounts).reduce((sum, n) => sum + n, 0) || 1; return <div className="integrity-bar-row" key={status}><span>{status}</span><div className="bar-track"><i style={{ width: `${Math.max(0.5, amount / total * 100)}%` }} /></div><b>{fmt(amount)}</b></div>; })}</div></div><p className="method-note">A record is marked ORIGINAL only when no detector has supported a tampering finding. Unrecoverable records remain explicitly quarantined; source fields are never silently rewritten.</p></div><ThreatPanel incidents={incidents} /></section>;

  if (active === "forensics") return <section className="panel"><PanelHeading icon={FileSearch} title="Record forensics" kicker="LEDGER SEARCH / SOURCE RECORD TRACE" /><div className="table-toolbar"><span>{fmt(records.length)} RECORDS LOADED</span><label className="search-field"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search record or shipment…" /></label></div><div className="table-wrap"><table><thead><tr><th>RECORD ID</th><th>SHIPMENT</th><th>OWNER</th><th>ORIGIN → DESTINATION</th><th>VALUE (USD)</th><th>STATUS</th></tr></thead><tbody>{records.filter((row) => !query || `${row.record_id} ${row.shipment_id}`.toLowerCase().includes(query.toLowerCase())).slice(0, 100).map((row) => { const incident = incidents.find((item) => item.record_id === row.record_id); return <tr key={String(row.record_id)} onClick={() => incident && selectIncident(incident)} className={incident ? "clickable-row" : ""}><td className="mono">{row.record_id}</td><td className="mono muted">{row.shipment_id}</td><td>{row.owner}</td><td>{row.origin} <span className="route-arrow">→</span> {row.destination}</td><td>{typeof row.declared_value_usd === "number" ? row.declared_value_usd.toLocaleString() : row.declared_value_usd}</td><td>{incident ? <StatusBadge value={incident.tampering_type} /> : <span className="clean-mark"><ShieldCheck size={13} /> VERIFIED</span>}</td></tr>; })}</tbody></table></div></section>;

  if (active === "incidents") return <section className="panel"><IncidentPanel incidents={incidents} query={query} setQuery={setQuery} selectIncident={selectIncident} /></section>;

  return <section className="overview-layout"><div className="overview-main"><section className="panel"><IncidentPanel incidents={recent} query={query} setQuery={setQuery} selectIncident={selectIncident} compact /></section><section className="panel"><PanelHeading icon={Route} title="Theater overview" kicker="ROUTE ANOMALIES / GLOBAL MARITIME" /><RouteMap routes={routes?.ports ?? []} compact /></section></div><div className="overview-aside"><ThreatPanel incidents={incidents} /><section className="panel"><PanelHeading icon={Boxes} title="Reconstruction" kicker="EXPLICIT DECISIONS" /><div className="recon-mini">{["ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"].map((status) => <div key={status}><span className={`recon-dot ${status.toLowerCase()}`} /><span>{status}</span><b>{fmt(reconstructionCounts[status])}</b></div>)}</div><button className="text-action" onClick={() => window.dispatchEvent(new CustomEvent("doom:nav", { detail: "reconstruction" }))}>OPEN RECONSTRUCTION LEDGER <ArrowUpRight size={14} /></button></section><section className="quote-panel"><div className="quote-mark">“</div><p>When the manifest cannot be trusted, reconstruct the truth.</p><span>LATVERIAN FORENSIC DOCTRINE</span></section></div></section>;
}

function PanelHeading({ icon: Icon, title, kicker }: { icon: typeof Activity; title: string; kicker: string }) {
  return <div className="panel-heading"><div className="panel-title"><span className="panel-icon"><Icon size={16} /></span><h2>{title}</h2></div><span className="panel-kicker">{kicker}</span></div>;
}

function IncidentPanel({ incidents, query, setQuery, selectIncident, compact = false }: { incidents: Incident[]; query: string; setQuery: (value: string) => void; selectIncident: (value: Incident) => void; compact?: boolean }) {
  return <><div className="panel-heading"><div className="panel-title"><span className="panel-icon alert-icon"><Crosshair size={16} /></span><h2>{compact ? "Active incidents" : "Incident register"}</h2><span className="table-count">{incidents.length} CASES</span></div><span className="panel-kicker">EVIDENCE-CORROBORATED FINDINGS</span></div><div className="table-toolbar"><span className="class-label">ALL CLASSIFICATIONS <ChevronDown size={13} /></span><label className="search-field"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter cases…" /></label></div>{incidents.length ? <div className="table-wrap"><table><thead><tr><th>CASE / RECORD</th><th>DETECTION CLASS</th><th>RISK</th><th>CONFIDENCE</th><th>DETECTORS</th><th /></tr></thead><tbody>{incidents.map((incident) => <tr key={incident.record_id} className="clickable-row" onClick={() => selectIncident(incident)}><td><span className="mono incident-id">{incident.record_id}</span>{incident.record_missing && <span className="missing-tag">MISSING</span>}</td><td><span className="attack-kind">{pretty(incident.tampering_type)}</span></td><td><RiskBadge value={incident.risk_score} /></td><td><Confidence value={incident.confidence} /></td><td><span className="detector-pills">{incident.detectors.slice(0, 2).map((name) => <span key={name}>{name.replaceAll("_", " ")}</span>)}</span></td><td><ChevronRight size={15} className="row-chevron" /></td></tr>)}</tbody></table></div> : <EmptyState title="No suspicious records" detail="No incidents match the current query or analysis run." />}</>;
}

function IncidentList({ items, onSelect }: { items: Incident[]; onSelect: (value: Incident) => void }) {
  return <div className="compact-list">{items.map((item) => <IncidentRow key={item.record_id} item={item} onClick={() => onSelect(item)} />)}</div>;
}
function IncidentRow({ item, onClick }: { item: Incident; onClick: () => void }) {
  return <button className="compact-incident" onClick={onClick}><span className="incident-glyph"><CircleAlert size={14} /></span><span><b>{pretty(item.tampering_type)}</b><small>{item.record_id}</small></span><RiskBadge value={item.risk_score} /></button>;
}
function RiskBadge({ value }: { value: number }) {
  return <span className={`risk-badge ${value >= 90 ? "critical" : value >= 75 ? "high" : "moderate"}`}><i />{value}<small> / 100</small></span>;
}
function Confidence({ value }: { value: number }) {
  return <span className="confidence"><span className="confidence-track"><i style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} /></span>{(value * 100).toFixed(0)}%</span>;
}
function StatusBadge({ value }: { value: string }) {
  return <span className={`status-badge ${value.toLowerCase().replaceAll("_", "-")}`}>{pretty(value)}</span>;
}
function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><ShieldEllipsis size={22} /><b>{title}</b><span>{detail}</span></div>;
}
function ThreatPanel({ incidents }: { incidents: Incident[] }) {
  const critical = incidents.filter((item) => item.risk_score >= 90).length;
  const high = incidents.filter((item) => item.risk_score >= 75 && item.risk_score < 90).length;
  return <section className="panel threat-panel"><PanelHeading icon={Shield} title="Threat posture" kicker="CURRENT BATCH ASSESSMENT" /><div className={`threat-gauge ${critical ? "elevated" : ""}`}><div className="gauge-arc"><div className="gauge-inner"><span>THREAT</span><b>{critical ? "ELEVATED" : incidents.length ? "GUARDED" : "NOMINAL"}</b><i><span /></i></div></div></div><div className="threat-breakdown"><div><span className="severity-dot critical" />CRITICAL EXPOSURES<b>{fmt(critical)}</b></div><div><span className="severity-dot high" />HIGH PRIORITY<b>{fmt(high)}</b></div><div><span className="severity-dot steel" />TOTAL CASES<b>{fmt(incidents.length)}</b></div></div></section>;
}
function RouteMap({ routes, compact = false }: { routes: { code: string; name: string; latitude: number; longitude: number }[]; compact?: boolean }) {
  const positions: Record<string, [number, number]> = { NLRTM: [47, 31], SGSIN: [66, 56], USLAX: [20, 38], AEJEA: [53, 43], CNSHA: [72, 37], DEHAM: [48, 28], BRSSZ: [37, 71], JPTYO: [79, 33], GBFXT: [45, 29], INNSA: [61, 47] };
  const nodes = routes.map((port) => ({ ...port, pos: positions[port.code] ?? [50, 50] as [number, number] }));
  return <div className={`route-map ${compact ? "compact" : ""}`}><div className="map-grid" /><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Schematic maritime port network">{[["CNSHA", "SGSIN"], ["SGSIN", "AEJEA"], ["AEJEA", "NLRTM"], ["SGSIN", "JPTYO"], ["JPTYO", "USLAX"], ["BRSSZ", "NLRTM"], ["NLRTM", "GBFXT"], ["INNSA", "DEHAM"], ["USLAX", "SGSIN"]].map(([a, b]) => { const start = nodes.find((node) => node.code === a); const end = nodes.find((node) => node.code === b); return start && end ? <line key={`${a}-${b}`} x1={start.pos[0]} y1={start.pos[1]} x2={end.pos[0]} y2={end.pos[1]} /> : null; })}</svg>{nodes.map((node, i) => <div className={`map-node node-${i % 4}`} key={node.code} style={{ left: `${node.pos[0]}%`, top: `${node.pos[1]}%` }}><i /><span>{node.code}</span></div>)}<div className="map-legend"><span><i className="legend-route" />KNOWN SHIPPING CORRIDOR</span><span><i className="legend-port" />REGISTERED PORT</span></div>{!compact && <div className="map-coordinates">GLOBAL THEATER <i>•</i> 10 REGISTERED NODES</div>}</div>;
}

function IncidentDrawer({ incident, detail, close }: { incident: Incident; detail: { incident: Incident | null; record: RecordRow | null; reconstruction: Decision | null; timeline: { event: string; time: string | null }[] } | null; close: () => void }) {
  return <div className="drawer-scrim" onClick={close}><aside className="incident-drawer" onClick={(event) => event.stopPropagation()}><header className="drawer-head"><div><span className="drawer-kicker"><Crosshair size={14} /> FORENSIC CASE FILE</span><button className="drawer-close" onClick={close} aria-label="Close case file"><X size={18} /></button></div><h2>{incident.record_id}</h2><StatusBadge value={incident.tampering_type} /></header><div className="drawer-content"><div className="drawer-risk"><div><span>RISK SCORE</span><RiskBadge value={incident.risk_score} /></div><div><span>DETECTION CONFIDENCE</span><b>{(incident.confidence * 100).toFixed(0)}%</b></div></div><section className="drawer-section"><PanelHeading icon={ScanEye} title="Evidence matrix" kicker={`${incident.evidence.length} OBSERVATIONS`} />{incident.evidence.map((item, index) => <div className="evidence-item" key={`${item.detector_id}:${item.evidence_code}:${index}`}><span className={`evidence-severity ${item.severity.toLowerCase()}`} /><div><b>{pretty(item.evidence_code)}</b><p>{item.explanation}</p><small>{item.detector_id.replaceAll("_", " ")} · {item.field} · {item.severity} SIGNAL · +{item.score_contribution.toFixed(2)}</small><p className="evidence-comparison">EXPECTED {JSON.stringify(item.expected)} <span>→</span> OBSERVED {JSON.stringify(item.observed)}</p></div></div>)}</section>{incident.counterfactual && <section className="drawer-section"><PanelHeading icon={Crosshair} title="Counterfactual" kicker="WHAT WOULD CLEAR THIS FINDING" /><p className="body-copy">{incident.counterfactual}</p></section>}<section className="drawer-section"><PanelHeading icon={Crosshair} title="Detectors involved" kicker="FUSION PATH" /><div className="drawer-pills">{incident.detectors.map((name) => <span key={name}>{name.replaceAll("_", " ")}</span>)}</div></section><section className="drawer-section"><PanelHeading icon={Fingerprint} title="Related records" kicker="LINKED MANIFEST EVIDENCE" />{incident.related_records.length ? incident.related_records.map((id) => <div className="related-record" key={id}><Database size={13} /><span>{id}</span><ChevronRight size={14} /></div>) : <p className="no-related">No linked record identified.</p>}</section><section className="drawer-section"><PanelHeading icon={Boxes} title="Reconstruction decision" kicker="EXPLICIT / AUDITABLE" />{detail?.reconstruction ? <div className="recon-decision"><StatusBadge value={detail.reconstruction.status} /><p>{detail.reconstruction.explanation}</p>{detail.reconstruction.changes.map((change) => <div className="change-set" key={change.field}><span>{change.field.toUpperCase()}</span><b>{change.from}</b><ArrowDownRight size={14} /><b className="changed-value">{change.to}</b></div>)}</div> : <div className="loading-line"><span className="mini-led brass" />Loading reconstruction record…</div>}</section><section className="drawer-section"><PanelHeading icon={Clock3} title="Case timeline" kicker="EVIDENCE CHAIN" />{detail?.timeline.map((item, index) => <div className="case-timeline-row" key={item.event}><span className="timeline-index">0{index + 1}</span><div><b>{item.event}</b><small>{item.time ? new Date(item.time).toLocaleString() : "Recorded in local evidence ledger"}</small></div></div>)}</section>{detail?.record && <section className="drawer-section"><PanelHeading icon={Database} title="Observed record" kicker="RAW MANIFEST FIELDS" /><pre className="record-json">{JSON.stringify(detail.record, null, 2)}</pre></section>}</div></aside></div>;
}

window.addEventListener("doom:nav", ((event: CustomEvent<ModuleKey>) => {
  document.querySelectorAll<HTMLButtonElement>(".nav-item").forEach((button) => {
    if (button.textContent?.toLowerCase().includes(event.detail)) button.click();
  });
}) as EventListener);
