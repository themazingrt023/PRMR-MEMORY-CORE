import { NextResponse } from "next/server";
import { SELF_SERVE_PROXY_BOUNDARY } from "@/lib/selfServeProxy";

export async function POST() {
  return NextResponse.json(
    {
      status: "error",
      error: {
        code: "local_password_login_disabled",
        message: "Use the Supabase Auth login form."
      },
      boundary: SELF_SERVE_PROXY_BOUNDARY
    },
    { status: 410 }
  );
}
