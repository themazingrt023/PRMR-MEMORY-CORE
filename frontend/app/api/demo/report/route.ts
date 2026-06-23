import { NextResponse } from "next/server";
import { callLocalDemoBridge, publicBridgeError } from "../localBridge";
import { demoBridgeDisabledResponse, isLocalDemoBridgeEnabled } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  if (!isLocalDemoBridgeEnabled()) {
    return demoBridgeDisabledResponse();
  }

  try {
    const url = new URL(request.url);
    const scenarioId = url.searchParams.get("scenario_id") || "ai_agent_memory";
    const payload = await callLocalDemoBridge("report", scenarioId);
    const status = payload.status === "ok" ? 200 : 400;
    return NextResponse.json(payload, { status });
  } catch {
    return NextResponse.json(publicBridgeError(), { status: 500 });
  }
}
