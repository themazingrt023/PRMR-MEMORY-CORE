import { NextResponse } from "next/server";
import { callLocalDemoBridge, publicBridgeError } from "../localBridge";
import { demoBridgeDisabledResponse, isLocalDemoBridgeEnabled } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  if (!isLocalDemoBridgeEnabled()) {
    return demoBridgeDisabledResponse();
  }

  try {
    const payload = await callLocalDemoBridge("health");
    return NextResponse.json(payload);
  } catch {
    return NextResponse.json(publicBridgeError(), { status: 500 });
  }
}
