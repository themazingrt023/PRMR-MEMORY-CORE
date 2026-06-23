export type EndpointDoc = {
  method: "GET" | "POST";
  path: string;
  purpose: string;
  request: string;
  response: string;
  boundary: string;
};

export const integrationFlow = [
  "Create a client record",
  "Issue an operator-approved API key",
  "Create a vault and namespace",
  "Send scoped messy events",
  "Generate a continuity packet",
  "Reconstruct current state",
  "Request a public-safe explanation or report",
  "View usage, blocked requests, reports, and memory health in the dashboard"
];

export const useCases = [
  "AI assistant and agent memory continuity",
  "Customer support/user-history continuity",
  "SaaS user-history continuity",
  "Education progress continuity",
  "Legal/research case continuity",
  "Fraud/risk sandbox evaluation",
  "Healthcare/admin case history continuity",
  "Game studio lore/canon continuity",
  "Robotics/agent state history",
  "Enterprise decision logs",
  "Project management memory"
];

export const endpoints: EndpointDoc[] = [
  {
    method: "POST",
    path: "/v1/events/ingest",
    purpose: "Accept scoped events and store them under a client, vault, and namespace.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "events": [
    {
      "event_id": "evt_demo_001",
      "entity_id": "agent_demo_001",
      "entity_type": "agent_memory",
      "timestamp": "2026-06-20T15:01:00Z",
      "event_type": "state_change",
      "state_before": "new workspace session",
      "state_after": "project preference recorded",
      "signal_type": "preference_origin",
      "status": "active",
      "trust_level": "trusted"
    }
  ],
  "metadata": {
    "dataset_type": "synthetic"
  }
}`,
    response: `{
  "ok": true,
  "accepted_event_count": 1,
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default"
}`,
    boundary: "Use synthetic or explicitly approved datasets only."
  },
  {
    method: "POST",
    path: "/v1/continuity/packet",
    purpose: "Turn scoped event history into a compact continuity packet.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "entity_id": "agent_demo_001"
}`,
    response: `{
  "ok": true,
  "packet": {
    "packet_id": "pkt_demo_001",
    "entity_id": "agent_demo_001",
    "current_state": "agent can continue with current project preference",
    "active_signals": ["continuity_ready"],
    "stale_signals": ["outdated_setup_note"],
    "continuity_summary": "Current state preserves active and stale signals for review."
  }
}`,
    boundary: "A packet is review support, not an automated final decision."
  },
  {
    method: "POST",
    path: "/v1/memory/reconstruct",
    purpose: "Reconstruct useful current state from a continuity packet.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001"
}`,
    response: `{
  "ok": true,
  "reconstruction_match": true,
  "reconstructable_state": {
    "current_state": "agent can continue with current project preference",
    "active_signals": ["continuity_ready"],
    "stale_signals": ["outdated_setup_note"]
  }
}`,
    boundary: "Reconstruction verifies continuity state; it does not certify real-world truth."
  },
  {
    method: "POST",
    path: "/v1/explain",
    purpose: "Create a public-safe explanation for review.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001",
  "audience": "customer_safe"
}`,
    response: `{
  "ok": true,
  "explanation": {
    "summary": "We noticed activity that may need review before continuing.",
    "customer_next_step": "Please confirm whether you recognize the change.",
    "review_boundary": "This is a review step, not a final conclusion."
  }
}`,
    boundary: "Public-safe explanations avoid restricted diagnostics and certainty-heavy language."
  },
  {
    method: "POST",
    path: "/v1/actions/least-harm",
    purpose: "Return a proportionate next-step boundary.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "packet_id": "pkt_demo_001"
}`,
    response: `{
  "ok": true,
  "recommended_action": "request_evidence",
  "allowed_actions": [
    "do_nothing",
    "warn",
    "request_evidence",
    "human_review",
    "keep_dormant"
  ],
  "not_final_decision": true
}`,
    boundary: "Least-harm output is review-oriented and does not perform final punitive action."
  },
  {
    method: "GET",
    path: "/v1/reports/{report_id}",
    purpose: "Fetch a public-safe report preview when the caller owns the report scope.",
    request: `GET /v1/reports/rep_demo_001
Authorization: Bearer <redacted local alpha token>
X-PRMR-Client-ID: client_alpha
X-PRMR-Vault-ID: alpha_vault
X-PRMR-Namespace: default`,
    response: `{
  "ok": true,
  "report": {
    "report_id": "rep_demo_001",
    "public_safe": true,
    "summary": "Continuity packet generated for controlled alpha review."
  }
}`,
    boundary: "Public report previews must not expose restricted diagnostics."
  },
  {
    method: "GET",
    path: "/v1/usage",
    purpose: "Return scoped usage counts for the authenticated client and vault.",
    request: `GET /v1/usage
Authorization: Bearer <redacted local alpha token>
X-PRMR-Client-ID: client_alpha
X-PRMR-Vault-ID: alpha_vault
X-PRMR-Namespace: default`,
    response: `{
  "ok": true,
  "usage": {
    "events_ingested": 4,
    "packets_generated": 1,
    "reports_created": 1,
    "reports_read": 1
  }
}`,
    boundary: "Usage output is scoped to the caller."
  },
  {
    method: "POST",
    path: "/v1/keys/rotate",
    purpose: "Rotate an active local alpha credential.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "reason": "scheduled_rotation"
}`,
    response: `{
  "ok": true,
  "rotated": true,
  "old_key_status": "revoked",
  "new_key_delivery": "show_once_or_out_of_band"
}`,
    boundary: "The browser should never receive raw credential material."
  },
  {
    method: "POST",
    path: "/v1/keys/revoke",
    purpose: "Revoke an active local alpha credential.",
    request: `{
  "client_id": "client_alpha",
  "vault_id": "alpha_vault",
  "namespace": "default",
  "reason": "manual_revoke"
}`,
    response: `{
  "ok": true,
  "revoked": true
}`,
    boundary: "Revoked credentials must not authorize future requests."
  }
];

export const versionTimeline = [
  "V0.50 Whole Core Truth Gauntlet: PASS",
  "V0.52.0 Alpha API Contract: PASS",
  "V0.52.1 Alpha API Sandbox: PASS",
  "V0.52.2 Sandbox Integrity Audit: PASS",
  "V0.53.1 Demo Replay Pack: PASS",
  "V0.55 Frontend-to-PRMR Local Demo Backend Connection: PASS",
  "V0.72 Client Dashboard MVP: PASS",
  "V0.72.1 Product Value Clarity + Site Utility Rewrite: current docs milestone"
];
