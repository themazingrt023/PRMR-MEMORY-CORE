export type DemoScenarioOption = {
  scenario_id: string;
  scenario_name: string;
  description: string;
};

export type DemoEventSummary = {
  event_id: string;
  from: string;
  to: string;
  status: string;
  signal: string;
};

export type ConnectedContinuityPacket = {
  current_state: string;
  active_signals: string[];
  stale_signals: string[];
  evidence: string[];
  summary: string;
};

export type ConnectedReconstruction = {
  state: string;
  confidence_label: "synthetic_demo" | string;
  active_signals?: string[];
  stale_signals?: string[];
};

export type ConnectedExplanation = {
  public_safe_summary: string;
  review_boundary: string;
  next_step?: string;
};

export type ConnectedLeastHarmAction = {
  label: string;
  meaning: string;
  allowed_actions?: string[];
  not_final_decision: boolean;
};

export type ConnectedReportPreview = {
  report_id: string;
  public_summary: string;
  owner_access: "allowed" | "denied" | string;
  public_safe: boolean;
};

export type ConnectedDenialPath = {
  wrong_key_denied: boolean;
  cross_client_denied: boolean;
  wrong_key_result?: string;
  cross_client_result?: string;
};

export type ConnectedDemoResponse = {
  status: "ok";
  version: string;
  scenario_id: string;
  scenario_name: string;
  synthetic_only: true;
  boundary: string;
  events_summary: DemoEventSummary[];
  continuity_packet: ConnectedContinuityPacket;
  reconstruction: ConnectedReconstruction;
  explanation: ConnectedExplanation;
  least_harm_action: ConnectedLeastHarmAction;
  report_preview: ConnectedReportPreview;
  denial_path: ConnectedDenialPath;
};
