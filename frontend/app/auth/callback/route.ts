import { NextRequest, NextResponse } from "next/server";
import {
  createSupabaseRouteClient,
  supabaseServerConfigured
} from "@/lib/supabaseServer";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function redirect(response: NextResponse, destination: URL) {
  response.headers.set("Location", destination.toString());
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const startUrl = new URL("/start", requestUrl.origin);
  const response = NextResponse.redirect(startUrl);

  if (!supabaseServerConfigured() || !code) {
    return redirect(
      response,
      new URL("/login?error=auth_callback_failed", requestUrl.origin)
    );
  }

  const auth = createSupabaseRouteClient(request, response);
  const { data, error } = await auth.auth.exchangeCodeForSession(code);
  if (error) {
    return redirect(
      response,
      new URL("/login?error=auth_callback_failed", requestUrl.origin)
    );
  }

  const {
    data: { user }
  } = await auth.auth.getUser();
  if (data.session && user?.email_confirmed_at) {
    return redirect(response, startUrl);
  }

  return redirect(
    response,
    new URL("/login?verified=1", requestUrl.origin)
  );
}
