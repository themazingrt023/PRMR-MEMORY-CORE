import { NextResponse } from "next/server";
import {
  createSupabaseServerClient,
  supabaseServerConfigured
} from "@/lib/supabaseServer";

export async function POST() {
  if (supabaseServerConfigured()) {
    const supabase = await createSupabaseServerClient();
    await supabase.auth.signOut();
  }
  return NextResponse.json({
    status: "ok",
    supabase_session_cleared: true,
    prmr_api_key_affected: false
  });
}
