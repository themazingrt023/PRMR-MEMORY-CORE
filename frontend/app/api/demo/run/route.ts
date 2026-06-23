import { NextResponse } from "next/server";
import { callLocalDemoBridge, publicBridgeError } from "../localBridge";
import { demoBridgeDisabledResponse, isLocalDemoBridgeEnabled } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (!isLocalDemoBridgeEnabled()) {
    return demoBridgeDisabledResponse();
  }

  try {
    const body = (await request.json().catch(() => ({}))) as { scenario_id?: string };
    const scenarioId = String(body.scenario_id || "");
    const payload = await callLocalDemoBridge("run", scenarioId);
    const status = payload.status === "ok" ? 200 : 400;
    return NextResponse.json(payload, { status });
  } catch {
    return NextResponse.json(publicBridgeError(), { status: 500 });
  }
}
