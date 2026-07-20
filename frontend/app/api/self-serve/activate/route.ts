import { NextRequest, NextResponse } from "next/server";
import {
  backendRequest,
  safePayload,
  SELF_SERVE_PROXY_BOUNDARY,
  supabaseAccessToken
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const auth = await supabaseAccessToken();
  if (!auth.accessToken || !auth.user) {
    return NextResponse.json(
      {
        status: "locked",
        error: {
          code: auth.reason,
          message: "A confirmed Supabase Auth session is required."
        },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: auth.reason === "supabase_email_confirmation_required" ? 403 : 401 }
    );
  }
  const body = (await request.json().catch(() => ({}))) as { plan?: string };
  const plan = String(body.plan || "free");
  if (!["free", "builder", "controlled_pilot"].includes(plan)) {
    return NextResponse.json(
      {
        status: "error",
        error: { code: "invalid_plan", message: "Choose a documented PRMR plan." },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: 400 }
    );
  }
  const response = await backendRequest(
    "/v1/auth/supabase/activate",
    {
      method: "POST",
      body: JSON.stringify({ plan_id: plan })
    },
    auth.accessToken
  );
  const payload = await safePayload(response);
  return NextResponse.json(
    {
      ...payload,
      supabase_access_token_exposed: false,
      raw_api_key_exposed_once: Boolean(payload.raw_api_key),
      boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: response.status }
  );
}
