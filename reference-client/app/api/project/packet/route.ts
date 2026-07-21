import { NextRequest, NextResponse } from "next/server";
import { requestPrmrPacket } from "@/lib/prmr";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const scope = {
    actor_reference: String(body.actor_reference || "actor_a"),
    workspace_reference: String(body.workspace_reference || "workspace_acme"),
    entity_reference: String(body.entity_reference || "project_alpha")
  };
  const result = await requestPrmrPacket(scope);
  return NextResponse.json(
    {
      scope,
      prmr_status: result.status,
      packet: result.body?.packet || null,
      report_id: result.body?.report_id || null,
      raw_api_key_exposed: false,
      internal_route_used: false
    },
    { status: result.ok ? 200 : result.status }
  );
}
