export type ContinuityPacket = {
  currentState: string;
  activeSignals: string[];
  staleSignals: string[];
  evidenceSummary: string[];
  reviewBoundary: string;
};

export type PublicExplanation = {
  summary: string;
  nextStep: string;
  boundary: string;
};

export type LeastHarmAction = {
  label: string;
  allowedActions: string[];
  notFinalDecision: boolean;
};

export type ReportPreview = {
  reportId: string;
  publicSafe: boolean;
  ownerAccess: string;
  denialPath: string;
};

export type DemoScenario = {
  id: string;
  name: string;
  description: string;
  rawEvents: string[];
  continuityPacket: ContinuityPacket;
  explanation: PublicExplanation;
  leastHarmAction: LeastHarmAction;
  reportPreview: ReportPreview;
};

export const demoScenarios: DemoScenario[] = [
  {
    id: "ai_agent_memory",
    name: "AI agent memory continuity",
    description: "Synthetic agent context showing a remembered project preference across turns.",
    rawEvents: [
      "new workspace session -> project preference recorded",
      "project preference recorded -> preference carried into refreshed context",
      "preference carried into refreshed context -> agent can continue with current project preference",
      "old setup note superseded -> outdated setup note archived"
    ],
    continuityPacket: {
      currentState: "agent can continue with current project preference",
      activeSignals: ["continuity_ready", "preference_recalled"],
      staleSignals: ["outdated_setup_note"],
      evidenceSummary: [
        "Synthetic project preference is present.",
        "Synthetic refreshed context preserved the current preference."
      ],
      reviewBoundary: "Review support only; this is not an autonomous decision surface."
    },
    explanation: {
      summary: "We noticed activity that may need review before continuing.",
      nextStep: "Please confirm whether you recognize the change.",
      boundary: "This is a review step, not a final conclusion."
    },
    leastHarmAction: {
      label: "request_evidence",
      allowedActions: ["do_nothing", "warn", "request_evidence", "human_review", "keep_dormant"],
      notFinalDecision: true
    },
    reportPreview: {
      reportId: "public-demo-agent-memory",
      publicSafe: true,
      ownerAccess: "owner access allowed",
      denialPath: "wrong key and cross-client attempts are denied in the sandbox"
    }
  },
  {
    id: "support_history",
    name: "Customer support/user-history continuity",
    description: "Synthetic support history showing a repeated issue without exposing restricted traces.",
    rawEvents: [
      "no active support issue -> support history available",
      "support history available -> delivery issue repeated after prior contact",
      "delivery issue repeated after prior contact -> support follow-up awaiting confirmation",
      "old shipping estimate active -> old shipping estimate superseded"
    ],
    continuityPacket: {
      currentState: "support follow-up awaiting confirmation",
      activeSignals: ["repeat_contact", "response_needed"],
      staleSignals: ["old_shipping_estimate"],
      evidenceSummary: [
        "Synthetic prior support context is present.",
        "Synthetic follow-up state needs confirmation."
      ],
      reviewBoundary: "Review support only; response content still needs human ownership."
    },
    explanation: {
      summary: "We noticed activity that may need review before continuing.",
      nextStep: "Please confirm whether you recognize the change.",
      boundary: "This is a review step, not a final conclusion."
    },
    leastHarmAction: {
      label: "request_evidence",
      allowedActions: ["do_nothing", "warn", "request_evidence", "human_review", "release_cleared_funds"],
      notFinalDecision: true
    },
    reportPreview: {
      reportId: "public-demo-support-history",
      publicSafe: true,
      ownerAccess: "owner access allowed",
      denialPath: "wrong key and cross-client attempts are denied in the sandbox"
    }
  },
  {
    id: "risk_continuity",
    name: "Fraud/risk continuity sandbox",
    description: "Synthetic risk-review continuity without accusation language or final decisions.",
    rawEvents: [
      "ordinary account activity -> ordinary account activity",
      "ordinary account activity -> new recipient and invoice note introduced",
      "new recipient and invoice note introduced -> recipient change awaiting confirmation",
      "old device note active -> old device note superseded"
    ],
    continuityPacket: {
      currentState: "recipient change awaiting confirmation",
      activeSignals: ["confirmation_needed", "recipient_change"],
      staleSignals: ["old_device_note"],
      evidenceSummary: [
        "Synthetic recipient change is active.",
        "Synthetic old device note is stale."
      ],
      reviewBoundary: "Review support only; no final punitive decision is made by this shell."
    },
    explanation: {
      summary: "We noticed activity that may need review before continuing.",
      nextStep: "Please confirm whether you recognize the change.",
      boundary: "This is a review step, not a final conclusion."
    },
    leastHarmAction: {
      label: "request_evidence",
      allowedActions: ["do_nothing", "warn", "request_evidence", "human_review", "keep_dormant"],
      notFinalDecision: true
    },
    reportPreview: {
      reportId: "public-demo-risk-continuity",
      publicSafe: true,
      ownerAccess: "owner access allowed",
      denialPath: "wrong key and cross-client attempts are denied in the sandbox"
    }
  }
];
