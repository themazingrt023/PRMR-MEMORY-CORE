import { NextResponse } from "next/server";
import {
  backendRequest,
  safePayload,
  SELF_SERVE_PROXY_BOUNDARY,
  sessionToken
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const token = await sessionToken();
  if (!token) {
    return NextResponse.json(
      {
        status: "locked",
        error: { code: "self_serve_session_required" },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: 401 }
    );
  }
  const response = await backendRequest("/v1/self-serve/dashboard", { method: "GET" }, token);
  const payload = await safePayload(response);
  return NextResponse.json(
    {
      ...payload,
      session_token_exposed: false,
      raw_api_key_exposed: false,
      proxy_boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: response.status }
  );
}
