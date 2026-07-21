"use client";

import { useState } from "react";

type Packet = Record<string, unknown>;

const actions = [
  ["create_project", "Create project"],
  ["set_goal", "Set project goal"],
  ["update_deadline", "Update deadline"],
  ["add_blocker", "Add blocker"],
  ["record_decision", "Record decision"],
  ["complete_milestone", "Complete milestone"]
];

export function ProjectClient() {
  const [actor, setActor] = useState("actor_a");
  const [entity, setEntity] = useState("project_alpha");
  const [signal, setSignal] = useState("Project Alpha moved from vague idea to scoped delivery plan.");
  const [message, setMessage] = useState("");
  const [packet, setPacket] = useState<Packet | null>(null);

  async function runAction(action: string) {
    setMessage("Sending event to PRMR...");
    const response = await fetch("/api/project/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        actor_reference: actor,
        workspace_reference: "workspace_acme",
        entity_reference: entity,
        signal,
        idempotency_key: `reference-client:${actor}:${entity}:${action}`
      })
    });
    const body = await response.json().catch(() => ({}));
    setMessage(response.ok ? `PRMR accepted ${body.prmr_body?.accepted_event_count ?? 0} event(s).` : `PRMR rejected the event: ${body.error?.code || body.prmr_body?.error?.code || response.status}`);
  }

  async function loadPacket() {
    setMessage("Requesting scoped continuity packet...");
    const response = await fetch("/api/project/packet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor_reference: actor,
        workspace_reference: "workspace_acme",
        entity_reference: entity
      })
    });
    const body = await response.json().catch(() => ({}));
    setPacket(body.packet || null);
    setMessage(response.ok ? "Continuity packet received from PRMR." : `Packet request failed: ${body.error?.code || response.status}`);
  }

  return (
    <main className="shell">
      <header className="top">
        <div>
          <p className="eyebrow">Independent reference client</p>
          <h1>PRMR Reference Project Client</h1>
        </div>
        <p className="eyebrow">Uses public PRMR HTTP only</p>
      </header>
      <section className="grid">
        <div className="panel">
          <p className="eyebrow">Project workflow</p>
          <p>This app stores ordinary project state separately. PRMR is used only for continuity events and packets.</p>
          <div className="actions">
            <input value={actor} onChange={(event) => setActor(event.target.value)} aria-label="Actor reference" />
            <input value={entity} onChange={(event) => setEntity(event.target.value)} aria-label="Entity reference" />
            <textarea value={signal} onChange={(event) => setSignal(event.target.value)} aria-label="Signal" />
            {actions.map(([action, label]) => (
              <button key={action} onClick={() => runAction(action)} type="button">{label}</button>
            ))}
            <button onClick={loadPacket} type="button">Request continuity packet</button>
          </div>
          <p>{message}</p>
        </div>
        <div className="panel">
          <p className="eyebrow">Continuity view</p>
          {packet ? (
            <div className="packet">
              {[
                "current_state",
                "active_information",
                "latent_information",
                "lineage_information",
                "repeated_patterns",
                "state_transition_summary",
                "coherence_score",
                "recoverability_score",
                "event_count",
                "packet_id",
                "last_updated"
              ].map((field) => (
                <div className="metric" key={field}>
                  <code>{field}</code>
                  <strong>{JSON.stringify(packet[field])}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p>No packet loaded yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}
