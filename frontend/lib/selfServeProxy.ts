import { verifiedSupabaseSession } from "@/lib/supabaseServer";

export const SELF_SERVE_PROXY_BOUNDARY =
  "V0.95 uses a confirmed Supabase Auth session for hosted dashboard and provisioning requests. PRMR API keys remain separate. Stripe billing and production authentication hardening are not implemented.";

export function backendBaseUrl() {
  return (process.env.PRMR_HOSTED_API_URL || "https://prmr-memory-core-api.onrender.com").replace(/\/$/, "");
}

export async function supabaseAccessToken() {
  return verifiedSupabaseSession();
}

export async function backendRequest(
  path: string,
  init: RequestInit = {},
  accessToken?: string
) {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
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
  delete payload.access_token;
  delete payload.refresh_token;
  delete payload.password;
  delete payload.password_hash;
  delete payload.key_hash;
  return payload;
}
