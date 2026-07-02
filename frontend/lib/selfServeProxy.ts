import { cookies } from "next/headers";

export const SELF_SERVE_SESSION_COOKIE = "prmr_self_serve_session";
export const SELF_SERVE_PROXY_BOUNDARY =
  "V0.94 hosted self-serve activation MVP. Session tokens remain in an HTTP-only cookie. Real email, Stripe billing, and production authentication hardening are not implemented.";

export function backendBaseUrl() {
  return (process.env.PRMR_HOSTED_API_URL || "https://prmr-memory-core-api.onrender.com").replace(/\/$/, "");
}

export async function sessionToken() {
  const cookieStore = await cookies();
  return cookieStore.get(SELF_SERVE_SESSION_COOKIE)?.value || "";
}

export async function backendRequest(
  path: string,
  init: RequestInit = {},
  token?: string
) {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Session ${token}`);
  return fetch(`${backendBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
}

export async function safePayload(response: Response) {
  const payload = (await response.json().catch(() => ({
    status: "error",
    error: { code: "non_json_backend_response", message: "The hosted backend returned an unreadable response." }
  }))) as Record<string, unknown>;
  delete payload.session_token;
  delete payload.password;
  delete payload.password_hash;
  delete payload.key_hash;
  return payload;
}
