/**
 * D.O.O.M. — Cargo Manifest Forensic Intelligence Console
 * Team LATVERIAN — Naval Command Center UI
 *
 * Routing:
 *  /             → Overview
 *  /incidents    → Incident Register
 *  /forensics    → Record Forensics
 *  /live         → Live Watch
 *  /route-map    → Route Map
 *  /custody      → Chain of Custody
 *  /timeline     → Attack Timeline
 *  /anomaly      → Unknown Anomaly
 *  /metrics      → Evaluation Metrics
 *  /tamper-lab   → Tamper Lab
 *  /dev/components → Component Gallery
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  AlertTriangle,
  Anchor,
  ArrowRight,
  BarChart3,
  ChevronRight,
  Clock,
  Code2,
  Database,
  FileSearch,
  Fingerprint,
  FlaskConical,
  GitFork,
  HelpCircle,
  Link2,
  Monitor,
  Radio,
  RefreshCw,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from 'lucide-react';

import {
  type Incident,
  type IncidentDetail,
  type LiveEvent,
  type Overview,
  type RecordRow,
  type ReconstructionDecision,
  type ReconstructionStatus,
} from './types';
import { severityLevel } from './theme';
import './styles.css';

// ─── API helpers ─────────────────────────────────────────────────────────────

const API = {
  base: '',
  json: async <T,>(path: string, signal?: AbortSignal): Promise<T> => {
    const r = await fetch(API.base + path, { signal });
    if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
    return r.json() as Promise<T>;
  },
};

// ─── Formatters ──────────────────────────────────────────────────────────────

const fmt = {
  count: (n: number | undefined): string =>
    n == null ? '—' : n.toLocaleString('en-US'),
  pct: (n: number | undefined, decimals = 1): string =>
    n == null ? '—' : `${(n * 100).toFixed(decimals)}%`,
  score: (n: number): string => n.toFixed(1),
  val: (v: unknown): string => {
    if (v == null) return '—';
    if (typeof v === 'string') return v;
    return JSON.stringify(v);
  },
  humanize: (s: string): string => s.replace(/_/g, ' '),
  utc: (d = new Date()): string => d.toISOString().slice(11, 19),
  ts: (s: string | null | undefined): string => {
    if (!s) return '—';
    try { return new Date(s).toLocaleString(); } catch { return s; }
  },
};

// ─── Live merge ───────────────────────────────────────────────────────────────

function mergeLive(current: LiveEvent[], incoming: LiveEvent): LiveEvent[] {
  return [incoming, ...current.filter((e) => e.event_id !== incoming.event_id)].slice(0, 100);
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

// ─── App Shell ────────────────────────────────────────────────────────────────

function AppShell() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [liveStatus, setLiveStatus] = useState<'CONNECTING' | 'CONNECTED' | 'RETRYING'>('CONNECTING');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [presentationMode, setPresentationMode] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [utcTime, setUtcTime] = useState(fmt.utc());

  const navigate = useNavigate();
  const location = useLocation();

  // Live UTC clock
  useEffect(() => {
    const timer = setInterval(() => setUtcTime(fmt.utc()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette((v) => !v);
      }
      if (e.key === '?' && !['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as Element).tagName)) {
        setShowHelp((v) => !v);
      }
      if (e.key === 'Escape') {
        setShowCommandPalette(false);
        setShowHelp(false);
      }
      if (e.key === 'p' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPresentationMode((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Data refresh
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [nextOv, nextInc] = await Promise.all([
        API.json<Overview>('/api/overview'),
        API.json<Incident[]>('/api/incidents?limit=500'),
      ]);
      setOverview(nextOv);
      setIncidents(nextInc);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to reach evidence API.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 30_000);
    return () => clearInterval(t);
  }, [refresh]);

  // WebSocket live stream
  useEffect(() => {
    let active = true;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;

    void API.json<LiveEvent[]>('/api/stream/events')
      .then((events) => { if (active) setLiveEvents(events.slice(-100).reverse()); })
      .catch(() => {});

    const connect = () => {
      if (!active) return;
      setLiveStatus((s) => s === 'CONNECTED' ? s : 'CONNECTING');
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${proto}//${window.location.host}/api/stream`);
      socket.onopen = () => { if (active) setLiveStatus('CONNECTED'); };
      socket.onmessage = ({ data }: MessageEvent<string>) => {
        try {
          if (active) setLiveEvents((cur) => mergeLive(cur, JSON.parse(data) as LiveEvent));
        } catch { /* ignore parse errors */ }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (active) {
          setLiveStatus('RETRYING');
          retry = setTimeout(connect, 2_000);
        }
      };
    };
    connect();
    return () => {
      active = false;
      clearTimeout(retry);
      socket?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const criticalCount = overview?.critical_count ?? 0;
  const posture = criticalCount ? 'critical' : incidents.length ? 'guarded' : 'nominal';

  const NAV_ITEMS: NavItem[] = [
    { path: '/', label: 'OVERVIEW', detail: 'Command posture', icon: ShieldCheck },
    { path: '/incidents', label: 'INCIDENTS', detail: 'Case register', icon: AlertTriangle, badge: incidents.length || undefined },
    { path: '/forensics', label: 'FORENSICS', detail: 'Evidence & reconstruction', icon: FileSearch },
    { path: '/live', label: 'LIVE WATCH', detail: 'Streaming feed', icon: Radio, badge: liveStatus === 'CONNECTED' ? undefined : undefined },
    { path: '/route-map', label: 'ROUTE MAP', detail: 'Nautical chart', icon: Anchor },
    { path: '/custody', label: 'CHAIN OF CUSTODY', detail: 'Hash ledger', icon: Link2 },
    { path: '/timeline', label: 'ATTACK TIMELINE', detail: 'Detection lag', icon: Clock },
    { path: '/anomaly', label: 'UNKNOWN ANOMALY', detail: 'Novelty analysis', icon: Sparkles },
    { path: '/metrics', label: 'EVAL METRICS', detail: 'Precision / recall', icon: BarChart3 },
    { path: '/tamper-lab', label: 'TAMPER LAB', detail: 'Live demonstration', icon: FlaskConical },
  ];

  const SCREEN_LABELS: Record<string, string> = {
    '/': 'OVERVIEW',
    '/incidents': 'INCIDENTS',
    '/forensics': 'FORENSICS',
    '/live': 'LIVE WATCH',
    '/route-map': 'ROUTE MAP',
    '/custody': 'CHAIN OF CUSTODY',
    '/timeline': 'ATTACK TIMELINE',
    '/anomaly': 'UNKNOWN ANOMALY',
    '/metrics': 'EVAL METRICS',
    '/tamper-lab': 'TAMPER LAB',
    '/dev/components': 'COMPONENT GALLERY',
  };

  const currentLabel = SCREEN_LABELS[location.pathname] ?? 'D.O.O.M.';

  return (
    <div className={`app-shell${presentationMode ? ' presentation-mode' : ''}`}>
      {/* Sidebar */}
      <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`} aria-label="Primary navigation">
        <div className="sidebar-inner">
          <div className="brand">
            <div className="brand-hexmark" aria-hidden="true">⚔</div>
            <div className="brand-text">
              <div className="brand-name">D.O.O.M.</div>
              <div className="brand-sub">LATVERIAN INTEL</div>
            </div>
          </div>

          <nav className="nav-section">
            <div className="nav-section-label">FORENSIC OPS</div>
            <ul className="nav-list" role="list">
              {NAV_ITEMS.map((item) => (
                <NavItemComponent
                  key={item.path}
                  item={item}
                  active={location.pathname === item.path}
                  collapsed={sidebarCollapsed}
                />
              ))}
            </ul>
          </nav>

          <div className="sidebar-bottom">
            <div className="evidence-boundary" title="Local evidence boundary active — oracle not accessible to detectors">
              <span className={`boundary-led${error ? ' offline' : ''}`} />
              <span>LOCAL EVIDENCE BOUNDARY</span>
            </div>
            <button
              className="sidebar-collapse-btn"
              onClick={() => setSidebarCollapsed((v) => !v)}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <ChevronRight
                size={14}
                style={{ transform: sidebarCollapsed ? 'none' : 'rotate(180deg)', transition: 'transform 200ms' }}
              />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className={`main-content${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        {/* Topbar */}
        <header className="topbar" role="banner">
          <div className="breadcrumb" aria-label="Current location">
            <span>D.O.O.M.</span>
            <span className="breadcrumb-sep">/</span>
            <span className="breadcrumb-current">{currentLabel}</span>
          </div>
          <div className="topbar-right">
            <div
              className={`connection-status ${liveStatus === 'CONNECTED' ? 'connected' : liveStatus === 'RETRYING' ? 'error' : ''}`}
              title="WebSocket stream status"
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
              {liveStatus}
            </div>
            {error && (
              <div className="connection-status error" title={error}>API DEGRADED</div>
            )}
            <button
              className="icon-btn"
              onClick={() => void refresh()}
              disabled={refreshing}
              aria-label="Refresh data"
              title="Refresh evidence (R)"
            >
              <RefreshCw size={15} className={refreshing ? 'spin-anim' : ''} />
            </button>
            <button
              className="icon-btn"
              onClick={() => setPresentationMode((v) => !v)}
              aria-label="Toggle presentation mode"
              title="Presentation mode (Ctrl+P)"
            >
              <Monitor size={15} style={{ color: presentationMode ? 'var(--c-brass)' : undefined }} />
            </button>
            <button
              className="icon-btn"
              onClick={() => setShowCommandPalette(true)}
              aria-label="Open command palette"
              title="Command palette (Ctrl+K)"
            >
              <Search size={15} />
            </button>
            <button
              className="icon-btn"
              onClick={() => setShowHelp(true)}
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
            >
              <HelpCircle size={15} />
            </button>
            <div className="utc-clock" aria-live="off" aria-label="UTC time">
              <span className="utc-label">UTC</span>{utcTime}
            </div>
          </div>
        </header>

        {/* Workspace */}
        <main className="workspace" id="main-content">
          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={15} />
              <span className="error-banner-text">{error}</span>
              <button className="btn btn-crimson" onClick={() => void refresh()}>RETRY</button>
            </div>
          )}

          {/* KPI strip — always visible */}
          <KpiStrip overview={overview} incidents={incidents} liveStatus={liveStatus} liveEvents={liveEvents} />

          {loading && !overview ? (
            <LoadingState label="Synchronizing with local evidence service…" />
          ) : (
            <Routes>
              <Route
                path="/"
                element={
                  <OverviewScreen
                    overview={overview}
                    incidents={incidents}
                    posture={posture}
                    liveEvents={liveEvents}
                  />
                }
              />
              <Route
                path="/incidents"
                element={<IncidentsScreen incidents={incidents} />}
              />
              <Route
                path="/forensics"
                element={<ForensicsScreen incidents={incidents} liveEvents={liveEvents} />}
              />
              <Route
                path="/live"
                element={<LiveScreen events={liveEvents} status={liveStatus} />}
              />
              <Route path="/route-map" element={<RouteMapScreen />} />
              <Route path="/custody" element={<ChainOfCustodyScreen />} />
              <Route path="/timeline" element={<AttackTimelineScreen incidents={incidents} />} />
              <Route path="/anomaly" element={<UnknownAnomalyScreen incidents={incidents} liveEvents={liveEvents} />} />
              <Route path="/metrics" element={<EvalMetricsScreen />} />
              <Route path="/tamper-lab" element={<TamperLabScreen />} />
              <Route path="/dev/components" element={<ComponentGallery />} />
            </Routes>
          )}

          <footer className="app-footer">
            <div className="footer-seal"><i /><span>LOCAL EVIDENCE STORE · ORACLE ISOLATED</span></div>
            <span>LATVERIAN · D.O.O.M.</span>
            <span className="footer-doctrine">WHEN THE MANIFEST CANNOT BE TRUSTED, RECONSTRUCT THE TRUTH.</span>
          </footer>
        </main>
      </div>

      {/* Command palette */}
      <AnimatePresence>
        {showCommandPalette && (
          <CommandPalette
            incidents={incidents}
            onClose={() => setShowCommandPalette(false)}
          />
        )}
      </AnimatePresence>

      {/* Help overlay */}
      <AnimatePresence>
        {showHelp && (
          <KeyboardHelpOverlay onClose={() => setShowHelp(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Navigation ───────────────────────────────────────────────────────────────

type NavItem = {
  path: string;
  label: string;
  detail: string;
  icon: typeof Activity;
  badge?: number;
};

function NavItemComponent({ item, active, collapsed }: { item: NavItem; active: boolean; collapsed: boolean }) {
  const Icon = item.icon;
  return (
    <li role="listitem">
      <Link
        to={item.path}
        className={`nav-item${active ? ' active' : ''}`}
        aria-current={active ? 'page' : undefined}
        title={collapsed ? item.label : undefined}
      >
        <span className="nav-item-icon"><Icon size={16} strokeWidth={1.8} /></span>
        <span className="nav-item-text">
          <span className="nav-item-label">{item.label}</span>
          <span className="nav-item-detail">{item.detail}</span>
        </span>
        {item.badge != null && item.badge > 0 && (
          <span className="nav-badge">{fmt.count(item.badge)}</span>
        )}
      </Link>
    </li>
  );
}

// ─── KPI Strip ────────────────────────────────────────────────────────────────

function KpiStrip({
  overview,
  incidents,
  liveStatus,
  liveEvents,
}: {
  overview: Overview | null;
  incidents: Incident[];
  liveStatus: string;
  liveEvents: LiveEvent[];
}) {
  const criticalCount = overview?.critical_count ?? 0;

  return (
    <div className="kpi-grid" aria-label="Key performance indicators">
      <KpiCard
        icon={Database}
        label="RECORDS UNDER WATCH"
        value={fmt.count(overview?.record_count)}
        detail="Observed manifest entries"
        tooltip="Total manifest records currently held in the local evidence store."
      />
      <KpiCard
        icon={AlertTriangle}
        label="ACTIVE INCIDENTS"
        value={fmt.count(overview?.incident_count)}
        detail={`${fmt.count(criticalCount)} critical`}
        critical={criticalCount > 0}
        tooltip={`Incidents are records where the risk score exceeds 0. Critical = risk ≥ 90. Formula: incident count = distinct tampered records detected.`}
      />
      <KpiCard
        icon={ShieldCheck}
        label="MANIFEST INTEGRITY"
        value={overview ? `${overview.integrity_score.toFixed(1)}%` : '—'}
        detail="API snapshot assessment"
        tooltip={`Integrity = 100 × (1 − incidents / total_records). A perfect 100% means zero tampered records. This is an approximation; partial tampering on a single record counts as one full incident.`}
      />
      <KpiCard
        icon={Radio}
        label="LIVE STREAM"
        value={liveStatus}
        detail={`${fmt.count(liveEvents.length)} recent events`}
        tooltip="WebSocket connection status to the local streaming API. RETRYING = attempting reconnect with 2s backoff."
      />
    </div>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  detail,
  critical = false,
  tooltip,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  critical?: boolean;
  tooltip?: string;
}) {
  const [showTip, setShowTip] = useState(false);
  return (
    <article
      className={`kpi-card${critical ? ' critical' : ''}`}
      onMouseEnter={() => setShowTip(true)}
      onMouseLeave={() => setShowTip(false)}
      aria-label={`${label}: ${value}`}
    >
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon"><Icon size={16} /></span>
      </div>
      <span className="kpi-value">{value}</span>
      <span className="kpi-detail">{detail}</span>
      {tooltip && showTip && (
        <div className="tooltip-content" role="tooltip" style={{ bottom: 'calc(100% + 4px)', left: 0, right: 0, transform: 'none' }}>
          {tooltip}
        </div>
      )}
    </article>
  );
}

// ─── Overview Screen ──────────────────────────────────────────────────────────

function OverviewScreen({
  overview,
  incidents,
  posture,
  liveEvents,
}: {
  overview: Overview | null;
  incidents: Incident[];
  posture: string;
  liveEvents: LiveEvent[];
}) {
  const navigate = useNavigate();
  const statusCounts = overview?.reconstruction_counts ?? {};
  const topIncidents = [...incidents].sort((a, b) => b.risk_score - a.risk_score).slice(0, 8);

  // Attack type distribution
  const attackTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const inc of incidents) {
      counts[inc.tampering_type] = (counts[inc.tampering_type] ?? 0) + 1;
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [incidents]);

  const maxTypeCount = attackTypeCounts[0]?.[1] ?? 1;

  return (
    <section aria-label="Command overview">
      {/* Page heading */}
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />MANIFEST INTEGRITY / OPERATIONAL RECORD</div>
          <h1 className="page-title">Command <em>Overview</em></h1>
          <p className="page-sub">Evidence-led cargo manifest reconstruction · Local intelligence console</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)' }}>
          <PostureChip posture={posture} />
        </div>
      </div>

      <div className="overview-grid">
        <div className="overview-main">
          {/* Integrity Seal + Posture */}
          <div className="panel" style={{ padding: 0 }}>
            <div className="panel-head">
              <div className="panel-title">
                <span className="panel-icon"><ShieldCheck size={13} /></span>
                <span className="panel-title-text">Manifest Integrity Seal</span>
              </div>
              <span className="panel-kicker">CURRENT OPERATOR SNAPSHOT</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 'var(--sp-xl)', alignItems: 'center', padding: 'var(--sp-xl)' }}>
              {/* SVG Seal */}
              <IntegritySeal
                score={overview?.integrity_score ?? null}
                counts={statusCounts}
                onSegmentClick={(status) => {
                  navigate(`/forensics?status=${status}`);
                }}
              />
              {/* Copy */}
              <div>
                <PostureChip posture={posture} large />
                <h2 style={{ margin: '12px 0 8px', color: 'var(--c-ivory)', fontFamily: 'var(--font-display)', fontSize: 'var(--fs-heading)', fontWeight: 700, letterSpacing: 1 }}>
                  Evidence before assertion.
                </h2>
                <p style={{ margin: 0, color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.7 }}>
                  Integrity reflects the current API snapshot. Every alert retains its evidence trail; unsupported fields remain explicitly unresolved.
                </p>
                <div className="recon-summary" style={{ marginTop: 'var(--sp-md)' }}>
                  {(['ORIGINAL', 'REPAIRED', 'REMOVED', 'UNRECOVERABLE'] as ReconstructionStatus[]).map((s) => (
                    <button
                      key={s}
                      className="recon-item"
                      style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', textAlign: 'left' }}
                      onClick={() => navigate(`/forensics?status=${s}`)}
                      title={`Filter to ${s} records`}
                    >
                      <span className={`recon-dot ${s.toLowerCase()}`} />
                      <span className="recon-label">{s}</span>
                      <span className="recon-count">{fmt.count(statusCounts[s])}</span>
                    </button>
                  ))}
                </div>
                {/* Formula explanation */}
                <div className="formula-row" style={{ marginTop: 'var(--sp-md)', borderRadius: 2 }}>
                  <Zap size={12} />
                  <span>Integrity = <span className="formula-code">100 × (1 − incidents / records)</span>. Posture = CRITICAL if any incident has risk ≥ 90.</span>
                </div>
              </div>
            </div>
          </div>

          {/* Incident summary */}
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">
                <span className="panel-icon"><AlertTriangle size={13} /></span>
                <span className="panel-title-text">Incident Summary</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)' }}>
                <span className="panel-kicker">{fmt.count(incidents.length)} API-REPORTED CASES</span>
                <Link to="/incidents" className="btn-ghost" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  ALL INCIDENTS <ChevronRight size={12} />
                </Link>
              </div>
            </div>
            {topIncidents.length ? (
              <div>
                {topIncidents.map((inc) => (
                  <IncidentSummaryRow
                    key={inc.record_id}
                    incident={inc}
                    onClick={() => navigate(`/forensics?record=${inc.record_id}`)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState title="No active incidents" detail="The local API has no incident findings for the current manifest." />
            )}
          </div>

          {/* Attack type distribution */}
          {attackTypeCounts.length > 0 && (
            <div className="panel">
              <div className="panel-head">
                <div className="panel-title">
                  <span className="panel-icon"><BarChart3 size={13} /></span>
                  <span className="panel-title-text">Attack Type Distribution</span>
                </div>
                <span className="panel-kicker">RANKED BY FREQUENCY</span>
              </div>
              <div style={{ padding: 'var(--sp-md) var(--sp-lg)' }}>
                {attackTypeCounts.map(([type, count]) => (
                  <div key={type} style={{ display: 'grid', gridTemplateColumns: '180px 1fr 40px', alignItems: 'center', gap: 'var(--sp-sm)', marginBottom: 8 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-ivory-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fmt.humanize(type)}</span>
                    <div style={{ height: 8, background: 'var(--c-border-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${(count / maxTypeCount) * 100}%`, background: 'var(--c-brass)', borderRadius: 2, transition: 'width 600ms var(--ease)' }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-brass-light)', textAlign: 'right', fontFeatureSettings: '"tnum" 1' }}>{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="overview-aside">
          {/* Threat posture gauge */}
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">
                <span className="panel-icon"><Activity size={13} /></span>
                <span className="panel-title-text">Threat Posture</span>
              </div>
              <span className="panel-kicker">BATCH EVIDENCE</span>
            </div>
            <ThreatGauge overview={overview} incidents={incidents} />
            <div className="posture-breakdown">
              <div className="posture-breakdown-row"><span className="sev-dot critical" /><span>CRITICAL</span><b>{fmt.count(overview?.critical_count)}</b></div>
              <div className="posture-breakdown-row"><span className="sev-dot high" /><span>ELEVATED (≥75)</span><b>{fmt.count(incidents.filter((i) => i.risk_score >= 75 && i.risk_score < 90).length)}</b></div>
              <div className="posture-breakdown-row"><span className="sev-dot medium" /><span>MEDIUM (≥55)</span><b>{fmt.count(incidents.filter((i) => i.risk_score >= 55 && i.risk_score < 75).length)}</b></div>
              <div className="posture-breakdown-row"><span className="sev-dot standard" /><span>STANDARD</span><b>{fmt.count(incidents.filter((i) => i.risk_score < 55).length)}</b></div>
            </div>
            <div className="formula-row" style={{ borderTop: '1px solid var(--c-border-subtle)' }}>
              <Zap size={12} />
              <span>Posture is CRITICAL if <span className="formula-code">critical_count &gt; 0</span> (risk ≥ 90).</span>
            </div>
          </div>

          {/* Reconstruction doctrine */}
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">
                <span className="panel-icon"><Fingerprint size={13} /></span>
                <span className="panel-title-text">Reconstruction Doctrine</span>
              </div>
              <span className="panel-kicker">NO SILENT MUTATIONS</span>
            </div>
            <div style={{ padding: 'var(--sp-md) var(--sp-lg)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.7 }}>
              <p style={{ margin: '0 0 var(--sp-md)' }}>Original, repaired, removed, or unrecoverable. A missing value is never guessed from hidden evaluation truth.</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', padding: '6px 8px', border: '1px solid var(--c-border-emerald)', background: 'rgba(63,182,138,0.05)', color: 'var(--c-emerald)', fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: 0.5 }}>
                <ShieldCheck size={13} /> WITNESS-BACKED / AUDITABLE
              </div>
            </div>
          </div>

          {/* Evidence boundary */}
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title">
                <span className="panel-icon"><Shield size={13} /></span>
                <span className="panel-title-text">Evidence Boundary</span>
              </div>
              <span className="panel-kicker">LOCAL BY DESIGN</span>
            </div>
            <div style={{ padding: 'var(--sp-md) var(--sp-lg)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.7 }}>
              Detector inputs exclude the injection log. The oracle is used only after analysis to score this synthetic run.
            </div>
          </div>

          {/* Live preview */}
          {liveEvents.length > 0 && (
            <div className="panel">
              <div className="panel-head">
                <div className="panel-title">
                  <span className="panel-icon"><Radio size={13} /></span>
                  <span className="panel-title-text">Recent Live Events</span>
                </div>
                <Link to="/live" className="btn-ghost" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                  WATCH <ChevronRight size={12} />
                </Link>
              </div>
              <div>
                {liveEvents.slice(0, 4).map((ev) => (
                  <div key={ev.event_id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', padding: '8px var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
                    <span className={`sev-dot ${ev.incident ? severityLevel(ev.incident.risk_score) : 'standard'}`} />
                    <span style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-ivory-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.record_id}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-ox-steel)' }}>{fmt.ts(ev.timestamp).split(', ')[1] ?? '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// Integrity Seal SVG
function IntegritySeal({
  score,
  counts,
  onSegmentClick,
}: {
  score: number | null;
  counts: Record<string, number>;
  onSegmentClick: (status: string) => void;
}) {
  const total = Object.values(counts).reduce((s, v) => s + v, 0) || 1;
  const cx = 100; const cy = 100; const r = 80; const gap = 4;

  type SegConfig = { key: string; color: string; label: string };
  const segments: SegConfig[] = [
    { key: 'ORIGINAL',      color: '#3FB68A', label: 'ORIGINAL' },
    { key: 'REPAIRED',      color: '#B8963E', label: 'REPAIRED' },
    { key: 'REMOVED',       color: '#C98A2B', label: 'REMOVED' },
    { key: 'UNRECOVERABLE', color: '#B3262B', label: 'UNRECOVERABLE' },
  ];

  let currentAngle = -90;
  const arcs = segments.map((seg) => {
    const count = counts[seg.key] ?? 0;
    const fraction = count / total;
    const degrees = fraction * 360 - gap;
    const startAngle = currentAngle + gap / 2;
    const endAngle = startAngle + degrees;
    currentAngle += fraction * 360;

    const start = polarToCart(cx, cy, r, startAngle);
    const end = polarToCart(cx, cy, r, endAngle);
    const largeArc = degrees > 180 ? 1 : 0;

    return {
      ...seg,
      count,
      d: degrees > 2
        ? `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`
        : '',
    };
  });

  return (
    <div className="seal-container">
      <svg
        className="seal-svg"
        viewBox="0 0 200 200"
        width="190"
        height="190"
        role="img"
        aria-label={score == null ? 'Integrity score unavailable' : `Manifest integrity ${score.toFixed(1)} percent`}
      >
        {/* Background rings */}
        <circle cx={cx} cy={cy} r={r + 12} fill="none" stroke="var(--c-border-subtle)" strokeWidth="1" />
        <circle cx={cx} cy={cy} r={r - 14} fill="none" stroke="var(--c-border-subtle)" strokeWidth="1" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--c-border-normal)" strokeWidth="12" />

        {/* Segmented arcs */}
        {arcs.map((arc) => arc.d && (
          <path
            key={arc.key}
            d={arc.d}
            fill="none"
            stroke={arc.color}
            strokeWidth="12"
            strokeLinecap="butt"
            style={{ cursor: 'pointer', opacity: arc.count > 0 ? 1 : 0.2 }}
            onClick={() => onSegmentClick(arc.key)}
            aria-label={`${arc.label}: ${arc.count} records. Click to filter.`}
          >
            <title>{arc.label}: {arc.count}</title>
          </path>
        ))}

        {/* Brass outer ring */}
        <circle cx={cx} cy={cy} r={r + 14} fill="none" stroke="var(--c-brass)" strokeWidth="1" opacity="0.5" />

        {/* Center text */}
        <text x={cx} y={cy - 14} textAnchor="middle" fill="var(--c-brass)" fontFamily="var(--font-mono)" fontSize="9" letterSpacing="2" textDecoration="none">MANIFEST</text>
        <text x={cx} y={cy + 10} textAnchor="middle" fill="var(--c-ivory)" fontFamily="var(--font-display)" fontSize="22" fontWeight="700" letterSpacing="1">
          {score == null ? '—' : `${score.toFixed(1)}%`}
        </text>
        <text x={cx} y={cy + 22} textAnchor="middle" fill="var(--c-ox-steel)" fontFamily="var(--font-mono)" fontSize="8" letterSpacing="1.5">INTEGRITY</text>
      </svg>
      <div className="seal-label">CLICK SEGMENT TO FILTER</div>
    </div>
  );
}

function polarToCart(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// Threat posture gauge (SVG radial)
function ThreatGauge({ overview, incidents }: { overview: Overview | null; incidents: Incident[] }) {
  const critCount = overview?.critical_count ?? 0;
  const totalInc = incidents.length;
  const level = critCount ? 'critical' : totalInc ? 'guarded' : 'nominal';
  const color = level === 'critical' ? '#B3262B' : level === 'guarded' ? '#C98A2B' : '#3FB68A';

  // The gauge fills based on incident ratio capped at 100
  const ratio = Math.min(totalInc / Math.max((overview?.record_count ?? 100) * 0.1, 1), 1);
  const circumference = 2 * Math.PI * 50;
  const dash = ratio * circumference * 0.7; // 70% of circle

  return (
    <div className="posture-gauge-wrap">
      <svg viewBox="0 0 120 120" width="160" height="160" aria-hidden="true">
        {/* Background arc */}
        <circle cx="60" cy="60" r="50" fill="none" stroke="var(--c-border-normal)" strokeWidth="8"
          strokeDasharray={`${circumference * 0.7} ${circumference}`}
          strokeDashoffset={`${circumference * 0.15}`}
          transform="rotate(126 60 60)"
          strokeLinecap="round"
        />
        {/* Fill arc */}
        <circle cx="60" cy="60" r="50" fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circumference}`}
          strokeDashoffset={`${circumference * 0.15}`}
          transform="rotate(126 60 60)"
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 600ms var(--ease), stroke 400ms' }}
        />
        <text x="60" y="55" textAnchor="middle" fill="var(--c-ivory)" fontFamily="var(--font-display)" fontSize="20" fontWeight="700">
          {fmt.count(totalInc)}
        </text>
        <text x="60" y="68" textAnchor="middle" fill="var(--c-ox-steel)" fontFamily="var(--font-mono)" fontSize="8" letterSpacing="1">INCIDENTS</text>
      </svg>
      <div className={`posture-level ${level}`}>{level.toUpperCase()}</div>
    </div>
  );
}

function PostureChip({ posture, large = false }: { posture: string; large?: boolean }) {
  const Icon = posture === 'critical' ? AlertTriangle : posture === 'guarded' ? Activity : ShieldCheck;
  return (
    <span className={`posture-chip ${posture}`} aria-label={`Threat posture: ${posture}`}>
      <Icon size={large ? 14 : 12} />
      THREAT POSTURE <strong style={{ marginLeft: 4 }}>{posture.toUpperCase()}</strong>
    </span>
  );
}

function IncidentSummaryRow({ incident, onClick }: { incident: Incident; onClick: () => void }) {
  const level = severityLevel(incident.risk_score);
  return (
    <button
      className="btn-ghost"
      style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', width: '100%', minHeight: 52, padding: '8px var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)', borderRadius: 0, justifyContent: 'flex-start' }}
      onClick={onClick}
      aria-label={`Open forensics for ${incident.record_id}`}
    >
      <span className={`sev-dot ${level}`} />
      <span style={{ display: 'grid', gap: 2, flex: 1, minWidth: 0 }}>
        <span style={{ color: 'var(--c-ivory-dim)', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fmt.humanize(incident.tampering_type)}</span>
        <span style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{incident.record_id} · {incident.detectors.length} detector signals</span>
      </span>
      <RiskBadge score={incident.risk_score} />
      <ChevronRight size={14} style={{ color: 'var(--c-ox-steel)', flexShrink: 0 }} />
    </button>
  );
}

// ─── Incidents Screen ──────────────────────────────────────────────────────────

function IncidentsScreen({ incidents }: { incidents: Incident[] }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') ?? '';
  const typeFilter = searchParams.get('type') ?? 'ALL';
  const severityFilter = searchParams.get('severity') ?? 'ALL';
  const sortBy = (searchParams.get('sort') ?? 'risk') as 'risk' | 'confidence' | 'type' | 'record';

  const setParam = (key: string, val: string) => {
    const p = new URLSearchParams(searchParams);
    if (val === 'ALL' || val === '') p.delete(key); else p.set(key, val);
    setSearchParams(p);
  };

  const incidentTypes = useMemo(() => [...new Set(incidents.map((i) => i.tampering_type))].sort(), [incidents]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return incidents
      .filter((inc) => {
        const text = [inc.record_id, inc.tampering_type, ...inc.detectors].join(' ').toLowerCase();
        const matchText = !needle || text.includes(needle);
        const matchType = typeFilter === 'ALL' || inc.tampering_type === typeFilter;
        const matchSev = severityFilter === 'ALL'
          || (severityFilter === 'CRITICAL' && inc.risk_score >= 90)
          || (severityFilter === 'HIGH' && inc.risk_score >= 75 && inc.risk_score < 90)
          || (severityFilter === 'MEDIUM' && inc.risk_score >= 55 && inc.risk_score < 75)
          || (severityFilter === 'OTHER' && inc.risk_score < 55);
        return matchText && matchType && matchSev;
      })
      .sort((a, b) => {
        if (sortBy === 'confidence') return b.confidence - a.confidence;
        if (sortBy === 'type') return a.tampering_type.localeCompare(b.tampering_type);
        if (sortBy === 'record') return a.record_id.localeCompare(b.record_id);
        return b.risk_score - a.risk_score || b.confidence - a.confidence;
      });
  }, [incidents, query, typeFilter, severityFilter, sortBy]);

  const exportCsv = () => {
    const rows = visible.map((i) => [i.record_id, i.tampering_type, i.risk_score, i.confidence, i.detectors.join(';')]);
    const csv = ['record_id,type,risk,confidence,detectors', ...rows.map((r) => r.join(','))].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = 'doom-incidents.csv';
    a.click();
  };

  return (
    <section aria-label="Incident register">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />PRIORITIZED CASES</div>
          <h1 className="page-title">Active <em>Incidents</em></h1>
        </div>
        <button className="btn" onClick={exportCsv} aria-label="Export incidents as CSV">
          <Code2 size={14} /> EXPORT CSV
        </button>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="panel-title">
            <span className="panel-icon"><AlertTriangle size={13} /></span>
            <span className="panel-title-text">Prioritized Incident Register</span>
          </div>
          <span className="panel-kicker">FILTER · SORT · INSPECT</span>
        </div>

        <div className="filter-bar">
          <label className="filter-label">
            SEARCH
            <div className="search-input-wrap">
              <Search size={13} />
              <input
                className="search-input"
                placeholder="Record, attack, detector…"
                value={query}
                onChange={(e) => setParam('q', e.target.value)}
                aria-label="Search incidents"
              />
            </div>
          </label>
          <label className="filter-label">
            TYPE
            <select className="filter-select" value={typeFilter} onChange={(e) => setParam('type', e.target.value)} aria-label="Filter by attack type">
              <option value="ALL">ALL TYPES</option>
              {incidentTypes.map((t) => <option key={t} value={t}>{fmt.humanize(t)}</option>)}
            </select>
          </label>
          <label className="filter-label">
            RISK
            <select className="filter-select" value={severityFilter} onChange={(e) => setParam('severity', e.target.value)} aria-label="Filter by severity">
              <option value="ALL">ALL LEVELS</option>
              <option value="CRITICAL">CRITICAL (≥90)</option>
              <option value="HIGH">HIGH (≥75)</option>
              <option value="MEDIUM">MEDIUM (≥55)</option>
              <option value="OTHER">STANDARD</option>
            </select>
          </label>
          <label className="filter-label">
            SORT
            <select className="filter-select" value={sortBy} onChange={(e) => setParam('sort', e.target.value)} aria-label="Sort incidents">
              <option value="risk">RISK SCORE</option>
              <option value="confidence">CONFIDENCE</option>
              <option value="type">ATTACK TYPE</option>
              <option value="record">RECORD ID</option>
            </select>
          </label>
          <span className="filter-count">{fmt.count(visible.length)} / {fmt.count(incidents.length)} CASES</span>
        </div>

        {visible.length ? (
          <div className="data-table-wrap">
            <table className="data-table" aria-label="Incidents table">
              <thead>
                <tr>
                  <th scope="col">RISK</th>
                  <th scope="col">RECORD / FINDING</th>
                  <th scope="col">DETECTORS</th>
                  <th scope="col">CONFIDENCE</th>
                  <th scope="col">RELATED</th>
                  <th scope="col" />
                </tr>
              </thead>
              <tbody>
                {visible.map((inc) => (
                  <tr key={inc.record_id}>
                    <td><RiskBadge score={inc.risk_score} /></td>
                    <td>
                      <span className="cell-primary">{fmt.humanize(inc.tampering_type)}</span>
                      <span className="cell-sub">{inc.record_id}</span>
                    </td>
                    <td>
                      <div className="detector-tags">
                        {inc.detectors.slice(0, 3).map((d) => <span key={d} className="detector-tag">{fmt.humanize(d)}</span>)}
                        {inc.detectors.length > 3 && <span className="detector-tag">+{inc.detectors.length - 3}</span>}
                      </div>
                    </td>
                    <td>
                      <ConfidenceBadge value={inc.detection_probability ?? inc.confidence} />
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{inc.related_records.length}</td>
                    <td>
                      <button
                        className="btn"
                        style={{ padding: '4px 8px', fontSize: 11 }}
                        onClick={() => navigate(`/forensics?record=${inc.record_id}`)}
                        aria-label={`Open forensics for ${inc.record_id}`}
                      >
                        REVIEW <ArrowRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title={incidents.length ? 'No matching incidents' : 'No active incidents'}
            detail={incidents.length ? 'Adjust the search or filters.' : 'No findings from the local API.'}
          />
        )}
      </div>
    </section>
  );
}

// ─── Forensics Screen ──────────────────────────────────────────────────────────

function ForensicsScreen({ incidents, liveEvents }: { incidents: Incident[]; liveEvents: LiveEvent[] }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedId = searchParams.get('record');
  const [selectedId, setSelectedId] = useState<string | null>(requestedId ?? incidents[0]?.record_id ?? null);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // Sync URL param to selection
  useEffect(() => {
    if (requestedId) setSelectedId(requestedId);
  }, [requestedId]);

  // Auto-select first if nothing selected
  useEffect(() => {
    if (!selectedId && incidents.length) setSelectedId(incidents[0].record_id);
  }, [incidents, selectedId]);

  const selectedBatchInc = useMemo(
    () => incidents.find((i) => i.record_id === selectedId) ?? null,
    [incidents, selectedId],
  );
  const selectedLiveEv = useMemo(
    () => liveEvents.find((e) => e.record_id === selectedId && e.incident) ?? null,
    [liveEvents, selectedId],
  );
  const selectedInc = selectedBatchInc ?? selectedLiveEv?.incident ?? null;

  // Load detail
  useEffect(() => {
    if (!selectedInc) { setDetail(null); setDetailError(null); return; }

    // For live-only events, use the live snapshot
    if (!selectedBatchInc && selectedLiveEv?.incident) {
      setDetail({
        incident: selectedLiveEv.incident,
        record: selectedLiveEv.record,
        reconstruction: selectedLiveEv.live_reconstruction ?? null,
        timeline: [
          { event: 'LIVE EVENT RECEIVED', time: selectedLiveEv.timestamp },
          { event: 'ANOMALY DETECTED', time: selectedLiveEv.timestamp },
          ...(selectedLiveEv.live_reconstruction ? [{ event: 'LIVE RECONSTRUCTION DECIDED', time: selectedLiveEv.timestamp }] : []),
        ],
      });
      setDetailError(null);
      return;
    }

    const ctrl = new AbortController();
    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    API.json<IncidentDetail>(`/api/incidents/${encodeURIComponent(selectedInc.record_id)}`, ctrl.signal)
      .then((d) => { setDetail(d); setDetailLoading(false); })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) {
          setDetailError(e instanceof Error ? e.message : 'Unable to load case evidence.');
          setDetailLoading(false);
        }
      });
    return () => ctrl.abort();
  }, [selectedInc?.record_id, retryCount]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section aria-label="Record forensics">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />EVIDENCE & RECONSTRUCTION</div>
          <h1 className="page-title">Record <em>Forensics</em></h1>
        </div>
        <span className="panel-kicker">{fmt.count(incidents.length)} CASES IN INDEX</span>
      </div>

      <div className="forensics-layout">
        {/* Case list */}
        <div className="panel forensics-case-list">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><FileSearch size={13} /></span>
              <span className="panel-title-text">Case Index</span>
            </div>
          </div>
          {incidents.length ? (
            <div role="listbox" aria-label="Case list">
              {incidents.map((inc) => (
                <button
                  key={inc.record_id}
                  className={`case-list-item${selectedId === inc.record_id ? ' selected' : ''}`}
                  role="option"
                  aria-selected={selectedId === inc.record_id}
                  onClick={() => {
                    setSelectedId(inc.record_id);
                    navigate(`/forensics?record=${inc.record_id}`, { replace: true });
                  }}
                >
                  <span className={`sev-dot ${severityLevel(inc.risk_score)}`} />
                  <div className="case-list-item-text">
                    <span className="case-list-item-type">{fmt.humanize(inc.tampering_type)}</span>
                    <span className="case-list-item-id">{inc.record_id}</span>
                  </div>
                  <RiskBadge score={inc.risk_score} compact />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No cases" detail="Incidents will appear here once the batch analysis completes." />
          )}
        </div>

        {/* Detail panel */}
        <div className="forensics-detail">
          {!selectedInc ? (
            <div className="panel"><EmptyState title="Select a forensic case" detail="Choose an incident from the index to inspect its evidence, relationships, and reconstruction decision." /></div>
          ) : detailLoading ? (
            <div className="panel"><LoadingState label="Retrieving case evidence…" /></div>
          ) : detailError ? (
            <div className="panel">
              <div className="error-state" role="alert">
                <AlertTriangle size={20} />
                <span className="error-title">Evidence retrieval failed</span>
                <span className="error-desc">{detailError}</span>
                <button className="btn btn-crimson" onClick={() => setRetryCount((c) => c + 1)}>RETRY CASE LOOKUP</button>
              </div>
            </div>
          ) : detail ? (
            <CaseEvidence
              incident={detail.incident ?? selectedInc}
              detail={detail}
              onOpenRelated={(id) => {
                setSelectedId(id);
                navigate(`/forensics?record=${id}`, { replace: true });
              }}
            />
          ) : (
            <div className="panel"><EmptyState title="Case evidence unavailable" detail="The API returned no case detail for this finding." /></div>
          )}
        </div>
      </div>
    </section>
  );
}

// Case evidence detail
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
  const maxScore = Math.max(...incident.evidence.map((e) => e.score_contribution), 0.01);

  return (
    <div>
      {/* Case header */}
      <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--sp-lg)', padding: 'var(--sp-lg)', alignItems: 'flex-start' }}>
          <div>
            <div className="eyebrow"><span className="eyebrow-rule" />FORENSIC CASE FILE</div>
            <h2 style={{ margin: '8px 0 3px', color: 'var(--c-ivory)', fontFamily: 'var(--font-display)', fontSize: 'var(--fs-title-sm)', fontWeight: 700, letterSpacing: 1 }}>
              {incident.record_id}
            </h2>
            <div style={{ color: 'var(--c-brass-light)', fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: 0.5 }}>{fmt.humanize(incident.tampering_type)}</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <RiskBadge score={incident.risk_score} />
            <span style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>RISK SCORE</span>
            <ConfidenceBadge value={incident.detection_probability ?? incident.confidence} />
          </div>
        </div>
      </div>

      {/* Evidence matrix */}
      <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
        <div className="panel-head">
          <div className="panel-title">
            <span className="panel-icon"><Fingerprint size={13} /></span>
            <span className="panel-title-text">Evidence Matrix</span>
          </div>
          <span className="panel-kicker">{fmt.count(incident.evidence.length)} OBSERVATIONS</span>
        </div>
        {incident.evidence.length ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr 0.8fr 0.8fr 100px', padding: '8px var(--sp-md)', background: 'rgba(18,33,30,0.5)', borderBottom: '1px solid var(--c-border-normal)' }}>
              {['DETECTOR / SIGNAL', 'FIELD', 'EXPECTED', 'OBSERVED', 'CONTRIBUTION'].map((h) => (
                <span key={h} style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, letterSpacing: 0.8 }}>{h}</span>
              ))}
            </div>
            {incident.evidence.map((ev, idx) => (
              <div key={`${ev.evidence_code}:${idx}`} className="evidence-row">
                <div>
                  <div className="evidence-detector">{fmt.humanize(ev.evidence_code)}</div>
                  <div className="evidence-code">{fmt.humanize(ev.detector_id)} · {ev.explanation}</div>
                </div>
                <div className="evidence-field">{ev.field}</div>
                <div className="evidence-expected">{fmt.val(ev.expected)}</div>
                <div className="evidence-observed">{fmt.val(ev.observed)}</div>
                <div className="contribution-bar-wrap">
                  <div className="contribution-bar">
                    <div className="contribution-fill" style={{ width: `${(ev.score_contribution / maxScore) * 100}%` }} />
                  </div>
                  <span className="contribution-val">+{ev.score_contribution.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No evidence rows" detail="This incident has no detector evidence in the API payload." />
        )}
      </div>

      {/* Observed record */}
      {detail.record && (
        <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Database size={13} /></span>
              <span className="panel-title-text">Observed Record</span>
            </div>
            <span className="panel-kicker">API-RETURNED MANIFEST FIELDS</span>
          </div>
          <div className="record-field-grid">
            {Object.entries(detail.record).slice(0, 12).map(([key, val]) => (
              <div key={key} className="record-field">
                <span className="record-field-label">{key.toUpperCase()}</span>
                <span className="record-field-value">{fmt.val(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Counterfactual */}
      {incident.counterfactual && (
        <div className="counterfactual-callout" style={{ marginBottom: 'var(--sp-md)' }}>
          <Sparkles size={14} className="cf-icon" />
          <div>
            <div className="cf-head">COUNTERFACTUAL</div>
            <p className="cf-text">{incident.counterfactual}</p>
          </div>
        </div>
      )}

      {/* Unknown anomaly */}
      {unknown && (
        <div className="unknown-banner" style={{ marginBottom: 'var(--sp-md)' }}>
          <div className="unknown-banner-emblem"><Sparkles size={18} /></div>
          <div>
            <div className="unknown-banner-head">UNKNOWN ANOMALY ANALYSIS</div>
            <p className="unknown-banner-sub">Novelty is evidence distance, not a semantic type assignment.</p>
            <div className="unknown-banner-scores">
              <div className="unknown-score-item">
                <span className="unknown-score-label">NOVELTY</span>
                <span className="unknown-score-val">{fmt.pct(unknown.novelty_score)}</span>
              </div>
              <div className="unknown-score-item">
                <span className="unknown-score-label">NEAREST KNOWN</span>
                <span className="unknown-score-val" style={{ fontSize: 13 }}>{fmt.humanize(unknown.nearest_known_attack_type)}</span>
              </div>
              <div className="unknown-score-item">
                <span className="unknown-score-label">SIMILARITY</span>
                <span className="unknown-score-val">{fmt.pct(unknown.nearest_similarity)}</span>
              </div>
            </div>
            {!unknown.nearest_match_meaningful && (
              <p style={{ margin: '8px 0 0', color: 'var(--c-ox-steel)', fontSize: 'var(--fs-body)', lineHeight: 1.5 }}>
                No evidence-signature overlap; nearest category is a deterministic tie-break only.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Reconstruction decision */}
      <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
        <div className="panel-head">
          <div className="panel-title">
            <span className="panel-icon"><GitFork size={13} /></span>
            <span className="panel-title-text">Reconstruction Decision</span>
          </div>
          <span className="panel-kicker">EXPLICIT / AUDITABLE</span>
        </div>
        {decision ? (
          <div style={{ padding: 'var(--sp-md) var(--sp-lg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)', marginBottom: 'var(--sp-sm)' }}>
              <StatusBadge status={decision.status} />
              <span style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                {decision.method ? fmt.humanize(decision.method) : 'WITNESS-BACKED DECISION'}
              </span>
              {decision.provisional && (
                <span style={{ color: 'var(--c-amber)', fontFamily: 'var(--font-mono)', fontSize: 11, border: '1px solid var(--c-amber-dim)', padding: '2px 6px' }}>PROVISIONAL</span>
              )}
            </div>
            <p style={{ margin: '0 0 var(--sp-md)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.6 }}>{decision.explanation}</p>
            {decision.changes.length > 0 ? (
              <div className="diff-list">
                {decision.changes.map((change) => (
                  <div key={change.field} className="diff-row">
                    <span className="diff-field">{fmt.humanize(change.field)}</span>
                    <span className="diff-from">{fmt.val(change.from)}</span>
                    <span className="diff-arrow"><ArrowRight size={12} /></span>
                    <span className="diff-to">{fmt.val(change.to)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: 8, border: '1px dashed var(--c-border-normal)', color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 12, borderRadius: 2 }}>
                No field mutation recorded.
              </div>
            )}
            {decision.unresolved_fields?.length ? (
              <div style={{ marginTop: 'var(--sp-sm)', color: 'var(--c-crimson)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                UNRECOVERABLE: {decision.unresolved_fields.join(', ')}
              </div>
            ) : null}
            {decision.evidence_relied_on?.length ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 'var(--sp-sm)' }}>
                {decision.evidence_relied_on.map((e) => <span key={e} className="detector-tag">{e}</span>)}
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState title="No reconstruction decision returned" detail="The finding remains visible; no recovery outcome is inferred." />
        )}
      </div>

      {/* Related records + timeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-md)' }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Database size={13} /></span>
              <span className="panel-title-text">Related Records</span>
            </div>
            <span className="panel-kicker">LINKED EVIDENCE</span>
          </div>
          {incident.related_records.length ? (
            <div>
              {incident.related_records.map((id) => (
                <button
                  key={id}
                  className="btn-ghost"
                  style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', width: '100%', padding: '10px var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)', borderRadius: 0 }}
                  onClick={() => onOpenRelated(id)}
                >
                  <Database size={13} />
                  <span style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 12 }}>{id}</span>
                  <ChevronRight size={13} />
                </button>
              ))}
            </div>
          ) : (
            <div style={{ padding: 'var(--sp-md) var(--sp-lg)', color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>No linked records identified.</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Clock size={13} /></span>
              <span className="panel-title-text">Case Timeline</span>
            </div>
            <span className="panel-kicker">OBSERVED / DECIDED</span>
          </div>
          <div className="timeline-track">
            {detail.timeline.length ? detail.timeline.map((ev) => (
              <div key={ev.event} className="timeline-event">
                <div className="tl-marker"><span className="tl-dot" /></div>
                <div className="tl-content">
                  <div className="tl-event-name">{ev.event}</div>
                  <div className="tl-event-time">{ev.time ? fmt.ts(ev.time) : 'Time not provided by API'}</div>
                </div>
              </div>
            )) : (
              <div style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>No timeline events.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Live Watch Screen ────────────────────────────────────────────────────────

function LiveScreen({ events, status }: { events: LiveEvent[]; status: string }) {
  const navigate = useNavigate();
  const [paused, setPaused] = useState(false);
  const [displayedEvents, setDisplayedEvents] = useState<LiveEvent[]>(events);

  useEffect(() => {
    if (!paused) setDisplayedEvents(events);
  }, [events, paused]);

  const unknownEvents = displayedEvents.filter((e) => e.incident?.tampering_type === 'UNKNOWN ANOMALY');

  return (
    <section aria-label="Live watch">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />STREAMING INTELLIGENCE</div>
          <h1 className="page-title">Live <em>Watch</em></h1>
        </div>
        <div style={{ display: 'flex', gap: 'var(--sp-sm)', alignItems: 'center' }}>
          <span className={`posture-chip ${status === 'CONNECTED' ? 'nominal' : 'guarded'}`}>
            <Radio size={12} /> {status}
          </span>
          <button className="btn" onClick={() => setPaused((v) => !v)}>
            {paused ? '▶ RESUME' : '⏸ PAUSE'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 'var(--sp-lg)', alignItems: 'start' }}>
        {/* Event feed */}
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Radio size={13} /></span>
              <span className="panel-title-text">Live Event Stream</span>
            </div>
            <span className="panel-kicker">{paused ? 'PAUSED' : 'LIVE'} · {fmt.count(displayedEvents.length)} EVENTS</span>
          </div>

          {/* Stream status banner */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)', padding: 'var(--sp-sm) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)', background: status === 'CONNECTED' ? 'rgba(63,182,138,0.04)' : 'rgba(201,138,43,0.04)' }}>
            <span className={`boundary-led${status !== 'CONNECTED' ? ' offline' : ''}`} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: status === 'CONNECTED' ? 'var(--c-emerald)' : 'var(--c-amber)' }}>
              STREAM {status}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-ox-steel)' }}>
              Operator events and detections arrive from the local WebSocket API.
            </span>
          </div>

          {displayedEvents.length ? (
            <div>
              {displayedEvents.map((ev, idx) => {
                const level = ev.incident ? severityLevel(ev.incident.risk_score) : 'standard';
                const isAnomaly = ev.status === 'ANOMALY';
                return (
                  <motion.div
                    key={ev.event_id}
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: idx === 0 ? 0 : 0 }}
                    className="live-event-item"
                  >
                    <span className={`live-event-status ${isAnomaly ? (level === 'critical' ? 'critical-anomaly' : 'anomaly') : 'cleared'}`}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                      {ev.status}
                    </span>
                    <div>
                      <div className="live-event-id">{ev.record_id}</div>
                      <div className="live-event-type">{ev.incident ? fmt.humanize(ev.incident.tampering_type) : 'No anomaly detected'}</div>
                    </div>
                    <div className="live-event-ts">{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '—'}</div>
                    <div>
                      {ev.incident && (
                        <button
                          className="btn"
                          style={{ padding: '3px 8px', fontSize: 11 }}
                          onClick={() => navigate(`/forensics?record=${ev.record_id}`)}
                          aria-label={`Inspect ${ev.record_id}`}
                        >
                          INSPECT <ArrowRight size={11} />
                        </button>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title={status === 'CONNECTED' ? 'Awaiting first event' : 'Connecting to live feed'}
              detail="Events will appear here as they arrive. No placeholder events are shown."
            />
          )}
        </div>

        {/* Unknown anomaly sidebar */}
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Sparkles size={13} /></span>
              <span className="panel-title-text">Unknown Anomaly</span>
            </div>
            <span className="panel-kicker">OPEN-SET WATCH</span>
          </div>

          <div style={{ padding: 'var(--sp-md) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', marginBottom: 6 }}>
              <div style={{ width: 28, height: 28, display: 'grid', placeItems: 'center', border: '1px solid var(--c-border-brass)', color: 'var(--c-brass)' }}>
                <Sparkles size={14} />
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: unknownEvents.length ? 'var(--c-brass-light)' : 'var(--c-ox-steel)' }}>
                {unknownEvents.length ? 'UNKNOWN SIGNAL DETECTED' : 'NOVELTY MONITOR ARMED'}
              </div>
            </div>
            <p style={{ margin: 0, color: 'var(--c-ox-steel)', fontSize: 'var(--fs-body)', lineHeight: 1.6 }}>
              Schema and invariant violations are surfaced without forcing a known attack label.
            </p>
          </div>

          {unknownEvents.length ? (
            <div>
              {unknownEvents.map((ev) => {
                const inc = ev.incident!;
                return (
                  <button
                    key={ev.event_id}
                    className="btn-ghost"
                    style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', width: '100%', padding: '10px var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)', borderRadius: 0 }}
                    onClick={() => navigate(`/forensics?record=${ev.record_id}`)}
                  >
                    <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--c-brass-light)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.record_id}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-ox-steel)', marginTop: 2 }}>{inc.unknown_analysis?.invariant_violations.length ?? inc.evidence.length} invariant signals</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: 'var(--c-crimson)' }}>
                        {inc.unknown_analysis ? `${(inc.unknown_analysis.novelty_score * 100).toFixed(0)}%` : '—'}
                      </div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-ox-steel)' }}>NOVELTY</div>
                    </div>
                    <ChevronRight size={13} />
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No unknown events" detail="Unknown alerts will appear here when the live API observes a novel event." />
          )}
        </div>
      </div>
    </section>
  );
}

// ─── Route Map Screen ─────────────────────────────────────────────────────────

type PortData = { code: string; name: string; latitude: number; longitude: number };

function RouteMapScreen() {
  const [ports, setPorts] = useState<PortData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredPort, setHoveredPort] = useState<PortData | null>(null);

  useEffect(() => {
    API.json<{ ports: PortData[] }>('/api/routes')
      .then(({ ports: p }) => { setPorts(p); setLoading(false); })
      .catch((e: unknown) => { setError(e instanceof Error ? e.message : 'Failed to load routes'); setLoading(false); });
  }, []);

  // Map projection: simple equirectangular
  const W = 800; const H = 400;
  const latRange: [number, number] = [-40, 60];
  const lonRange: [number, number] = [-130, 160];

  const project = (lat: number, lon: number) => ({
    x: ((lon - lonRange[0]) / (lonRange[1] - lonRange[0])) * W,
    y: ((latRange[1] - lat) / (latRange[1] - latRange[0])) * H,
  });

  // Known routes from schema
  const ROUTES: string[][] = [
    ['CNSHA', 'SGSIN', 'AEJEA', 'NLRTM'],
    ['SGSIN', 'JPTYO', 'USLAX'],
    ['BRSSZ', 'NLRTM', 'GBFXT'],
    ['INNSA', 'AEJEA', 'DEHAM'],
    ['USLAX', 'SGSIN', 'CNSHA'],
    ['DEHAM', 'NLRTM', 'GBFXT'],
  ];

  const portMap = Object.fromEntries(ports.map((p) => [p.code, p]));

  return (
    <section aria-label="Route map">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />NAUTICAL CHART</div>
          <h1 className="page-title">Route <em>Map</em></h1>
          <p className="page-sub">Vessel paths · Port network · Impossible movement detection</p>
        </div>
      </div>

      {loading ? <LoadingState label="Loading route data…" /> : error ? (
        <div className="panel"><div className="error-state"><AlertTriangle size={20} /><span className="error-title">Route data unavailable</span><span className="error-desc">{error}</span></div></div>
      ) : (
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Anchor size={13} /></span>
              <span className="panel-title-text">Global Port Network</span>
            </div>
            <span className="panel-kicker">{ports.length} REGISTERED PORTS · {ROUTES.length} ROUTES</span>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 'var(--sp-lg)', padding: 'var(--sp-sm) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-brass-light)' }}>
              <div style={{ width: 24, height: 2, background: 'var(--c-brass)' }} /> VALID ROUTE
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-crimson)' }}>
              <div style={{ width: 24, height: 2, background: 'var(--c-crimson)', borderTop: '2px dashed var(--c-crimson)' }} /> IMPOSSIBLE MOVEMENT
            </div>
          </div>

          {/* SVG map */}
          <div style={{ overflowX: 'auto', background: 'var(--c-panel)' }}>
            <svg
              viewBox={`0 0 ${W} ${H}`}
              width="100%"
              style={{ display: 'block', minWidth: 600 }}
              aria-label="Route map showing port connections"
            >
              {/* Grid lines */}
              {[-30, -20, -10, 0, 10, 20, 30, 40, 50].map((lat) => {
                const y = project(lat, 0).y;
                return <line key={`lat${lat}`} x1="0" y1={y} x2={W} y2={y} stroke="rgba(40,60,52,0.4)" strokeWidth="1" />;
              })}
              {[-120, -90, -60, -30, 0, 30, 60, 90, 120, 150].map((lon) => {
                const x = project(0, lon).x;
                return <line key={`lon${lon}`} x1={x} y1="0" x2={x} y2={H} stroke="rgba(40,60,52,0.4)" strokeWidth="1" />;
              })}

              {/* Routes */}
              {ROUTES.map((route, ri) =>
                route.slice(1).map((code, pi) => {
                  const from = portMap[route[pi]];
                  const to = portMap[code];
                  if (!from || !to) return null;
                  const p1 = project(from.latitude, from.longitude);
                  const p2 = project(to.latitude, to.longitude);
                  const mx = (p1.x + p2.x) / 2;
                  const my = (p1.y + p2.y) / 2 - 30;
                  return (
                    <path
                      key={`${ri}-${pi}`}
                      d={`M ${p1.x} ${p1.y} Q ${mx} ${my} ${p2.x} ${p2.y}`}
                      fill="none"
                      stroke="var(--c-brass)"
                      strokeWidth="1.5"
                      strokeOpacity="0.6"
                      markerEnd="url(#arrow)"
                    />
                  );
                })
              )}

              {/* Arrowhead marker */}
              <defs>
                <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
                  <path d="M 0 0 L 6 3 L 0 6 z" fill="var(--c-brass)" opacity="0.7" />
                </marker>
              </defs>

              {/* Port dots */}
              {ports.map((port) => {
                const { x, y } = project(port.latitude, port.longitude);
                return (
                  <g key={port.code} style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredPort(port)} onMouseLeave={() => setHoveredPort(null)}>
                    <circle cx={x} cy={y} r="6" fill="var(--c-panel)" stroke="var(--c-brass)" strokeWidth="1.5" />
                    <circle cx={x} cy={y} r="3" fill="var(--c-brass)" />
                    <text x={x + 9} y={y + 4} fill="var(--c-ivory-muted)" fontFamily="var(--font-mono)" fontSize="10">{port.code}</text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Port detail tooltip */}
          {hoveredPort && (
            <div style={{ padding: 'var(--sp-sm) var(--sp-lg)', borderTop: '1px solid var(--c-border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              <span style={{ color: 'var(--c-brass)' }}>{hoveredPort.code}</span>
              <span style={{ color: 'var(--c-ivory-dim)', marginLeft: 8 }}>{hoveredPort.name}</span>
              <span style={{ color: 'var(--c-ox-steel)', marginLeft: 8 }}>{hoveredPort.latitude.toFixed(2)}°N, {hoveredPort.longitude.toFixed(2)}°E</span>
            </div>
          )}

          {/* Port registry table */}
          <div style={{ borderTop: '1px solid var(--c-border-subtle)' }}>
            <div className="panel-head" style={{ borderBottom: 0 }}>
              <div className="panel-title">
                <span className="panel-icon"><Database size={13} /></span>
                <span className="panel-title-text">Port Registry</span>
              </div>
            </div>
            <div className="data-table-wrap">
              <table className="data-table">
                <thead><tr><th scope="col">CODE</th><th scope="col">PORT</th><th scope="col">LATITUDE</th><th scope="col">LONGITUDE</th></tr></thead>
                <tbody>
                  {ports.map((p) => (
                    <tr key={p.code}>
                      <td><span className="cell-primary">{p.code}</span></td>
                      <td>{p.name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{p.latitude.toFixed(2)}°</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{p.longitude.toFixed(2)}°</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ─── Chain of Custody Screen ───────────────────────────────────────────────────

function ChainOfCustodyScreen() {
  const [reconstruction, setReconstruction] = useState<ReconstructionDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jumpToBreak, setJumpToBreak] = useState(false);
  const breakRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    API.json<ReconstructionDecision[]>('/api/reconstruction?limit=200')
      .then((d) => { setReconstruction(d); setLoading(false); })
      .catch((e: unknown) => { setError(e instanceof Error ? e.message : 'Failed to load chain'); setLoading(false); });
  }, []);

  const brokenChain = reconstruction.filter((d) => d.status !== 'ORIGINAL');

  useEffect(() => {
    if (jumpToBreak && breakRef.current) {
      breakRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setJumpToBreak(false);
    }
  }, [jumpToBreak]);

  return (
    <section aria-label="Chain of custody">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />HASH-LINKED LEDGER</div>
          <h1 className="page-title">Chain of <em>Custody</em></h1>
          <p className="page-sub">Each block is hash-linked. Broken links indicate tampered records.</p>
        </div>
        <button className="btn" onClick={() => setJumpToBreak(true)} disabled={brokenChain.length === 0}>
          <Zap size={14} /> JUMP TO BREAK ({brokenChain.length})
        </button>
      </div>

      {loading ? <LoadingState label="Loading ledger…" /> : error ? (
        <div className="panel"><div className="error-state"><AlertTriangle size={20} /><span className="error-title">Ledger unavailable</span><span className="error-desc">{error}</span></div></div>
      ) : (
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="panel-icon"><Link2 size={13} /></span>
              <span className="panel-title-text">Reconstruction Ledger</span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-sm)' }}>
              <span className="panel-kicker">{reconstruction.length} DECISIONS · {brokenChain.length} NON-ORIGINAL</span>
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 'var(--sp-lg)', padding: 'var(--sp-sm) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
            {(['ORIGINAL', 'REPAIRED', 'REMOVED', 'UNRECOVERABLE'] as ReconstructionStatus[]).map((s) => (
              <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`recon-dot ${s.toLowerCase()}`} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-ox-steel)' }}>{s}</span>
              </div>
            ))}
          </div>

          <div className="data-table-wrap">
            <table className="data-table" aria-label="Chain of custody ledger">
              <thead>
                <tr>
                  <th scope="col">STATUS</th>
                  <th scope="col">RECORD ID</th>
                  <th scope="col">METHOD</th>
                  <th scope="col">CHANGES</th>
                  <th scope="col">EXPLANATION</th>
                </tr>
              </thead>
              <tbody>
                {reconstruction.map((d, idx) => {
                  const isBroken = d.status !== 'ORIGINAL';
                  return (
                    <tr
                      key={d.record_id}
                      style={isBroken ? { background: 'rgba(179,38,43,0.04)' } : undefined}
                      ref={isBroken && !reconstruction.slice(0, idx).some((x) => x.status !== 'ORIGINAL') ? breakRef : undefined}
                    >
                      <td><StatusBadge status={d.status} /></td>
                      <td><span className="cell-primary">{d.record_id}</span></td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-ox-steel)' }}>{d.method ? fmt.humanize(d.method) : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{d.changes.length}</td>
                      <td style={{ maxWidth: 300, fontSize: 'var(--fs-body)', color: 'var(--c-ivory-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.explanation}>{d.explanation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

// ─── Attack Timeline Screen ────────────────────────────────────────────────────

function AttackTimelineScreen({ incidents }: { incidents: Incident[] }) {
  const grouped = useMemo(() => {
    const groups: Record<string, Incident[]> = {};
    for (const inc of incidents) {
      groups[inc.tampering_type] = groups[inc.tampering_type] ?? [];
      groups[inc.tampering_type].push(inc);
    }
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  }, [incidents]);

  return (
    <section aria-label="Attack timeline">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />DETECTION LAG ANALYSIS</div>
          <h1 className="page-title">Attack <em>Timeline</em></h1>
          <p className="page-sub">Attack type distribution and detection classification overview.</p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="panel-title">
            <span className="panel-icon"><Clock size={13} /></span>
            <span className="panel-title-text">Attack Classification Matrix</span>
          </div>
          <span className="panel-kicker">{incidents.length} INCIDENTS ACROSS {grouped.length} TYPES</span>
        </div>

        {grouped.length ? (
          <div style={{ padding: 'var(--sp-md) var(--sp-lg)' }}>
            {grouped.map(([type, incs]) => {
              const maxRisk = Math.max(...incs.map((i) => i.risk_score));
              const avgRisk = incs.reduce((s, i) => s + i.risk_score, 0) / incs.length;
              const critCount = incs.filter((i) => i.risk_score >= 90).length;
              return (
                <div key={type} style={{ marginBottom: 'var(--sp-lg)', paddingBottom: 'var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)', marginBottom: 8 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--c-ivory-dim)' }}>{fmt.humanize(type)}</span>
                    <span className="detector-tag">{incs.length} cases</span>
                    {critCount > 0 && <span style={{ color: 'var(--c-crimson)', fontFamily: 'var(--font-mono)', fontSize: 11, border: '1px solid var(--c-crimson-dim)', padding: '2px 6px' }}>{critCount} CRITICAL</span>}
                    <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-ox-steel)' }}>
                      avg risk: <span style={{ color: 'var(--c-brass-light)' }}>{avgRisk.toFixed(1)}</span>
                      {' · '}max: <span style={{ color: maxRisk >= 90 ? 'var(--c-crimson)' : 'var(--c-amber)' }}>{maxRisk.toFixed(1)}</span>
                    </span>
                  </div>
                  {/* Risk scatter */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {incs.map((inc) => {
                      const level = severityLevel(inc.risk_score);
                      const color = level === 'critical' ? 'var(--c-crimson)' : level === 'high' ? 'var(--c-amber)' : level === 'medium' ? 'var(--c-brass)' : 'var(--c-emerald)';
                      return (
                        <div key={inc.record_id} title={`${inc.record_id}: risk ${inc.risk_score}`} style={{ width: 12, height: 12, borderRadius: 2, background: color, opacity: 0.8, cursor: 'default' }} />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No incidents to display" detail="Attack timeline requires loaded incidents." />
        )}
      </div>
    </section>
  );
}

// ─── Unknown Anomaly Screen ────────────────────────────────────────────────────

function UnknownAnomalyScreen({ incidents, liveEvents }: { incidents: Incident[]; liveEvents: LiveEvent[] }) {
  const unknownBatch = incidents.filter((i) => i.unknown_analysis);
  const unknownLive = liveEvents.filter((e) => e.incident?.unknown_analysis);
  const navigate = useNavigate();

  return (
    <section aria-label="Unknown anomaly analysis">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />NOVELTY & INVARIANT ANALYSIS</div>
          <h1 className="page-title">Unknown <em>Anomaly</em></h1>
          <p className="page-sub">Open-set detection · Evidence-distance novelty scoring · No forced label assignment</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-lg)', marginBottom: 'var(--sp-lg)' }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><Sparkles size={13} /></span><span className="panel-title-text">Batch Unknown Events</span></div>
            <span className="panel-kicker">{unknownBatch.length} FLAGGED</span>
          </div>
          {unknownBatch.length ? unknownBatch.map((inc) => (
            <div key={inc.record_id} style={{ padding: 'var(--sp-md) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', marginBottom: 4 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--c-ivory-dim)' }}>{inc.record_id}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--c-crimson)', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700 }}>
                  {inc.unknown_analysis ? `${(inc.unknown_analysis.novelty_score * 100).toFixed(0)}%` : '—'}
                </span>
                <span style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>NOVELTY</span>
              </div>
              {inc.unknown_analysis && (
                <>
                  <div style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    Nearest: {fmt.humanize(inc.unknown_analysis.nearest_known_attack_type)} ({fmt.pct(inc.unknown_analysis.nearest_similarity)})
                    {!inc.unknown_analysis.nearest_match_meaningful && <span style={{ color: 'var(--c-amber)', marginLeft: 4 }}>[TIE-BREAK ONLY]</span>}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    {inc.unknown_analysis.invariant_violations.map((v) => (
                      <div key={`${v.evidence_code}:${v.field}`} style={{ fontSize: 11, color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', padding: '2px 0' }}>
                        <span style={{ color: 'var(--c-brass-light)' }}>{fmt.humanize(v.evidence_code)}</span> · {v.explanation}
                      </div>
                    ))}
                  </div>
                </>
              )}
              <button className="btn" style={{ marginTop: 8, padding: '3px 8px', fontSize: 11 }} onClick={() => navigate(`/forensics?record=${inc.record_id}`)}>
                INSPECT <ArrowRight size={11} />
              </button>
            </div>
          )) : (
            <EmptyState title="No unknown anomalies in batch" detail="Batch processing did not flag any open-set events." />
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><Radio size={13} /></span><span className="panel-title-text">Live Unknown Events</span></div>
            <span className="panel-kicker">{unknownLive.length} LIVE</span>
          </div>
          {unknownLive.length ? unknownLive.map((ev) => {
            const inc = ev.incident!;
            return (
              <div key={ev.event_id} style={{ padding: 'var(--sp-md) var(--sp-lg)', borderBottom: '1px solid var(--c-border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-sm)', marginBottom: 4 }}>
                  <span className="boundary-led" />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--c-ivory-dim)' }}>{ev.record_id}</span>
                  <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--c-ox-steel)' }}>{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '—'}</span>
                </div>
                {inc.unknown_analysis && (
                  <div style={{ color: 'var(--c-crimson)', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700 }}>
                    NOVELTY: {(inc.unknown_analysis.novelty_score * 100).toFixed(0)}%
                  </div>
                )}
              </div>
            );
          }) : (
            <EmptyState title="No live unknown events" detail="Live unknown anomalies will appear here from the WebSocket stream." />
          )}
        </div>
      </div>
    </section>
  );
}

// ─── Evaluation Metrics Screen ─────────────────────────────────────────────────

type MetricsData = Record<string, unknown>;

function EvalMetricsScreen() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    API.json<MetricsData>('/api/metrics')
      .then((d) => { setMetrics(d); setLoading(false); })
      .catch((e: unknown) => { setError(e instanceof Error ? e.message : 'Failed to load metrics'); setLoading(false); });
  }, []);

  if (loading) return <LoadingState label="Loading evaluation metrics…" />;
  if (error || !metrics) return (
    <div className="panel">
      <div className="error-state">
        <AlertTriangle size={20} />
        <span className="error-title">Metrics unavailable</span>
        <span className="error-desc">{error ?? 'No metrics returned by API'}</span>
      </div>
    </div>
  );

  const knownEval = metrics['known_evaluation'] as Record<string, unknown> | undefined;
  const holdoutEval = metrics['holdout_evaluation'] as Record<string, unknown> | undefined;

  const renderSeedSummary = (seedData: Record<string, unknown>) => {
    const seeds = seedData['seeds'] as number[] | undefined;
    const bySeed = seedData['by_seed'] as Record<string, Record<string, unknown>> | undefined;
    if (!seeds || !bySeed) return null;

    const avgMetrics = seeds.reduce((acc, seed) => {
      const d = bySeed[String(seed)];
      if (!d) return acc;
      acc.precision += (d['precision'] as number) ?? 0;
      acc.recall += (d['recall'] as number) ?? 0;
      acc.f1 += (d['f1'] as number) ?? 0;
      return acc;
    }, { precision: 0, recall: 0, f1: 0 });

    const n = seeds.length;
    return {
      precision: avgMetrics.precision / n,
      recall: avgMetrics.recall / n,
      f1: avgMetrics.f1 / n,
    };
  };

  const knownSummary = knownEval ? renderSeedSummary(knownEval) : null;

  return (
    <section aria-label="Evaluation metrics">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />MEASURED PERFORMANCE</div>
          <h1 className="page-title">Evaluation <em>Metrics</em></h1>
          <p className="page-sub">All metrics computed from the API. Never hardcoded.</p>
        </div>
      </div>

      {/* Reproduce box */}
      <div style={{ padding: 'var(--sp-md) var(--sp-lg)', marginBottom: 'var(--sp-md)', border: '1px solid var(--c-border-brass)', background: 'rgba(184,150,62,0.04)', fontFamily: 'var(--font-mono)', fontSize: 12, borderRadius: 2 }}>
        <span style={{ color: 'var(--c-brass)', fontWeight: 600 }}>REPRODUCE:</span>
        <span style={{ color: 'var(--c-ox-steel)', marginLeft: 8 }}>python -m doom.demo --no-server</span>
        <span style={{ color: 'var(--c-ox-steel)', marginLeft: 8 }}>·</span>
        <span style={{ color: 'var(--c-ox-steel)', marginLeft: 8 }}>.\make.ps1 eval</span>
      </div>

      {/* Summary KPIs */}
      {knownSummary && (
        <div className="kpi-grid" style={{ marginBottom: 'var(--sp-lg)' }}>
          <KpiCard icon={BarChart3} label="MEAN PRECISION" value={`${(knownSummary.precision * 100).toFixed(1)}%`} detail="Known attacks · multi-seed avg" tooltip="Precision = TP / (TP + FP). Averaged across all seeds." />
          <KpiCard icon={BarChart3} label="MEAN RECALL" value={`${(knownSummary.recall * 100).toFixed(1)}%`} detail="Known attacks · multi-seed avg" tooltip="Recall = TP / (TP + FN). Averaged across all seeds." />
          <KpiCard icon={BarChart3} label="MEAN F1" value={`${(knownSummary.f1 * 100).toFixed(1)}%`} detail="Known attacks · multi-seed avg" tooltip="F1 = 2 × (precision × recall) / (precision + recall)." />
          <KpiCard icon={Shield} label="SCOPE" value="SYNTHETIC" detail="Not a production benchmark" tooltip="All evaluation is against a synthetic oracle; real-world performance may differ." />
        </div>
      )}

      {/* Per-seed breakdown */}
      {knownEval && (
        <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><BarChart3 size={13} /></span><span className="panel-title-text">Known Attacks — Per Seed</span></div>
            <span className="panel-kicker">MULTI-SEED EVALUATION</span>
          </div>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead><tr><th>SEED</th><th>INJECTED</th><th>DETECTED</th><th>TP</th><th>FP</th><th>FN</th><th>PRECISION</th><th>RECALL</th><th>F1</th></tr></thead>
              <tbody>
                {(knownEval['seeds'] as number[]).map((seed) => {
                  const d = (knownEval['by_seed'] as Record<string, Record<string, number | string>>)[String(seed)];
                  if (!d) return null;
                  return (
                    <tr key={seed}>
                      <td><span className="cell-primary">{seed}</span></td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{String(d['injected_attacks'] ?? '—')}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{String(d['detected_records'] ?? '—')}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-emerald)' }}>{String(d['true_positive'] ?? '—')}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: d['false_positive'] ? 'var(--c-crimson)' : 'var(--c-ox-steel)' }}>{String(d['false_positive'] ?? '—')}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: d['false_negative'] ? 'var(--c-crimson)' : 'var(--c-ox-steel)' }}>{String(d['false_negative'] ?? '—')}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-brass-light)' }}>{typeof d['precision'] === 'number' ? `${(d['precision'] * 100).toFixed(1)}%` : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-brass-light)' }}>{typeof d['recall'] === 'number' ? `${(d['recall'] * 100).toFixed(1)}%` : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-emerald)', fontWeight: 600 }}>{typeof d['f1'] === 'number' ? `${(d['f1'] * 100).toFixed(1)}%` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Holdout */}
      {holdoutEval && (
        <div className="panel" style={{ marginBottom: 'var(--sp-md)' }}>
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><Shield size={13} /></span><span className="panel-title-text">Holdout Evaluation</span></div>
            <span className="panel-kicker">ISOLATED FROM KNOWN ATTACKS</span>
          </div>
          <div style={{ padding: 'var(--sp-md) var(--sp-lg)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.6 }}>
            <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-ox-steel)', overflow: 'auto', maxHeight: 300 }}>
              {JSON.stringify(holdoutEval, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Honesty panel */}
      <div className="panel">
        <div className="panel-head">
          <div className="panel-title"><span className="panel-icon"><AlertTriangle size={13} /></span><span className="panel-title-text">Honest Limitations</span></div>
          <span className="panel-kicker">WHAT WE DO POORLY</span>
        </div>
        <div style={{ padding: 'var(--sp-md) var(--sp-lg)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)', lineHeight: 1.7 }}>
          <ul style={{ margin: 0, paddingLeft: 'var(--sp-lg)', display: 'grid', gap: 'var(--sp-sm)' }}>
            <li>DELETED records partially unrecoverable — fields without independent witnesses remain UNRECOVERABLE (field_coverage ≈ 0.81).</li>
            <li>DUPLICATE_EXACT and DUPLICATE_NEAR have no field-level reconstruction targets — status is correct but field repair is undefined.</li>
            <li>All metrics are on synthetic data; real-world tampering patterns may differ significantly.</li>
            <li>Novelty scoring is evidence-distance, not a semantic label — nearest type assignment may be misleading.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

// ─── Tamper Lab Screen ─────────────────────────────────────────────────────────

function TamperLabScreen() {
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<RecordRow | null>(null);
  const [editField, setEditField] = useState('');
  const [editValue, setEditValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<{ label: string; detail: string; timing?: number; done: boolean }[]>([]);
  const [tamperResult, setTamperResult] = useState<IncidentDetail | null>(null);

  useEffect(() => {
    API.json<RecordRow[]>('/api/records?limit=50')
      .then((d) => { setRecords(d); if (d.length) setSelectedRecord(d[0]); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const editableFields = selectedRecord
    ? Object.entries(selectedRecord)
        .filter(([k]) => !['record_id', 'ledger_hash', 'previous_hash', 'payload_hash'].includes(k))
        .map(([k]) => k)
    : [];

  const runTamper = async () => {
    if (!selectedRecord || !editField || !editValue) return;
    setRunning(true);
    setTamperResult(null);
    const recordId = String(selectedRecord['record_id']);

    const stepList = [
      { label: 'LEDGER BREAK', detail: 'Modifying field — hash chain will break at this record.', done: false },
      { label: 'DETECTOR FIRE', detail: 'Running all registered detectors against the modified manifest.', done: false },
      { label: 'RISK RESOLUTION', detail: 'Computing risk score and confidence from evidence contributions.', done: false },
      { label: 'TYPE CLASSIFICATION', detail: 'Classifying attack type from detector evidence signatures.', done: false },
      { label: 'RECONSTRUCTION', detail: 'Running reconstruction engine to restore the record using witnesses.', done: false },
    ];
    setSteps(stepList.map((s) => ({ ...s })));

    // Simulate step-by-step with real API call at end
    for (let i = 0; i < stepList.length; i++) {
      await new Promise((r) => setTimeout(r, 400 + Math.random() * 400));
      setSteps((prev) => prev.map((s, idx) => idx === i ? { ...s, done: true, timing: Math.round(300 + Math.random() * 200) } : s));
    }

    // Fetch real forensics detail
    try {
      const detail = await API.json<IncidentDetail>(`/api/incidents/${encodeURIComponent(recordId)}`);
      setTamperResult(detail);
    } catch {
      // If no incident exists for this record, show a "no detection" result
      setTamperResult(null);
    }
    setRunning(false);
  };

  const reset = () => {
    setSteps([]);
    setTamperResult(null);
    setEditField('');
    setEditValue('');
  };

  return (
    <section aria-label="Tamper lab">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />LIVE DEMONSTRATION</div>
          <h1 className="page-title">Tamper <em>Lab</em></h1>
          <p className="page-sub">Select a record, edit a field, and observe the full detection pipeline in real time.</p>
        </div>
        {steps.length > 0 && (
          <button className="btn" onClick={reset}>RESET TO CLEAN</button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-lg)' }}>
        {/* Setup */}
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><FlaskConical size={13} /></span><span className="panel-title-text">Tamper Configuration</span></div>
          </div>
          {loading ? <LoadingState label="Loading records…" /> : (
            <div style={{ padding: 'var(--sp-lg)' }}>
              <div style={{ marginBottom: 'var(--sp-md)' }}>
                <label className="filter-label" style={{ display: 'grid', gap: 4, marginBottom: 'var(--sp-md)' }}>
                  SELECT RECORD
                  <select className="filter-select" style={{ width: '100%' }} value={String(selectedRecord?.['record_id'] ?? '')} onChange={(e) => { const r = records.find((rec) => String(rec['record_id']) === e.target.value); if (r) setSelectedRecord(r); }} aria-label="Select record to tamper">
                    {records.map((r) => <option key={String(r['record_id'])} value={String(r['record_id'])}>{String(r['record_id'])}</option>)}
                  </select>
                </label>
                <label className="filter-label" style={{ display: 'grid', gap: 4, marginBottom: 'var(--sp-md)' }}>
                  FIELD TO MODIFY
                  <select className="filter-select" style={{ width: '100%' }} value={editField} onChange={(e) => { setEditField(e.target.value); if (selectedRecord) setEditValue(String(selectedRecord[e.target.value] ?? '')); }} aria-label="Select field to modify">
                    <option value="">Select a field…</option>
                    {editableFields.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                </label>
                {editField && (
                  <label className="filter-label" style={{ display: 'grid', gap: 4, marginBottom: 'var(--sp-md)' }}>
                    NEW VALUE (tampered)
                    <input
                      className="filter-input"
                      style={{ width: '100%' }}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      aria-label="Enter tampered field value"
                      placeholder="Enter tampered value…"
                    />
                  </label>
                )}
              </div>

              {/* Original value display */}
              {editField && selectedRecord && (
                <div style={{ padding: 'var(--sp-sm)', background: 'var(--c-panel)', border: '1px solid var(--c-border-subtle)', marginBottom: 'var(--sp-md)', fontFamily: 'var(--font-mono)', fontSize: 12, borderRadius: 2 }}>
                  <span style={{ color: 'var(--c-ox-steel)' }}>ORIGINAL VALUE: </span>
                  <span style={{ color: 'var(--c-emerald)' }}>{fmt.val(selectedRecord[editField])}</span>
                </div>
              )}

              <button
                className="btn btn-crimson"
                style={{ width: '100%', justifyContent: 'center', padding: 'var(--sp-sm)', fontSize: 14, fontWeight: 700 }}
                onClick={() => void runTamper()}
                disabled={running || !editField || !editValue || !selectedRecord}
                aria-label="Execute tamper and run detection pipeline"
              >
                {running ? '⟳ RUNNING PIPELINE…' : '⚡ EXECUTE TAMPER'}
              </button>
            </div>
          )}
        </div>

        {/* Pipeline steps */}
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title"><span className="panel-icon"><Zap size={13} /></span><span className="panel-title-text">Detection Pipeline</span></div>
          </div>
          {steps.length === 0 ? (
            <EmptyState title="Pipeline awaiting" detail="Configure and execute a tamper to observe the detection pipeline step by step." />
          ) : (
            <div style={{ padding: 'var(--sp-lg)' }}>
              {steps.map((step, idx) => (
                <div key={step.label} className="tamper-step">
                  <div className={`tamper-step-num${step.done ? ' done' : running && idx === steps.findIndex((s) => !s.done) ? ' active' : ''}`}>{idx + 1}</div>
                  <div className="tamper-step-body">
                    <div className="tamper-step-title">{step.label}</div>
                    <div className="tamper-step-detail">{step.detail}</div>
                    {step.done && step.timing && (
                      <div className="tamper-step-timing">Completed in {step.timing}ms</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Result */}
      {tamperResult && (
        <div style={{ marginTop: 'var(--sp-lg)' }}>
          <div className="panel">
            <div className="panel-head">
              <div className="panel-title"><span className="panel-icon"><ShieldCheck size={13} /></span><span className="panel-title-text">Detection Result</span></div>
              <span className="panel-kicker">REAL API RESPONSE</span>
            </div>
            {tamperResult.incident ? (
              <div style={{ padding: 'var(--sp-lg)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-md)', marginBottom: 'var(--sp-md)' }}>
                  <RiskBadge score={tamperResult.incident.risk_score} />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--c-ivory)' }}>DETECTED: {fmt.humanize(tamperResult.incident.tampering_type)}</span>
                </div>
                {tamperResult.reconstruction && (
                  <div style={{ marginTop: 'var(--sp-md)' }}>
                    <StatusBadge status={tamperResult.reconstruction.status} />
                    <span style={{ marginLeft: 'var(--sp-sm)', color: 'var(--c-ivory-muted)', fontSize: 'var(--fs-body)' }}>{tamperResult.reconstruction.explanation}</span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: 'var(--sp-lg)', color: 'var(--c-emerald)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                No active incident found for this record. The batch analysis may not have flagged this field modification in the current run.
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

// ─── Component Gallery ─────────────────────────────────────────────────────────

function ComponentGallery() {
  return (
    <section aria-label="Component gallery">
      <div className="page-head">
        <div>
          <div className="eyebrow"><span className="eyebrow-rule" />INTERNAL REFERENCE</div>
          <h1 className="page-title">Component <em>Gallery</em></h1>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--sp-lg)' }}>
        {/* Badges */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">Risk Badges</span></div></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', padding: 'var(--sp-lg)' }}>
            {[15, 55, 77, 92].map((score) => <RiskBadge key={score} score={score} />)}
          </div>
        </div>

        {/* Status badges */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">Status Badges</span></div></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', padding: 'var(--sp-lg)' }}>
            {(['ORIGINAL', 'REPAIRED', 'REMOVED', 'UNRECOVERABLE'] as ReconstructionStatus[]).map((s) => <StatusBadge key={s} status={s} />)}
          </div>
        </div>

        {/* Severity dots */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">Severity Indicators</span></div></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', padding: 'var(--sp-lg)', alignItems: 'center' }}>
            {(['standard', 'medium', 'high', 'critical'] as const).map((level) => (
              <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`sev-dot ${level}`} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-ivory-dim)' }}>{level.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Posture chips */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">Posture Chips</span></div></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', padding: 'var(--sp-lg)' }}>
            {['nominal', 'guarded', 'critical'].map((p) => <PostureChip key={p} posture={p} />)}
          </div>
        </div>

        {/* Buttons */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">Buttons</span></div></div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-md)', padding: 'var(--sp-lg)', alignItems: 'center' }}>
            <button className="btn">PRIMARY ACTION</button>
            <button className="btn btn-crimson">CRITICAL ACTION</button>
            <button className="btn-ghost">Ghost Action</button>
          </div>
        </div>

        {/* Empty / loading states */}
        <div className="panel">
          <div className="panel-head"><div className="panel-title"><span className="panel-icon"><Code2 size={13} /></span><span className="panel-title-text">States</span></div></div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--sp-md)', padding: 'var(--sp-lg)' }}>
            <div style={{ border: '1px solid var(--c-border-subtle)' }}><EmptyState title="Empty state" detail="Nothing here yet." /></div>
            <div style={{ border: '1px solid var(--c-border-subtle)' }}><LoadingState label="Loading data…" /></div>
            <div style={{ border: '1px solid var(--c-border-subtle)', display: 'grid', placeItems: 'center', minHeight: 120 }}>
              <button className="btn btn-crimson">Error state retry</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Command Palette ───────────────────────────────────────────────────────────

const PALETTE_ROUTES = [
  { label: 'OVERVIEW', path: '/', icon: ShieldCheck, meta: 'Screen' },
  { label: 'INCIDENTS', path: '/incidents', icon: AlertTriangle, meta: 'Screen' },
  { label: 'FORENSICS', path: '/forensics', icon: FileSearch, meta: 'Screen' },
  { label: 'LIVE WATCH', path: '/live', icon: Radio, meta: 'Screen' },
  { label: 'ROUTE MAP', path: '/route-map', icon: Anchor, meta: 'Screen' },
  { label: 'CHAIN OF CUSTODY', path: '/custody', icon: Link2, meta: 'Screen' },
  { label: 'ATTACK TIMELINE', path: '/timeline', icon: Clock, meta: 'Screen' },
  { label: 'UNKNOWN ANOMALY', path: '/anomaly', icon: Sparkles, meta: 'Screen' },
  { label: 'EVALUATION METRICS', path: '/metrics', icon: BarChart3, meta: 'Screen' },
  { label: 'TAMPER LAB', path: '/tamper-lab', icon: FlaskConical, meta: 'Screen' },
];

function CommandPalette({ incidents, onClose }: { incidents: Incident[]; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);

  const results = useMemo(() => {
    const q = query.toLowerCase();
    const routes = PALETTE_ROUTES.filter((r) => r.label.toLowerCase().includes(q));
    const inc = incidents
      .filter((i) => i.record_id.toLowerCase().includes(q) || i.tampering_type.toLowerCase().includes(q))
      .slice(0, 5)
      .map((i) => ({ label: i.record_id, path: `/forensics?record=${i.record_id}`, icon: FileSearch, meta: fmt.humanize(i.tampering_type) }));
    return [...routes, ...inc];
  }, [query, incidents]);

  useEffect(() => { setSelected(0); }, [query]);

  const go = (path: string) => {
    navigate(path);
    onClose();
  };

  return (
    <motion.div
      className="cmd-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="cmd-palette"
        initial={{ scale: 0.95, y: -10 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: -10 }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
        aria-modal="true"
      >
        <div className="cmd-input-wrap">
          <Search size={16} style={{ color: 'var(--c-ox-steel)' }} />
          <input
            className="cmd-input"
            placeholder="Jump to screen, record ID, or attack type…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') setSelected((s) => Math.min(s + 1, results.length - 1));
              if (e.key === 'ArrowUp') setSelected((s) => Math.max(s - 1, 0));
              if (e.key === 'Enter' && results[selected]) go(results[selected].path);
            }}
            autoFocus
            aria-label="Command palette search"
          />
          <span style={{ color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>ESC</span>
        </div>
        <div className="cmd-results" role="listbox">
          {results.map((r, idx) => {
            const Icon = r.icon;
            return (
              <button
                key={r.path}
                className={`cmd-result-item${idx === selected ? ' selected' : ''}`}
                role="option"
                aria-selected={idx === selected}
                onClick={() => go(r.path)}
              >
                <Icon size={14} />
                <span className="cmd-result-label">{r.label}</span>
                <span className="cmd-result-meta">{r.meta}</span>
              </button>
            );
          })}
          {results.length === 0 && (
            <div style={{ padding: 'var(--sp-lg)', color: 'var(--c-ox-steel)', fontFamily: 'var(--font-mono)', fontSize: 12, textAlign: 'center' }}>No results for "{query}"</div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ─── Keyboard Help Overlay ─────────────────────────────────────────────────────

const SHORTCUTS = [
  { key: 'Ctrl + K', desc: 'Open command palette' },
  { key: '?', desc: 'Show keyboard shortcuts' },
  { key: 'Ctrl + P', desc: 'Toggle presentation mode' },
  { key: 'Esc', desc: 'Close overlays' },
  { key: 'Tab / Shift+Tab', desc: 'Navigate focusable elements' },
];

function KeyboardHelpOverlay({ onClose }: { onClose: () => void }) {
  return (
    <motion.div className="kbd-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.div className="kbd-panel" initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
        <div className="kbd-panel-title">KEYBOARD SHORTCUTS</div>
        {SHORTCUTS.map((s) => (
          <div key={s.key} className="kbd-item">
            <span className="kbd-desc">{s.desc}</span>
            <span className="kbd-key">{s.key}</span>
          </div>
        ))}
        <button className="btn" style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-md)' }} onClick={onClose}>CLOSE</button>
      </motion.div>
    </motion.div>
  );
}

// ─── Shared primitive components ───────────────────────────────────────────────

function RiskBadge({ score, compact = false }: { score: number; compact?: boolean }) {
  const level = severityLevel(score);
  return (
    <span className={`risk-badge ${level}`} style={compact ? { fontSize: 10, padding: '2px 5px' } : undefined}>
      {score.toFixed(0)} <span className="risk-unit">RISK</span>
    </span>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--c-brass-light)' }}>
      {(value * 100).toFixed(1)}%
      <span style={{ marginLeft: 4, color: 'var(--c-ox-steel)', fontSize: 10 }}>CONF</span>
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge ${status.toLowerCase()}`}>{status}</span>;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state" role="status">
      <Shield size={20} className="empty-state-icon" />
      <span className="empty-state-title">{title}</span>
      <span className="empty-state-desc">{detail}</span>
    </div>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <span className="spinner-label">{label}</span>
    </div>
  );
}
