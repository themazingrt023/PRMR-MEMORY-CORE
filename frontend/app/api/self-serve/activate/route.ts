import { NextRequest, NextResponse } from "next/server";
import {
  backendRequest,
  SELF_SERVE_PROXY_BOUNDARY,
  SELF_SERVE_SESSION_COOKIE
} from "@/lib/selfServeProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ActivationBody = {
  name?: string;
  email?: string;
  password?: string;
  plan?: string;
};

async function json(response: Response) {
  return (await response.json().catch(() => ({}))) as Record<string, any>;
}

function failed(response: Response, payload: Record<string, any>, step: string) {
  return NextResponse.json(
    {
      status: "error",
      activation_step: step,
      error: payload.error || { code: "hosted_activation_failed", message: "Hosted activation did not complete." },
      boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: response.status || 502 }
  );
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as ActivationBody;
  const name = String(body.name || "").trim();
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");
  const plan = String(body.plan || "free");
  if (name.length < 2 || !email.includes("@") || password.length < 10) {
    return NextResponse.json(
      { status: "error", error: { code: "invalid_signup_fields" }, boundary: SELF_SERVE_PROXY_BOUNDARY },
      { status: 400 }
    );
  }
  if (plan !== "free") {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "hosted_plan_not_active",
          message: "Only the Free plan activates in V0.94. Builder billing is not connected and Pilot remains manual."
        },
        boundary: SELF_SERVE_PROXY_BOUNDARY
      },
      { status: 409 }
    );
  }

  const signupResponse = await backendRequest("/v1/self-serve/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password })
  });
  const signup = await json(signupResponse);
  if (!signupResponse.ok) return failed(signupResponse, signup, "signup");

  const userId = String(signup.account?.user_id || "");
  const verifyResponse = await backendRequest("/v1/self-serve/verify", {
    method: "POST",
    body: JSON.stringify({ user_id: userId })
  });
  const verify = await json(verifyResponse);
  if (!verifyResponse.ok) return failed(verifyResponse, verify, "local_test_verification");

  const loginResponse = await backendRequest("/v1/self-serve/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  const login = await json(loginResponse);
  if (!loginResponse.ok || !login.session_token) return failed(loginResponse, login, "session_login");
  const token = String(login.session_token);

  const planResponse = await backendRequest(
    "/v1/self-serve/plan",
    { method: "POST", body: JSON.stringify({ plan_id: "free" }) },
    token
  );
  const planPayload = await json(planResponse);
  if (!planResponse.ok) return failed(planResponse, planPayload, "plan");

  const scopeResponse = await backendRequest("/v1/self-serve/provision", { method: "POST" }, token);
  const scopePayload = await json(scopeResponse);
  if (!scopeResponse.ok) return failed(scopeResponse, scopePayload, "provision");

  const response = NextResponse.json(
    {
      status: "ok",
      verification_mode: "local_test_no_email_sent",
      plan: "free",
      scope: scopePayload.scope,
      session_token_exposed: false,
      api_key_created: false,
      next_step: "/dashboard",
      boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: 201 }
  );
  response.cookies.set(SELF_SERVE_SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return response;
}
