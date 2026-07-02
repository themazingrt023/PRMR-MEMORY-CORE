import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export function supabaseServerConfigured() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  );
}

export async function createSupabaseServerClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("Supabase Auth is not configured for this server.");
  }
  const cookieStore = await cookies();
  return createServerClient(url, key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Server Components cannot always write cookies. Route handlers can.
        }
      }
    }
  });
}

export function createSupabaseRouteClient(
  request: NextRequest,
  response: NextResponse
) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("Account authentication is not configured for this server.");
  }
  return createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headersToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
        Object.entries(headersToSet).forEach(([name, value]) => {
          response.headers.set(name, value);
        });
      }
    }
  });
}

export async function verifiedSupabaseSession() {
  if (!supabaseServerConfigured()) {
    return { accessToken: "", user: null, reason: "supabase_env_missing" };
  }
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
    error
  } = await supabase.auth.getUser();
  if (error || !user) {
    return { accessToken: "", user: null, reason: "supabase_session_required" };
  }
  if (!user.email_confirmed_at) {
    return { accessToken: "", user: null, reason: "supabase_email_confirmation_required" };
  }
  const {
    data: { session }
  } = await supabase.auth.getSession();
  if (!session?.access_token) {
    return { accessToken: "", user: null, reason: "supabase_session_required" };
  }
  return { accessToken: session.access_token, user, reason: "allowed" };
}
