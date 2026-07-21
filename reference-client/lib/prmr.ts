export type ProjectEvent = {
  event_type: string;
  signal: string;
  actor_reference: string;
  workspace_reference: string;
  entity_reference: string;
  occurred_at: string;
  idempotency_key: string;
  metadata: {
    source_app: "prmr_reference_client";
    action: string;
    synthetic?: boolean;
  };
};

export function prmrBaseUrl() {
  return (process.env.PRMR_API_URL || process.env.PRMR_API_BASE_URL || "").replace(/\/$/, "");
}

export function prmrApiKey() {
  return process.env.PRMR_API_KEY || "";
}

export async function sendPrmrEvent(event: ProjectEvent) {
  const baseUrl = prmrBaseUrl();
  const apiKey = prmrApiKey();
  if (!baseUrl || !apiKey) {
    return {
      ok: false,
      status: 500,
      body: { error: { code: "missing_prmr_server_env" } }
    };
  }
  const response = await fetch(`${baseUrl}/v1/events/ingest`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ events: [event] }),
    cache: "no-store"
  });
  const body = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, body };
}

export async function requestPrmrPacket(scope: {
  actor_reference: string;
  workspace_reference: string;
  entity_reference: string;
}) {
  const baseUrl = prmrBaseUrl();
  const apiKey = prmrApiKey();
  if (!baseUrl || !apiKey) {
    return {
      ok: false,
      status: 500,
      body: { error: { code: "missing_prmr_server_env" } }
    };
  }
  const response = await fetch(`${baseUrl}/v1/continuity/packet`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      application_reference: "prmr_reference_client",
      ...scope
    }),
    cache: "no-store"
  });
  const body = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, body };
}
