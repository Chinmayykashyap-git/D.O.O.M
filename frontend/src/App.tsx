import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowDown,
  Bell,
  Boxes,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  FileSearch,
  Fingerprint,
  Radio,
  RefreshCw,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

type Screen = "overview" | "incidents" | "forensics" | "live";
type ReconstructionStatus = "ORIGINAL" | "REPAIRED" | "REMOVED" | "UNRECOVERABLE";

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

type UnknownAnalysis = {
  invariant_violations: {
    detector_id: string;
    evidence_code: string;
    field: string;
    explanation: string;
  }[];
  nearest_known_attack_type: string;
  nearest_similarity: number;
  novelty_score: number;
  nearest_match_meaningful: boolean;
};

type Incident = {
  record_id: string;
  tampering_type: string;
  risk_score: number;
  confidence: number;
  evidence: Evidence[];
  detectors: string[];
  related_records: string[];
  record_missing?: boolean;
  detection_probability?: number;
  counterfactual?: string;
  unknown_analysis?: UnknownAnalysis;
};

type Overview = {
  record_count: number;
  incident_count: number;
  critical_count: number;
  integrity_score: number;
  reconstruction_counts: Record<ReconstructionStatus, number>;
  metrics: Record<string, unknown>;
  stream_status: string;
};

type ReconstructionDecision = {
  record_id: string;
  status: ReconstructionStatus;
  explanation: string;
  changes: { field: string; from: unknown; to: unknown }[];
  tampering_type: string | null;
  method?: string;
  evidence_relied_on?: string[];
  unresolved_fields?: string[];
  confidence?: number;
  provisional?: boolean;
};

type RecordRow = Record<string, string | number | null>;

type TimelineEvent = { event: string; time: string | null };

type IncidentDetail = {
  incident: Incident | null;
  record: RecordRow | null;
  reconstruction: ReconstructionDecision | null;
  timeline: TimelineEvent[];
};

type LiveEvent = {
  event_id: string;
  timestamp: string;
  sequence?: number;
  record_id: string;
  status: "ANOMALY" | "CLEARED";
  incident: Incident | null;
  record: RecordRow;
  live_reconstruction?: ReconstructionDecision;
};

const NAV: { id: Screen; label: string; detail: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", detail: "Command posture", icon: ShieldCheck },
  { id: "incidents", label: "Incidents", detail: "Prioritized cases", icon: CircleAlert },
  { id: "forensics", label: "Record forensics", detail: "Evidence & reconstruction", icon: FileSearch },
  { id: "live", label: "Live watch", detail: "Streaming intelligence", icon: Radio },
];

const SCREEN_TITLE: Record<Screen, string> = {
  overview: "COMMAND OVERVIEW",
  incidents: "ACTIVE INCIDENTS",
  forensics: "RECORD FORENSICS",
  live: "LIVE WATCH",
};

const formatCount = (value: number | undefined) =>
  value == null ? "—" : value.toLocaleString("en-US");

