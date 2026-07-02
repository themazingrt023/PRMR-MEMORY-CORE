import { NextResponse } from "next/server";
import { SELF_SERVE_SESSION_COOKIE } from "@/lib/selfServeProxy";

export async function POST() {
  const response = NextResponse.json({ status: "ok", session_cleared: true });
  response.cookies.set(SELF_SERVE_SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0
  });
  return response;
}
