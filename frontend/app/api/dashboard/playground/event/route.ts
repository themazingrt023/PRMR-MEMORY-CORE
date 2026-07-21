import { NextRequest, NextResponse } from "next/server";
import { backendRequest, safePayload, SELF_SERVE_PROXY_BOUNDARY, supabaseAccessToken } from "@/lib/selfServeProxy";

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
  const response = await backendRequest(
    "/v1/auth/supabase/dashboard/playground/event",
    { method: "POST", body: JSON.stringify(body) },
    auth.accessToken
  );
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
