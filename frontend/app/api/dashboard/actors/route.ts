import { NextRequest, NextResponse } from "next/server";
import { backendRequest, safePayload, SELF_SERVE_PROXY_BOUNDARY, supabaseAccessToken } from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = await supabaseAccessToken();
  if (!auth.accessToken) {
    return NextResponse.json({ status: "locked", error: { code: auth.reason }, boundary: SELF_SERVE_PROXY_BOUNDARY }, { status: 401 });
  }
  const url = new URL(request.url);
  const response = await backendRequest(`/v1/auth/supabase/dashboard/actors?${url.searchParams.toString()}`, { method: "GET" }, auth.accessToken);
  const payload = await safePayload(response);
  return NextResponse.json({ ...payload, raw_api_key_exposed: false, proxy_boundary: SELF_SERVE_PROXY_BOUNDARY }, { status: response.status });
}
