import { NextRequest, NextResponse } from "next/server";
import {
  backendRequest,
  SELF_SERVE_PROXY_BOUNDARY,
  SELF_SERVE_SESSION_COOKIE
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as { email?: string; password?: string };
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");
  if (!email.includes("@") || password.length < 10) {
    return NextResponse.json(
      { status: "error", error: { code: "invalid_login_fields" }, boundary: SELF_SERVE_PROXY_BOUNDARY },
      { status: 400 }
    );
  }
  const backend = await backendRequest("/v1/self-serve/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  const payload = (await backend.json().catch(() => ({}))) as {
    session_token?: string;
    account?: Record<string, unknown>;
    error?: Record<string, unknown>;
  };
  if (!backend.ok || !payload.session_token) {
    return NextResponse.json(
      {
        status: "error",
        error: payload.error || { code: "hosted_login_failed" },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: backend.status || 502 }
    );
  }
  const response = NextResponse.json({
    status: "ok",
    account: payload.account,
    session_token_exposed: false,
    next_step: "/dashboard",
    boundary: SELF_SERVE_PROXY_BOUNDARY
  });
  response.cookies.set(SELF_SERVE_SESSION_COOKIE, payload.session_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return response;
}
