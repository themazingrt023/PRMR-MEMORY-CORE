import { NextRequest, NextResponse } from "next/server";
import {
  backendRequest,
  safePayload,
  SELF_SERVE_PROXY_BOUNDARY,
  sessionToken
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, method: "GET" | "POST" | "PATCH" | "DELETE") {
  const token = await sessionToken();
  if (!token) {
    return NextResponse.json(
      { status: "locked", error: { code: "self_serve_session_required" }, boundary: SELF_SERVE_PROXY_BOUNDARY },
      { status: 401 }
    );
  }
  const body = method === "GET" ? undefined : await request.text();
  const response = await backendRequest(
    "/v1/self-serve/keys",
    { method, body: body || undefined },
    token
  );
  const payload = await safePayload(response);
  return NextResponse.json(
    {
      ...payload,
      session_token_exposed: false,
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
