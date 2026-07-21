const apiUrl = (process.env.PRMR_API_URL || process.env.PRMR_API_BASE_URL || "").replace(/\/$/, "");
const apiKey = process.env.PRMR_API_KEY || "";

function finish(result, detail = {}) {
  const payload = {
    result,
    api_domain_used: apiUrl || null,
    key_environment: apiKey ? "server_env_present" : "missing",
    boundary: "Hosted reference-client smoke uses public PRMR HTTP only. It does not use dashboard routes, database access, or PRMR backend imports.",
    ...detail
  };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(result === "PASS" ? 0 : result === "NEEDS_CREDENTIALS" ? 2 : 1);
}

if (!apiUrl || !apiKey) {
  finish("NEEDS_CREDENTIALS", {
    next_step: "Set PRMR_API_URL and PRMR_API_KEY for a real deployed PRMR scope, then rerun npm run hosted:smoke."
  });
}

const event = {
  event_type: "reference.project.created",
  signal: "Hosted reference client smoke created a synthetic project.",
  actor_reference: "actor_hosted_smoke_a",
  workspace_reference: "workspace_acme",
  entity_reference: "project_hosted_smoke_alpha",
  occurred_at: new Date().toISOString(),
  idempotency_key: `hosted-reference-smoke-${Date.now()}`,
  application_reference: "prmr_reference_client",
  metadata: { source_app: "prmr_reference_client", synthetic: true }
};

const ingest = await fetch(`${apiUrl}/v1/events/ingest`, {
  method: "POST",
  headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
  body: JSON.stringify({ events: [event] })
});
const ingestBody = await ingest.json().catch(() => ({}));
if (!ingest.ok) finish("NEEDS_WORK", { failed_step: "events_ingest", status: ingest.status, body: ingestBody });

const packet = await fetch(`${apiUrl}/v1/continuity/packet`, {
  method: "POST",
  headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
  body: JSON.stringify({
    application_reference: "prmr_reference_client",
    actor_reference: event.actor_reference,
    workspace_reference: event.workspace_reference,
    entity_reference: event.entity_reference
  })
});
const packetBody = await packet.json().catch(() => ({}));
if (!packet.ok) finish("NEEDS_WORK", { failed_step: "continuity_packet", status: packet.status, body: packetBody });

finish("PASS", {
  events_sent: ingestBody.accepted_event_count,
  packet_id: packetBody.packet?.packet_id || null,
  event_count: packetBody.packet?.event_count || null,
  raw_key_exposed: false
});