const humanize = (value: string) => value.replaceAll("_", " ");

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function mergeLiveEvents(current: LiveEvent[], incoming: LiveEvent): LiveEvent[] {
  return [incoming, ...current.filter((event) => event.event_id !== incoming.event_id)].slice(0, 100);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  const serialized = JSON.stringify(value);
  return serialized ?? String(value);
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [liveStatus, setLiveStatus] = useState<"CONNECTING" | "CONNECTED" | "RETRYING">("CONNECTING");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [detailRequest, setDetailRequest] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState<"risk" | "confidence" | "type" | "record">("risk");

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [nextOverview, nextIncidents] = await Promise.all([
        getJson<Overview>("/api/overview"),
        getJson<Incident[]>("/api/incidents?limit=500"),
      ]);
      setOverview(nextOverview);
      setIncidents(nextIncidents);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reach the local evidence API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    let active = true;
    let retryTimer: number | undefined;
    let socket: WebSocket | undefined;

    void getJson<LiveEvent[]>("/api/stream/events")
      .then((events) => {
        if (active) setLiveEvents(events.slice(-100).reverse());
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Unable to load live event history.");
        }
      });

    const connect = () => {
      if (!active) return;
      setLiveStatus((status) => status === "CONNECTED" ? status : "CONNECTING");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/api/stream`);
      socket.onopen = () => {
        if (active) setLiveStatus("CONNECTED");
      };
      socket.onmessage = (message: MessageEvent<string>) => {
        try {
          const event = JSON.parse(message.data) as LiveEvent;
          if (active) setLiveEvents((current) => mergeLiveEvents(current, event));
        } catch {
          if (active) setError("The live feed returned an unreadable event.");
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (active) {
          setLiveStatus("RETRYING");
          retryTimer = window.setTimeout(connect, 2_000);
        }
      };
    };

    connect();
    return () => {
      active = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  const selectedBatchIncident = useMemo(
    () => incidents.find((incident) => incident.record_id === selectedId) ?? null,
    [incidents, selectedId],
  );
  const selectedLiveEvent = useMemo(
    () => liveEvents.find((event) => event.record_id === selectedId && event.incident) ?? null,
    [liveEvents, selectedId],
  );
  const selectedIncident = selectedBatchIncident ?? selectedLiveEvent?.incident ?? null;

  useEffect(() => {
    if (!selectedId && incidents.length) {
      setSelectedId(incidents[0].record_id);
    } else if (
      selectedId
      && !incidents.some((incident) => incident.record_id === selectedId)
      && !liveEvents.some((event) => event.record_id === selectedId)
    ) {
      setSelectedId(incidents[0]?.record_id ?? null);
    }
  }, [incidents, liveEvents, selectedId]);

  useEffect(() => {
    if (screen !== "forensics" || !selectedIncident) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    if (!selectedBatchIncident && selectedLiveEvent?.incident) {
      setDetail({
        incident: selectedLiveEvent.incident,
        record: selectedLiveEvent.record,
        reconstruction: selectedLiveEvent.live_reconstruction ?? null,
        timeline: [
          { event: "LIVE EVENT RECEIVED", time: selectedLiveEvent.timestamp },
          { event: "ANOMALY DETECTED", time: selectedLiveEvent.timestamp },
          ...(selectedLiveEvent.live_reconstruction
            ? [{ event: "LIVE RECONSTRUCTION DECIDED", time: selectedLiveEvent.timestamp }]
            : []),
        ],
      });
      setDetailError(null);
      return;
    }
    const controller = new AbortController();
    setDetail(null);
    setDetailError(null);
    getJson<IncidentDetail>(
      `/api/incidents/${encodeURIComponent(selectedIncident.record_id)}`,
      controller.signal,
    )
      .then(setDetail)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setDetailError(cause instanceof Error ? cause.message : "Unable to load case evidence.");
        }
      });
    return () => controller.abort();
  }, [
    detailRequest,
    screen,
    selectedBatchIncident,
    selectedIncident,
    selectedLiveEvent,
  ]);

  const incidentTypes = useMemo(
    () => [...new Set(incidents.map((incident) => incident.tampering_type))].sort(),
    [incidents],
  );

  const visibleIncidents = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = incidents.filter((incident) => {
      const text = [
        incident.record_id,
        incident.tampering_type,
        ...incident.detectors,
        ...incident.evidence.map((item) => `${item.detector_id} ${item.evidence_code} ${item.field}`),
      ].join(" ").toLowerCase();
      const severityMatch = severityFilter === "ALL"
        || (severityFilter === "CRITICAL" && incident.risk_score >= 90)
        || (severityFilter === "HIGH" && incident.risk_score >= 75 && incident.risk_score < 90)
        || (severityFilter === "OTHER" && incident.risk_score < 75);
      return (!needle || text.includes(needle))
        && (typeFilter === "ALL" || incident.tampering_type === typeFilter)
        && severityMatch;
    });
    return matches.sort((left, right) => {
      if (sortBy === "confidence") return right.confidence - left.confidence;
      if (sortBy === "type") return left.tampering_type.localeCompare(right.tampering_type);
      if (sortBy === "record") return left.record_id.localeCompare(right.record_id);
      return right.risk_score - left.risk_score || right.confidence - left.confidence;
    });
  }, [incidents, query, severityFilter, sortBy, typeFilter]);

  const criticalCount = overview?.critical_count ?? 0;
  const posture = criticalCount ? "CRITICAL" : incidents.length ? "GUARDED" : "NOMINAL";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Shield size={21} strokeWidth={1.5} /></div>
          <div>
            <div className="brand-name">D.O.O.M.</div>
            <div className="brand-sub">LATVERIAN INTELLIGENCE</div>
          </div>
        </div>
        <div className="nav-section-label">FORENSIC OPERATIONS</div>
        <nav aria-label="Primary navigation" className="nav-list">
          {NAV.map(({ id, label, detail: navDetail, icon: Icon }) => (
            <button
              aria-current={screen === id ? "page" : undefined}
              className={`nav-item ${screen === id ? "active" : ""}`}
              key={id}
              onClick={() => setScreen(id)}
            >
              <Icon size={16} strokeWidth={1.7} />
              <span><b>{label}</b><small>{navDetail}</small></span>
              {id === "incidents" && incidents.length > 0 && (
                <span className="nav-count">{formatCount(incidents.length)}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="side-seal">
            <Fingerprint size={15} />
            <span>LOCAL EVIDENCE BOUNDARY</span>
            <span className="seal-led" />
          </div>
          <div className="operator">
            <div className="operator-avatar">L</div>
            <div><b>LATVERIAN</b><span>FORENSICS DIVISION</span></div>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            <span>D.O.O.M. / OPERATIONS</span><ChevronRight size={13} />
            <b>{SCREEN_TITLE[screen]}</b>
          </div>
          <div className="top-actions">
            <span className={`system-status ${error ? "status-error" : ""}`}>
              <i />{error ? "API DEGRADED" : "LOCAL SYSTEM"}
            </span>
            <button
              aria-label="Refresh evidence"
              className="icon-button"
              disabled={refreshing}
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} />
            </button>
            <button
              aria-label="Open active incidents"
              className="icon-button"
              onClick={() => setScreen("incidents")}
            >
              <Bell size={16} />
              {criticalCount > 0 && <i className="notification-dot" />}
            </button>
            <span className="utc-clock"><i>UTC</i>{new Date().toISOString().slice(11, 19)}</span>
          </div>
        </header>

        <div className="workspace">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span />MANIFEST INTEGRITY / OPERATIONAL RECORD</div>
              <h1>{screen === "overview" ? <>Command <em>overview</em></> : SCREEN_TITLE[screen]}</h1>
              <p className="page-subtitle">
                Evidence-led cargo manifest reconstruction <span>/</span> Local intelligence console
              </p>
            </div>
            <div className="heading-meta">
              <span className={`posture-chip ${criticalCount ? "critical" : incidents.length ? "guarded" : ""}`}>
                <i />THREAT POSTURE <b>{posture}</b>
              </span>
              <button className="sync-button" onClick={() => void refresh()}>
                <RefreshCw size={14} />{refreshing ? "SYNCING" : "SYNC LEDGER"}
              </button>
            </div>
          </div>

          {error && (
            <div className="error-banner" role="alert">
              <CircleAlert size={16} /><span>{error}</span>
              <button onClick={() => void refresh()}>RETRY</button>
            </div>
          )}

          <section aria-label="Current manifest metrics" className="metric-grid">
            <MetricCard icon={Database} label="RECORDS UNDER WATCH" value={formatCount(overview?.record_count)} detail="Observed manifest" />
            <MetricCard icon={CircleAlert} label="ACTIVE INCIDENTS" value={formatCount(overview?.incident_count)} detail={`${formatCount(criticalCount)} critical`} critical={criticalCount > 0} />
            <MetricCard icon={ShieldCheck} label="MANIFEST INTEGRITY" value={overview ? `${overview.integrity_score.toFixed(1)}%` : "—"} detail="Current API assessment" />
            <MetricCard icon={Radio} label="LIVE WATCH" value={liveStatus === "CONNECTED" ? "CONNECTED" : liveStatus} detail={`${formatCount(liveEvents.length)} recent events`} />
          </section>

          {loading && !overview ? (
            <LoadingState label="Synchronizing with the local evidence service…" />
          ) : screen === "overview" ? (
            <OverviewScreen
              overview={overview}
              incidents={incidents}
              onOpenIncident={(incident) => {
                setSelectedId(incident.record_id);
                setScreen("forensics");
              }}
              onViewAll={() => setScreen("incidents")}
            />
          ) : screen === "incidents" ? (
            <IncidentsScreen
              incidents={visibleIncidents}
              allCount={incidents.length}
              query={query}
              typeFilter={typeFilter}
              severityFilter={severityFilter}
              sortBy={sortBy}
              incidentTypes={incidentTypes}
              setQuery={setQuery}
              setTypeFilter={setTypeFilter}
              setSeverityFilter={setSeverityFilter}
              setSortBy={setSortBy}
              onSelect={(incident) => {
                setSelectedId(incident.record_id);
                setScreen("forensics");
              }}
            />
          ) : screen === "forensics" ? (
            <ForensicsScreen
              incidents={incidents}
              selected={selectedIncident}
              detail={detail}
              loading={Boolean(selectedIncident) && !detail && !detailError}
              error={detailError}
              onSelect={(incident) => setSelectedId(incident.record_id)}
              onRetry={() => {
                setDetailRequest((attempt) => attempt + 1);
              }}
            />
          ) : (
            <LiveScreen
              events={liveEvents}
              status={liveStatus}
              onSelect={(incident) => {
                setSelectedId(incident.record_id);
                setScreen("forensics");
              }}
            />
          )}

          <footer className="footer">
            <span><i />LOCAL EVIDENCE STORE / ORACLE ISOLATED</span>
            <span>LATVERIAN <b>·</b> D.O.O.M.</span>
            <span>WHEN THE MANIFEST CANNOT BE TRUSTED, RECONSTRUCT THE TRUTH.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  critical = false,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  critical?: boolean;
}) {
  return (
    <article className={`metric-card ${critical ? "critical" : ""}`}>
      <div className="metric-top"><span>{label}</span><Icon size={17} /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function PanelHeading({
  icon: Icon,
  title,
  kicker,
  action,
}: {
  icon: typeof Activity;
  title: string;
  kicker: string;
  action?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div className="panel-title"><span><Icon size={15} /></span><h2>{title}</h2></div>
      <div className="panel-heading-right"><small>{kicker}</small>{action}</div>
    </div>
  );
}

function OverviewScreen({
  overview,
  incidents,
  onOpenIncident,
  onViewAll,
}: {
  overview: Overview | null;
  incidents: Incident[];
  onOpenIncident: (incident: Incident) => void;
  onViewAll: () => void;
}) {
  const statusCounts = overview?.reconstruction_counts;
  const decisionCount = statusCounts
    ? Object.values(statusCounts).reduce((sum, value) => sum + value, 0)
    : undefined;
  const ranked = [...incidents].sort((left, right) => right.risk_score - left.risk_score).slice(0, 6);
  const seal = overview?.integrity_score;
  return (
    <section className="overview-layout">
      <div className="overview-main">
        <section className="panel seal-panel">
          <PanelHeading icon={ShieldCheck} title="Manifest integrity seal" kicker="CURRENT OPERATOR SNAPSHOT" />
          <div className="seal-content">
            <div className="integrity-seal" aria-label={seal == null ? "Integrity score unavailable" : `Manifest integrity ${seal.toFixed(1)} percent`}>
              <span>MANIFEST</span><strong>{seal == null ? "—" : `${seal.toFixed(1)}%`}</strong><small>INTEGRITY</small>
            </div>
            <div className="seal-copy">
              <span className={`posture-large ${overview?.critical_count ? "critical" : incidents.length ? "guarded" : ""}`}>
                <i />{overview?.critical_count ? "CRITICAL EXPOSURE" : incidents.length ? "ELEVATED REVIEW" : "NO ACTIVE THREATS"}
              </span>
              <h2>Evidence before assertion.</h2>
              <p>Integrity reflects the current API snapshot. Every alert retains its evidence trail; unsupported fields remain explicitly unresolved.</p>
              <div className="reconstruction-summary">
                {(["ORIGINAL", "REPAIRED", "REMOVED", "UNRECOVERABLE"] as ReconstructionStatus[]).map((status) => (
                  <div key={status}><span className={`recon-mark ${status.toLowerCase()}`} /><b>{status}</b><strong>{formatCount(statusCounts?.[status])}</strong></div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="panel">
          <PanelHeading
            icon={CircleAlert}
            title="Incident summary"
            kicker={`${formatCount(incidents.length)} API-REPORTED CASES`}
            action={<button className="text-button" onClick={onViewAll}>ALL INCIDENTS <ChevronRight size={13} /></button>}
          />
          {ranked.length ? (
            <div className="incident-summary-list">
              {ranked.map((incident) => (
                <IncidentSummaryRow key={incident.record_id} incident={incident} onClick={() => onOpenIncident(incident)} />
              ))}
            </div>
          ) : (
            <EmptyState title="No active incidents" detail="The local API has no incident findings for the current manifest." />
          )}
        </section>
      </div>

      <aside className="overview-aside">
        <section className="panel posture-panel">
          <PanelHeading icon={Activity} title="Threat posture" kicker="BATCH EVIDENCE" />
          <div className={`posture-gauge ${overview?.critical_count ? "critical" : incidents.length ? "guarded" : ""}`}>
            <div className="gauge-ring"><span>{overview?.critical_count ? "CRITICAL" : incidents.length ? "GUARDED" : "NOMINAL"}</span><strong>{formatCount(incidents.length)}</strong><small>OPEN FINDINGS</small></div>
          </div>
          <div className="posture-breakdown">
            <div><i className="critical" />CRITICAL<b>{formatCount(overview?.critical_count)}</b></div>
            <div><i className="guarded" />ELEVATED<b>{formatCount(incidents.filter((item) => item.risk_score >= 75 && item.risk_score < 90).length)}</b></div>
            <div><i />RECONSTRUCTION DECISIONS<b>{formatCount(decisionCount)}</b></div>
          </div>
        </section>

        <section className="panel doctrine-panel">
          <PanelHeading icon={Boxes} title="Reconstruction doctrine" kicker="NO SILENT MUTATIONS" />
          <p>Original, repaired, removed, or unrecoverable. A missing value is never guessed from hidden evaluation truth.</p>
          <div className="doctrine-seal"><Check size={14} /> WITNESS-BACKED / AUDITABLE</div>
        </section>

        <section className="panel local-boundary">
          <PanelHeading icon={Fingerprint} title="Evidence boundary" kicker="LOCAL BY DESIGN" />
          <p>Detector inputs exclude the injection log. The oracle is used only after analysis to score this synthetic run.</p>
        </section>
      </aside>
    </section>
  );
}

function IncidentSummaryRow({ incident, onClick }: { incident: Incident; onClick: () => void }) {
  return (
    <button className="incident-summary-row" onClick={onClick}>
      <span className={`severity-mark ${severityClass(incident.risk_score)}`} />
      <span className="summary-main"><b>{humanize(incident.tampering_type)}</b><small>{incident.record_id} · {incident.detectors.length} detector signals</small></span>
      <RiskBadge value={incident.risk_score} />
      <ChevronRight size={15} />
    </button>
  );
}

function IncidentsScreen({
  incidents,
  allCount,
  query,
  typeFilter,
  severityFilter,
  sortBy,
  incidentTypes,
  setQuery,
  setTypeFilter,
  setSeverityFilter,
  setSortBy,
  onSelect,
}: {
  incidents: Incident[];
  allCount: number;
  query: string;
  typeFilter: string;
  severityFilter: string;
  sortBy: "risk" | "confidence" | "type" | "record";
  incidentTypes: string[];
  setQuery: (value: string) => void;
  setTypeFilter: (value: string) => void;
  setSeverityFilter: (value: string) => void;
  setSortBy: (value: "risk" | "confidence" | "type" | "record") => void;
  onSelect: (incident: Incident) => void;
}) {
  return (
    <section className="panel incident-browser">
      <PanelHeading icon={CircleAlert} title="Prioritized incident register" kicker="FILTER / SORT / INSPECT" />
      <div className="filter-bar">
        <label className="search-box"><Search size={15} /><input aria-label="Search incidents" placeholder="Record, attack, detector…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <label>TYPE
          <select aria-label="Filter by attack type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="ALL">ALL TYPES</option>
            {incidentTypes.map((type) => <option key={type} value={type}>{humanize(type)}</option>)}
          </select>
        </label>
        <label>RISK
          <select aria-label="Filter by severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="ALL">ALL LEVELS</option><option value="CRITICAL">CRITICAL</option>
            <option value="HIGH">HIGH</option><option value="OTHER">OTHER</option>
          </select>
        </label>
        <label>SORT
          <select aria-label="Sort incidents" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}>
            <option value="risk">RISK SCORE</option><option value="confidence">CONFIDENCE</option>
            <option value="type">ATTACK TYPE</option><option value="record">RECORD ID</option>
          </select>
        </label>
        <span className="filter-count">{formatCount(incidents.length)} / {formatCount(allCount)} CASES</span>
      </div>
      {incidents.length ? (
        <div className="table-wrap">
          <table className="incident-table">
            <thead><tr><th>RISK</th><th>RECORD / FINDING</th><th>DETECTORS</th><th>CONFIDENCE</th><th>RELATED</th><th /></tr></thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.record_id}>
                  <td><RiskBadge value={incident.risk_score} /></td>
                  <td><b>{humanize(incident.tampering_type)}</b><small className="cell-sub">{incident.record_id}</small></td>
                  <td><div className="detector-tags">{incident.detectors.slice(0, 3).map((detector) => <span key={detector}>{humanize(detector)}</span>)}{incident.detectors.length > 3 && <span>+{incident.detectors.length - 3}</span>}</div></td>
                  <td><Confidence value={incident.detection_probability ?? incident.confidence} /></td>
                  <td>{incident.related_records.length}</td>
                  <td><button aria-label={`Open forensics for ${incident.record_id}`} className="row-action" onClick={() => onSelect(incident)}>REVIEW <ChevronRight size={13} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title={allCount ? "No matching incidents" : "No active incidents"} detail={allCount ? "Adjust the search or filters to widen the case list." : "No findings have been returned by the local API."} />
      )}
    </section>
  );
}

function ForensicsScreen({
  incidents,
  selected,
  detail,
  loading,
  error,
  onSelect,
  onRetry,
}: {
  incidents: Incident[];
  selected: Incident | null;
  detail: IncidentDetail | null;
  loading: boolean;
  error: string | null;
  onSelect: (incident: Incident) => void;
  onRetry: () => void;
}) {
  return (
    <section className="forensics-layout">
      <div className="panel case-list-panel">
        <PanelHeading icon={FileSearch} title="Case index" kicker={`${formatCount(incidents.length)} FINDINGS`} />
        {incidents.length ? (
          <div className="case-list">
            {incidents.map((incident) => (
              <button
                aria-current={selected?.record_id === incident.record_id ? "true" : undefined}
                className={`case-list-item ${selected?.record_id === incident.record_id ? "selected" : ""}`}
                key={incident.record_id}
                onClick={() => onSelect(incident)}
              >
                <span className={`severity-mark ${severityClass(incident.risk_score)}`} />
                <span><b>{humanize(incident.tampering_type)}</b><small>{incident.record_id}</small></span>
                <RiskBadge value={incident.risk_score} />
              </button>
            ))}
          </div>
        ) : <EmptyState title="No cases to inspect" detail="Incidents from the current API snapshot will appear here." />}
      </div>
      <div className="panel case-detail-panel">
        {!selected ? (
          <EmptyState title="Select a forensic case" detail="Choose an incident to inspect its evidence, relationships, and reconstruction decision." />
        ) : loading ? (
          <LoadingState label="Retrieving case evidence…" />
        ) : error ? (
          <div className="error-state" role="alert"><CircleAlert size={20} /><b>Evidence retrieval failed</b><span>{error}</span><button onClick={onRetry}>RETRY CASE LOOKUP</button></div>
        ) : detail ? (
          <CaseEvidence incident={detail.incident ?? selected} detail={detail} onOpenRelated={(id) => {
            const related = incidents.find((item) => item.record_id === id);
            if (related) onSelect(related);
          }} />
        ) : (
          <EmptyState title="Case evidence unavailable" detail="The API returned no case detail for this finding." />
        )}
      </div>
    </section>
  );
}

function CaseEvidence({
  incident,
  detail,
  onOpenRelated,
}: {
  incident: Incident;
  detail: IncidentDetail;
  onOpenRelated: (id: string) => void;
}) {
  const decision = detail.reconstruction;
  const unknown = incident.unknown_analysis;
  return (
    <div className="case-evidence">
      <div className="case-title">
        <div><span className="eyebrow"><span />FORENSIC CASE FILE</span><h2>{incident.record_id}</h2><p>{humanize(incident.tampering_type)}</p></div>
        <div className="case-score"><RiskBadge value={incident.risk_score} /><span>RISK SCORE</span><Confidence value={incident.detection_probability ?? incident.confidence} /></div>
      </div>

      <section className="case-section">
        <PanelHeading icon={Fingerprint} title="Evidence matrix" kicker={`${formatCount(incident.evidence.length)} OBSERVATIONS`} />
        {incident.evidence.length ? (
          <div className="evidence-table-wrap">
            <table className="evidence-table">
              <thead><tr><th>DETECTOR / SIGNAL</th><th>FIELD</th><th>EXPECTED</th><th>OBSERVED</th><th>SCORE</th></tr></thead>
              <tbody>{incident.evidence.map((item, index) => (
                <tr key={`${item.evidence_code}:${index}`}>
                  <td><b>{humanize(item.evidence_code)}</b><small>{humanize(item.detector_id)} · {item.explanation}</small></td>
                  <td className="mono">{item.field}</td><td>{displayValue(item.expected)}</td>
                  <td>{displayValue(item.observed)}</td><td className="score-cell">+{item.score_contribution.toFixed(2)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <EmptyState title="No evidence rows" detail="This incident has no detector evidence in the returned API payload." />}
      </section>

      <section className="case-section">
        <PanelHeading icon={Database} title="Observed record" kicker="API-RETURNED MANIFEST FIELDS" />
        {detail.record ? (
          <div className="record-facts">
            {([
              ["SHIPMENT", detail.record.shipment_id],
              ["OWNER", detail.record.owner],
              ["CONTAINER", detail.record.container_id],
              ["ROUTE", detail.record.planned_route],
              ["DECLARED VALUE", detail.record.declared_value_usd],
              ["EVENT TIME", detail.record.event_ts],
            ] as const).map(([label, value]) => (
              <div key={label}><span>{label}</span><b>{displayValue(value)}</b></div>
            ))}
          </div>
        ) : <EmptyState title="Source payload unavailable" detail="No observed row was returned; reconstruction must rely only on independent evidence." />}
      </section>

      {incident.counterfactual && (
        <section className="counterfactual">
          <Sparkles size={15} /><div><b>COUNTERFACTUAL</b><p>{incident.counterfactual}</p></div>
        </section>
      )}

      {unknown && (
        <section className="unknown-analysis">
          <div className="unknown-heading"><CircleAlert size={16} /><div><b>UNKNOWN ANOMALY ANALYSIS</b><small>Novelty is evidence distance, not a semantic type assignment.</small></div></div>
          <div className="unknown-scores"><span>NOVELTY <b>{(unknown.novelty_score * 100).toFixed(1)}%</b></span><span>NEAREST KNOWN <b>{humanize(unknown.nearest_known_attack_type)}</b></span><span>SIMILARITY <b>{(unknown.nearest_similarity * 100).toFixed(1)}%</b></span></div>
          {!unknown.nearest_match_meaningful && <p className="nearest-note">No evidence-signature overlap; the nearest category is a deterministic tie-break only.</p>}
          <ul>{unknown.invariant_violations.map((item) => <li key={`${item.evidence_code}:${item.field}`}><b>{humanize(item.evidence_code)}</b><span>{item.explanation}</span></li>)}</ul>
        </section>
      )}

      <section className="case-section reconstruction-section">
        <PanelHeading icon={Boxes} title="Reconstruction decision" kicker="EXPLICIT / AUDITABLE" />
        {decision ? (
          <div className="decision-body">
            <div className="decision-status"><StatusBadge value={decision.status} /><span>{decision.method ? humanize(decision.method) : "WITNESS-BACKED DECISION"}</span></div>
            <p>{decision.explanation}</p>
            {decision.provisional && <p className="unresolved-fields">PROVISIONAL — FIRST OBSERVED STREAM SNAPSHOT</p>}
            {decision.changes.length ? (
              <div className="diff-list">{decision.changes.map((change) => (
                <div className="diff-row" key={change.field}><b>{humanize(change.field)}</b><span>{displayValue(change.from)}</span><ArrowDown size={14} /><strong>{displayValue(change.to)}</strong></div>
              ))}</div>
            ) : <div className="no-diff">No field mutation recorded.</div>}
            {decision.unresolved_fields?.length ? <p className="unresolved-fields">UNRESOLVED: {decision.unresolved_fields.join(", ")}</p> : null}
            {decision.evidence_relied_on?.length ? <div className="evidence-provenance">{decision.evidence_relied_on.map((item) => <span key={item}>{item}</span>)}</div> : null}
          </div>
        ) : <EmptyState title="No reconstruction decision returned" detail="The finding remains visible; no recovery outcome is inferred." />}
      </section>

      <section className="case-section related-timeline-grid">
        <div>
          <PanelHeading icon={Database} title="Related records" kicker="LINKED EVIDENCE" />
          {incident.related_records.length ? (
            <div className="related-list">{incident.related_records.map((id) => (
              <button key={id} onClick={() => onOpenRelated(id)}><Database size={13} />{id}<ChevronRight size={13} /></button>
            ))}</div>
          ) : <p className="quiet-copy">No linked record identified.</p>}
        </div>
        <div>
          <PanelHeading icon={Clock3} title="Case timeline" kicker="OBSERVED / DECIDED" />
          {detail.timeline.length ? (
            <div className="case-timeline">{detail.timeline.map((item) => (
              <div className="timeline-event" key={item.event}><i /><b>{item.event}</b><small>{item.time ? new Date(item.time).toLocaleString() : "Time not provided by API"}</small></div>
            ))}</div>
          ) : <p className="quiet-copy">No timeline events returned by the API.</p>}
        </div>
      </section>
    </div>
  );
}

function LiveScreen({
  events,
  status,
  onSelect,
}: {
  events: LiveEvent[];
  status: "CONNECTING" | "CONNECTED" | "RETRYING";
  onSelect: (incident: Incident) => void;
}) {
  const unknown = events.filter((event) => event.incident?.tampering_type === "UNKNOWN ANOMALY");
  return (
    <section className="live-layout">
      <div className="panel live-panel">
        <PanelHeading icon={Radio} title="Live event stream" kicker="INCREMENTAL / LOCAL FEED" />
        <div className={`stream-banner ${status === "CONNECTED" ? "connected" : "retrying"}`}>
          <span className="stream-pulse"><Radio size={16} /></span>
          <div><b>STREAM {status}</b><small>Operator events and detections arrive from the local WebSocket API.</small></div>
          <span className="live-tag"><i />{status}</span>
        </div>
        {events.length ? (
          <div className="live-event-list">
            {events.map((event) => (
              <div className="live-event-row" key={event.event_id}>
                <span className={`event-state ${event.status === "ANOMALY" ? severityClass(event.incident?.risk_score ?? 0) : ""}`}><i />{event.status}</span>
                <div><b>{event.record_id}</b><small>{event.incident ? humanize(event.incident.tampering_type) : "No anomaly in current event"}</small></div>
                <time>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "—"}</time>
                {event.incident && <button onClick={() => {
                  if (event.incident) onSelect(event.incident);
                }}>INSPECT <ChevronRight size={13} /></button>}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title={status === "CONNECTED" ? "Awaiting first event" : "Connecting to live feed"} detail="The interface will display events as they arrive; no placeholder events are shown." />
        )}
      </div>
      <aside className="panel unknown-panel">
        <PanelHeading icon={Sparkles} title="Unknown anomaly" kicker="OPEN-SET WATCH" />
        <div className="unknown-intro">
          <span className="unknown-emblem"><Sparkles size={18} /></span>
          <div><b>{unknown.length ? "UNKNOWN SIGNAL DETECTED" : "NOVELTY MONITOR ARMED"}</b><p>Schema and invariant violations are surfaced without forcing a known attack label.</p></div>
        </div>
        {unknown.length ? (
          <div className="unknown-event-list">
            {unknown.map((event) => {
              const incident = event.incident!;
              return (
                <button className="unknown-event" key={event.event_id} onClick={() => onSelect(incident)}>
                  <span><b>{event.record_id}</b><small>{incident.unknown_analysis?.invariant_violations.length ?? incident.evidence.length} invariant signals</small></span>
                  <span className="novelty-score">{incident.unknown_analysis ? `${(incident.unknown_analysis.novelty_score * 100).toFixed(0)}%` : "—"}<small>NOVELTY</small></span>
                  <ChevronRight size={14} />
                </button>
              );
            })}
          </div>
        ) : <EmptyState title="No unknown events" detail="Unknown alerts will appear here when the live API observes a novel event." />}
      </aside>
    </section>
  );
}

function RiskBadge({ value }: { value: number }) {
  return <span className={`risk-badge ${severityClass(value)}`}>{value.toFixed(0)} <small>RISK</small></span>;
}

function Confidence({ value }: { value: number }) {
  return <span className="confidence-value">{(value * 100).toFixed(1)}%</span>;
}

function StatusBadge({ value }: { value: string }) {
  return <span className={`status-badge ${value.toLowerCase()}`}>{humanize(value)}</span>;
}

function severityClass(score: number): string {
  if (score >= 90) return "critical";
  if (score >= 75) return "high";
  return "standard";
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><Shield size={19} /><b>{title}</b><span>{detail}</span></div>;
}

function LoadingState({ label }: { label: string }) {
  return <div className="loading-state" role="status"><span className="loading-indicator" />{label}</div>;
}
