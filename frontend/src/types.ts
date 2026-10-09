export type ReconstructionStatus =
  | "ORIGINAL"
  | "REPAIRED"
  | "REMOVED"
  | "UNRECOVERABLE";

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type Evidence = {
  detector_id: string;
  evidence_code: string;
  record_ids: string[];
  field: string;
  expected: unknown;
  observed: unknown;
  score_contribution: number;
  severity: Severity | string;
  explanation: string;
};

export type UnknownAnalysis = {
  invariant_violations: Array<{
    detector_id: string;
    evidence_code: string;
    field: string;
    explanation: string;
  }>;
  nearest_known_attack_type: string;
  nearest_similarity: number;
  novelty_score: number;
  nearest_match_meaningful: boolean;
};

export type Incident = {
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

export type Overview = {
  record_count: number;
  incident_count: number;
  critical_count: number;
  integrity_score: number;
  reconstruction_counts: Record<ReconstructionStatus, number>;
  metrics: Record<string, unknown>;
  stream_status: string;
};

export type ReconstructionDecision = {
  record_id: string;
  status: ReconstructionStatus;
  explanation: string;
  changes: Array<{ field: string; from: unknown; to: unknown }>;
  tampering_type: string | null;
  method?: string;
  evidence_relied_on?: string[];
  unresolved_fields?: string[];
  confidence?: number;
  provisional?: boolean;
};

export type RecordRow = Record<string, string | number | boolean | null | undefined>;

export type TimelineEvent = { event: string; time: string | null };

export type IncidentDetail = {
  incident: Incident | null;
  record: RecordRow | null;
  reconstruction: ReconstructionDecision | null;
  timeline: TimelineEvent[];
};

export type LiveEvent = {
  event_id: string;
  timestamp: string;
  sequence?: number;
  record_id: string;
  status: "ANOMALY" | "CLEARED";
  incident: Incident | null;
  record: RecordRow;
  live_reconstruction?: ReconstructionDecision;
};

export type RoutePort = {
  code: string;
  name: string;
  latitude: number;
  longitude: number;
};

export type RoutePayload = {
  ports: RoutePort[];
};

export type MetricsPayload = {
  injected_attacks?: number;
  detected_records?: number;
  true_positive?: number;
  false_positive?: number;
  false_negative?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  type_accuracy_on_detected?: number;
  reconstruction_accuracy?: number;
  streaming?: Record<string, number | string>;
  [key: string]: unknown;
};
