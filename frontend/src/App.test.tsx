import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";

const firstIncident = {
  record_id: "MF-0000101",
  tampering_type: "MODIFIED_VALUE",
  risk_score: 92,
  confidence: 0.91,
  detection_probability: 0.94,
  evidence: [{
    detector_id: "integrity_hash",
    evidence_code: "EXPECTED_PAYLOAD_HASH_MISMATCH",
    record_ids: ["MF-0000101"],
    field: "payload_hash",
    expected: "anchor-digest",
    observed: "observed-digest",
    score_contribution: 0.9,
    severity: "HIGH",
    explanation: "The observed payload differs from the independent ledger.",
  }],
  detectors: ["integrity_hash"],
  related_records: ["MF-0000102"],
  counterfactual: "Restore the ledger-attested field value.",
};

const secondIncident = {
  ...firstIncident,
  record_id: "MF-0000102",
  tampering_type: "TELEPORTATION",
  risk_score: 72,
  confidence: 0.98,
  detection_probability: 0.71,
  evidence: [],
  detectors: ["route_validation"],
  related_records: [],
  counterfactual: undefined,
};

const incidents = [firstIncident, secondIncident];
const overview = {
  record_count: 40,
  incident_count: incidents.length,
  critical_count: 1,
  integrity_score: 95,
  reconstruction_counts: {
    ORIGINAL: 35,
    REPAIRED: 3,
    REMOVED: 1,
    UNRECOVERABLE: 1,
  },
  metrics: {},
  stream_status: "LIVE",
};

const details = {
  incident: firstIncident,
  record: {
    record_id: firstIncident.record_id,
    shipment_id: "SHP-0000101",
    owner: "Aster Maritime",
    container_id: "CONT-0000101",
    planned_route: "SGSIN|AEJEA|NLRTM",
    declared_value_usd: 54000,
    event_ts: "2026-03-01T12:00:00Z",
  },
  reconstruction: {
    record_id: firstIncident.record_id,
    status: "REPAIRED",
    explanation: "The value is supported by independent customs evidence.",
    changes: [{ field: "declared_value_usd", from: "62000", to: "54000" }],
    tampering_type: "MODIFIED_VALUE",
    method: "WITNESS_RESTORATION",
    evidence_relied_on: ["customs_entry", "control_ledger"],
    unresolved_fields: [],
    confidence: 0.94,
  },
  timeline: [
    { event: "RECORD OBSERVED", time: "2026-03-01T12:00:00Z" },
    { event: "ANOMALY DETECTED", time: null },
  ],
};

function jsonResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as Response;
}

