import { NextRequest, NextResponse } from "next/server";
import {
  backendBaseUrl,
  safePayload,
  SELF_SERVE_PROXY_BOUNDARY,
  supabaseAccessToken
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const auth = await supabaseAccessToken();
  if (!auth.accessToken) {
    return NextResponse.json(
      { status: "locked", error: { code: auth.reason }, boundary: SELF_SERVE_PROXY_BOUNDARY },
      { status: 401 }
    );
  }
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const apiKey = String(body.api_key || "").trim();
  if (!apiKey) {
    return NextResponse.json(
      { status: "error", error: { code: "missing_api_key" }, boundary: SELF_SERVE_PROXY_BOUNDARY },
      { status: 400 }
    );
  }
  const event = {
    event_type: String(body.event_type || "prmr.playground.first_event"),
    signal: String(body.signal || "A first sandbox event was sent to PRMR."),
    occurred_at: new Date().toISOString(),
    application_reference: String(body.application_reference || "app_main"),
    actor_reference: String(body.actor_reference || "user_123"),
    workspace_reference: String(body.workspace_reference || "workspace_demo"),
    entity_reference: String(body.entity_reference || "entity_demo"),
    metadata: {
      source_app: "prmr_dashboard_playground",
      synthetic: true
    },
    idempotency_key: String(body.idempotency_key || `playground-${Date.now()}`)
  };
  const response = await fetch(`${backendBaseUrl()}/v1/events/ingest`, {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ events: [event] }),
    cache: "no-store"
  });
  const payload = await safePayload(response);
  return NextResponse.json(
    {
      ...payload,
      playground_used_public_api_contract: true,
      raw_api_key_exposed: false,
      supabase_access_token_exposed: false,
      boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: response.status }
  );
}
