import { NextRequest, NextResponse } from "next/server";
import {
  backendRequest,
  safePayload,
  SELF_SERVE_PROXY_BOUNDARY,
  supabaseAccessToken
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, method: "GET" | "POST" | "PATCH" | "DELETE") {
  const auth = await supabaseAccessToken();
  if (!auth.accessToken) {
    return NextResponse.json(
      {
        status: "locked",
        error: { code: auth.reason },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: 401 }
    );
  }
  const body = method === "GET" ? undefined : await request.text();
  const response = await backendRequest(
    "/v1/auth/supabase/keys",
    { method, body: body || undefined },
    auth.accessToken
  );
  const payload = await safePayload(response);
  return NextResponse.json(
    {
      ...payload,
      supabase_access_token_exposed: false,
      proxy_boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: response.status }
  );
}

export async function GET(request: NextRequest) {
  return proxy(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxy(request, "POST");
}

export async function PATCH(request: NextRequest) {
  return proxy(request, "PATCH");
}

export async function DELETE(request: NextRequest) {
  return proxy(request, "DELETE");
}