class TestWebSocket {
  static instances: TestWebSocket[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(readonly url: string) {
    TestWebSocket.instances.push(this);
    queueMicrotask(() => this.onopen?.(new Event("open")));
  }

  close() {
    this.onclose?.(new CloseEvent("close"));
  }
}

function installApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/overview") return jsonResponse(overview);
    if (path.startsWith("/api/incidents?")) return jsonResponse(incidents);
    if (path === "/api/stream/events") return jsonResponse([]);
    if (path === `/api/incidents/${firstIncident.record_id}`) return jsonResponse(details);
    return jsonResponse([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", TestWebSocket);
}

beforeEach(() => {
  TestWebSocket.instances = [];
  installApi();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("D.O.O.M. operations console", () => {
  it("renders current overview values from the API", async () => {
    render(<App />);
    expect(await screen.findAllByText("95.0%")).toHaveLength(2);
    expect(screen.getByText("40", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("CRITICAL EXPOSURE")).toBeInTheDocument();
    expect(screen.getByText("Incident summary")).toBeInTheDocument();
  });

  it("filters and sorts incidents by API-provided fields", async () => {
    render(<App />);
    await screen.findAllByText("95.0%");
    fireEvent.click(screen.getByRole("button", { name: /Incidents/ }));

    const search = screen.getByRole("textbox", { name: "Search incidents" });
    fireEvent.change(search, { target: { value: "teleportation" } });
    const table = screen.getByRole("table");
    expect(await within(table).findByText("TELEPORTATION")).toBeInTheDocument();
    expect(within(table).queryByText("MODIFIED VALUE")).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "" } });
    const sort = screen.getByLabelText("Sort incidents");
    fireEvent.change(sort, { target: { value: "confidence" } });
    expect(table.querySelector("tbody tr")).toHaveTextContent("MF-0000102");

    fireEvent.change(screen.getByLabelText("Filter by severity"), { target: { value: "CRITICAL" } });
    expect(within(table).getByText("MF-0000101")).toBeInTheDocument();
    expect(within(table).queryByText("MF-0000102")).not.toBeInTheDocument();
  });

  it("shows evidence, expected and observed values, and reconstruction diff in one view", async () => {
    render(<App />);
    await screen.findAllByText("95.0%");
    fireEvent.click(screen.getByRole("button", { name: /Record forensics/ }));

    expect(await screen.findByText("EXPECTED PAYLOAD HASH MISMATCH")).toBeInTheDocument();
    expect(screen.getByText("anchor-digest")).toBeInTheDocument();
    expect(screen.getByText("observed-digest")).toBeInTheDocument();
    expect(screen.getByText("WITNESS RESTORATION")).toBeInTheDocument();
    expect(screen.getByText("Restore the ledger-attested field value.")).toBeInTheDocument();
    expect(screen.getByText("Case timeline")).toBeInTheDocument();
  });

  it("surfaces streaming-only unknown anomalies from the live WebSocket", async () => {
    render(<App />);
    await screen.findAllByText("95.0%");
    fireEvent.click(screen.getByRole("button", { name: /Live watch/ }));
    await waitFor(() => expect(TestWebSocket.instances.length).toBeGreaterThan(0));

    const liveIncident = {
      ...firstIncident,
      record_id: "LIVE-UNKNOWN-01",
      tampering_type: "UNKNOWN ANOMALY",
      unknown_analysis: {
        invariant_violations: [{
          detector_id: "stream_sequence",
          evidence_code: "STREAM_RECORD_ID_MUTATION",
          field: "container_id",
          explanation: "A previously observed record ID reappeared with changed identity.",
        }],
        nearest_known_attack_type: "DELETED",
        nearest_similarity: 0,
        novelty_score: 1,
        nearest_match_meaningful: false,
      },
    };
    const event = {
      event_id: "event-1",
      timestamp: "2026-03-01T12:01:00Z",
      record_id: liveIncident.record_id,
      status: "ANOMALY",
      incident: liveIncident,
      record: {},
      live_reconstruction: {
        record_id: liveIncident.record_id,
        status: "REPAIRED",
        explanation: "The changed field is restored to a previously observed snapshot.",
        changes: [{ field: "container_id", from: "SWAPPED-CONT-101", to: "CONT-101" }],
        tampering_type: "UNKNOWN ANOMALY",
        method: "first_observed_stream_snapshot",
        provisional: true,
      },
    };
    const socket = TestWebSocket.instances[0];
    if (!socket?.onmessage) throw new Error("WebSocket message handler was not attached.");
    socket.onmessage(new MessageEvent("message", { data: JSON.stringify(event) }));

    expect(await screen.findByText("UNKNOWN SIGNAL DETECTED")).toBeInTheDocument();
    expect(screen.getAllByText("LIVE-UNKNOWN-01")).toHaveLength(2);
    expect(screen.queryByText("NOVELTY MONITOR ARMED")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "INSPECT" }));
    expect(await screen.findByText("UNKNOWN ANOMALY ANALYSIS")).toBeInTheDocument();
    expect(screen.getByText("STREAM RECORD ID MUTATION")).toBeInTheDocument();
    expect(screen.getByText("PROVISIONAL — FIRST OBSERVED STREAM SNAPSHOT")).toBeInTheDocument();
    expect(screen.getByText("SWAPPED-CONT-101")).toBeInTheDocument();
    expect(screen.getByText("CONT-101")).toBeInTheDocument();
  });
});
