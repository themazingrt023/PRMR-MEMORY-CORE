import { NextRequest, NextResponse } from "next/server";
import { sendPrmrEvent, type ProjectEvent } from "@/lib/prmr";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const eventTypes: Record<string, string> = {
  create_project: "reference.project.created",
  set_goal: "reference.project.goal_updated",
  update_deadline: "reference.project.deadline_changed",
  add_blocker: "reference.project.blocker_recorded",
  record_decision: "reference.project.decision_recorded",
  complete_milestone: "reference.project.milestone_completed"
};

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const action = String(body.action || "");
  const eventType = eventTypes[action];
  if (!eventType) {
    return NextResponse.json({ error: { code: "unknown_project_action" } }, { status: 400 });
  }
  const actor = String(body.actor_reference || "actor_a");
  const workspace = String(body.workspace_reference || "workspace_acme");
  const entity = String(body.entity_reference || "project_alpha");
  const signal = String(body.signal || `${action} happened for ${entity}.`);
  const occurredAt = new Date().toISOString();
  const event: ProjectEvent = {
    event_type: eventType,
    signal,
    actor_reference: actor,
    workspace_reference: workspace,
    entity_reference: entity,
    occurred_at: occurredAt,
    idempotency_key: String(body.idempotency_key || `${workspace}:${entity}:${action}:${occurredAt}`),
    metadata: {
      source_app: "prmr_reference_client",
      action,
      synthetic: true
    }
  };
  const result = await sendPrmrEvent(event);
  return NextResponse.json(
    {
      action,
      event,
      prmr_status: result.status,
      prmr_body: result.body,
      raw_api_key_exposed: false,
      internal_route_used: false
    },
    { status: result.ok ? 200 : result.status }
  );
}
