"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

type ActivationStep = { event_type: string; label: string; completed: boolean };
type Dashboard = {
  account: { name: string; email: string };
  plan: { usage: { requests_used: number; requests_limit: number; requests_remaining: number } };
  applications: { application_reference: string; name: string; environment: string; event_count: number; packet_count: number }[];
  api_keys: KeyRecord[];
  activation?: { steps: ActivationStep[]; completed_count: number; total_count: number };
};
type KeyRecord = { key_id: string; label: string; safe_key_preview: string; status: string; created_at: string; last_used_at?: string | null };
type EventRecord = {
  event_id: string;
  actor_reference: string;
  entity_reference: string;
  event_type: string;
  status: string;
  occurred_at: string;
  received_at: string;
  readable_summary: string;
  payload?: unknown;
  associated_packets?: string[];
};
type PacketRecord = {
  packet_id?: string;
  report_id?: string;
  actor_reference?: string;
  created?: string | null;
  events_considered?: number;
  status?: string;
  summary?: string;
};
type ActorRecord = {
  actor_reference: string;
  latest_activity?: string | null;
  event_count: number;
  packet_count: number;
  status: string;
  latest_packet_id?: string | null;
  current_continuity?: string | null;
};
type LogRecord = {
  log_id?: string;
  timestamp: string;
  method?: string;
  endpoint: string;
  status: string;
  allowed?: boolean;
  reason?: string;
  rejection_reason?: string | null;
  public_safe_message?: string;
};
type PacketDetail = Record<string, unknown>;
type Usage = {
  events_received: number;
  packets_generated: number;
  active_actors: number;
  api_requests: number;
  requests_used: number;
  requests_remaining: number;
  requests_limit: number;
  storage_used: null | string;
  storage_measured: boolean;
  billing_live: boolean;
};

const PAGE_SIZE = 50;

export function HostedSelfServeDashboard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [packets, setPackets] = useState<PacketRecord[]>([]);
  const [actors, setActors] = useState<ActorRecord[]>([]);
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [oneTimeKey, setOneTimeKey] = useState("");
  const [keyName, setKeyName] = useState("Server key");
  const [playgroundJson, setPlaygroundJson] = useState('{"actor_id":"test_actor","event_type":"task.completed","payload":{"summary":"A test task was completed."}}');
  const [playgroundPacket, setPlaygroundPacket] = useState<PacketDetail | null>(null);
  const [selectedPacket, setSelectedPacket] = useState<PacketDetail | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<EventRecord | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function json<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, { cache: "no-store", ...init });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.error?.code || "request_failed");
    return body as T;
  }

  async function loadAll() {
    setLoading(true);
    try {
      const [state, eventBody, packetBody, actorBody, logBody, usageBody] = await Promise.all([
        json<{ dashboard?: Dashboard }>("/api/dashboard/state"),
        json<{ events?: EventRecord[] }>(`/api/dashboard/events?limit=${PAGE_SIZE}`),
        json<{ packets?: PacketRecord[] }>(`/api/dashboard/packets?limit=${PAGE_SIZE}`),
        json<{ actors?: ActorRecord[] }>(`/api/dashboard/actors?limit=${PAGE_SIZE}`),
        json<{ logs?: LogRecord[] }>(`/api/dashboard/logs?limit=${PAGE_SIZE}`),
        json<{ usage?: Usage }>("/api/dashboard/usage/live")
      ]);
      setDashboard(state.dashboard || null);
      setEvents(eventBody.events || []);
      setPackets(packetBody.packets || []);
      setActors(actorBody.actors || []);
      setLogs(logBody.logs || []);
      setUsage(usageBody.usage || null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
    const stored = window.sessionStorage.getItem("prmr_one_time_activation_key") || "";
    if (stored) {
      setOneTimeKey(stored);
      window.sessionStorage.removeItem("prmr_one_time_activation_key");
    }
  }, []);

  const activeApp = dashboard?.applications?.[0];
  const activationSteps = dashboard?.activation?.steps || [];
  const firstRunDone = Boolean(usage && usage.events_received > 0 && usage.packets_generated > 0);
  const latestEvent = events[0];
  const latestPacket = packets[0];
  const recentErrors = logs.filter((row) => row.allowed === false || row.status !== "ok").slice(0, 3);

  async function createKey() {
    setBusy(true);
    setMessage("");
    try {
      const body = await json<{ raw_api_key?: string }>("/api/dashboard/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: keyName })
      });
      if (body.raw_api_key) setOneTimeKey(body.raw_api_key);
      setMessage(body.raw_api_key ? "Copy this key now. PRMR will not show it again." : "Key created.");
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Key action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function keyAction(method: "PATCH" | "DELETE", keyId: string) {
    setBusy(true);
    setMessage("");
    try {
      const body = await json<{ raw_api_key?: string }>("/api/dashboard/keys", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key_id: keyId })
      });
      if (body.raw_api_key) setOneTimeKey(body.raw_api_key);
      setMessage(method === "PATCH" ? "Key rotated. Copy the replacement now if shown." : "Key revoked.");
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Key action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function generateTestPacket() {
    setBusy(true);
    setMessage("");
    try {
      const parsed = JSON.parse(playgroundJson || "{}") as Record<string, unknown>;
      const validation = validatePlayground(parsed);
      if (validation) {
        setMessage(validation);
        return;
      }
      await json("/api/dashboard/playground/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor_reference: String(parsed.actor_id),
          event_type: String(parsed.event_type),
          signal: JSON.stringify(parsed.payload || {}),
          payload: JSON.stringify(parsed.payload || {}),
          timestamp: String(parsed.timestamp || new Date().toISOString())
        })
      });
      const packet = await json<{ packet?: PacketDetail }>("/api/dashboard/playground/packet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_reference: String(parsed.actor_id), entity_reference: String(parsed.actor_id) })
      });
      setPlaygroundPacket(packet.packet || null);
      setMessage("TEST MODE packet generated. Live continuity was not touched.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Playground failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resetPlayground() {
    setBusy(true);
    try {
      await json("/api/dashboard/playground", { method: "DELETE" });
      setPlaygroundPacket(null);
      setMessage("TEST MODE data reset. Live Events, Packets and Actors were not touched.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openPacket(packetId?: string) {
    if (!packetId) return;
    try {
      const body = await json<{ packet?: PacketDetail }>(`/api/dashboard/packets/${encodeURIComponent(packetId)}`);
      setSelectedPacket(body.packet || null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Packet could not be opened.");
    }
  }

  if (loading) return <State title="Loading Memory Core" detail="Checking your console session..." />;
  if (!dashboard) {
    return (
      <State title="Console locked" detail="Sign in or create an account to activate Memory Core.">
        <a className="silver-button mt-6 inline-block px-5 py-3 text-xs" href="/signup">Start building</a>
      </State>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 px-6 pb-24 pt-8">
      <section id="home" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="kimi-section-label">Memory Core Home</p>
            <h1 className="mt-4 font-display text-[clamp(42px,6vw,76px)] leading-none text-white">
              {firstRunDone ? "Memory Core is working." : "Your Memory Core is ready."}
            </h1>
            <p className="mt-5 max-w-3xl text-sm leading-7 text-mist/58">
              {firstRunDone
                ? "Your software has sent events and PRMR has generated continuity packets."
                : "Copy your API key, send your first event, then generate your first continuity packet."}
            </p>
          </div>
          <button className="ghost-button px-4 py-3 text-xs" onClick={() => void fetch("/api/self-serve/logout", { method: "POST" }).then(() => { window.location.href = "/login"; })} type="button">
            Sign out
          </button>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <Metric label="Events received" value={String(usage?.events_received ?? 0)} />
          <Metric label="Packets generated" value={String(usage?.packets_generated ?? 0)} />
          <Metric label="Active actors" value={String(usage?.active_actors ?? 0)} />
          <Metric label="Usage this month" value={`${usage?.requests_used ?? 0}/${usage?.requests_limit ?? 0}`} />
          <Metric label="Attention required" value={recentErrors.length ? `${recentErrors.length} issue(s)` : "None"} />
        </div>
        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          <Panel title="First-run progress">
            <Progress steps={activationSteps} oneTimeKey={oneTimeKey} />
            <div className="mt-5 flex flex-wrap gap-3">
              {oneTimeKey ? <button className="silver-button px-4 py-3 text-xs" onClick={() => navigator.clipboard.writeText(oneTimeKey)} type="button">Copy API Key</button> : null}
              <a className="ghost-button px-4 py-3 text-xs" href="#playground">Open Playground</a>
              <a className="ghost-button px-4 py-3 text-xs" href="#how-to-use">View How to Use</a>
            </div>
          </Panel>
          <Panel title="Recent activity">
            <Activity label="Latest event" value={latestEvent ? `${latestEvent.actor_reference} / ${latestEvent.event_type}` : "No live events yet"} />
            <Activity label="Latest packet" value={latestPacket?.packet_id || "No live packets yet"} />
            <Activity label="Current application" value={activeApp?.name || "My First Application"} />
          </Panel>
        </div>
      </section>

      <section id="playground" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <p className="kimi-section-label">TEST MODE</p>
        <h2 className="mt-3 font-display text-5xl text-white">Playground</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-mist/58">
          Data created here is isolated and will not affect live continuity. The Playground uses the real Memory Core engine in a resettable test boundary.
        </p>
        <div className="mt-6 grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
          <Panel title="Paste JSON">
            <textarea className="field-input min-h-56" value={playgroundJson} onChange={(event) => setPlaygroundJson(event.target.value)} />
            <p className="mt-3 text-sm text-mist/48">Required mapping: Actor ID, Event Type, Timestamp, Payload.</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button className="silver-button px-4 py-3 text-xs disabled:opacity-40" disabled={busy} onClick={generateTestPacket} type="button">Generate Test Packet</button>
              <button className="ghost-button px-4 py-3 text-xs disabled:opacity-40" disabled={busy} onClick={resetPlayground} type="button">Reset Test Data</button>
              <button className="ghost-button px-4 py-3 text-xs" onClick={() => setPlaygroundJson(samplePlaygroundJson)} type="button">Sample Data</button>
            </div>
          </Panel>
          <Panel title="Results">
            <TabsJson packet={playgroundPacket} empty="No TEST MODE packet generated yet." />
          </Panel>
        </div>
      </section>

      <section id="events" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Events" detail="Live customer activity received by Memory Core." />
        <DataTable
          columns={["Actor", "Event", "Status", "Received"]}
          rows={events.map((event) => [
            event.actor_reference,
            event.event_type,
            event.status,
            event.received_at,
            <button className="ghost-button px-3 py-2 text-xs" onClick={() => setSelectedEvent(event)} type="button" key={event.event_id}>Detail</button>
          ])}
          empty="No live events yet."
        />
      </section>

      <section id="packets" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Packets" detail="Continuity packets are the primary Memory Core output." />
        <DataTable
          columns={["Packet ID", "Actor", "Created", "Events Considered", "Status"]}
          rows={packets.map((packet) => [
            packet.packet_id || "",
            packet.actor_reference || "",
            packet.created || "",
            String(packet.events_considered || 0),
            packet.status || "Ready",
            <button className="ghost-button px-3 py-2 text-xs" onClick={() => openPacket(packet.packet_id)} type="button" key={packet.packet_id}>Open</button>
          ])}
          empty="No live packets yet."
        />
      </section>

      <section id="actors" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Actors" detail="An actor is the person or thing whose continuity Memory Core is preserving." />
        <DataTable
          columns={["Actor ID", "Latest Activity", "Events", "Packets", "Status"]}
          rows={actors.map((actor) => [
            actor.actor_reference,
            actor.latest_activity || "",
            String(actor.event_count),
            String(actor.packet_count),
            actor.status
          ])}
          empty="No actors yet. Send an event to create the first actor."
        />
      </section>

      <section id="api-keys" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="API Keys" detail="Keys are server-side credentials. Raw key values are shown once only." />
        {oneTimeKey ? (
          <div className="mb-5 border border-white/25 bg-white/[0.03] p-5">
            <p className="font-semibold text-white">Copy this key now. PRMR will not show it again.</p>
            <code className="mt-4 block overflow-x-auto border border-white/10 bg-black/30 p-4 text-xs text-mist/80">{oneTimeKey}</code>
            <button className="ghost-button mt-4 px-4 py-2 text-xs" onClick={() => setOneTimeKey("")} type="button">I stored it</button>
          </div>
        ) : null}
        <div className="mb-6 flex flex-wrap gap-3">
          <input className="field-input max-w-sm" value={keyName} onChange={(event) => setKeyName(event.target.value)} />
          <button className="silver-button px-4 py-3 text-xs disabled:opacity-40" disabled={busy || keyName.trim().length < 2} onClick={createKey} type="button">Create Key</button>
        </div>
        <DataTable
          columns={["Name", "Created", "Last Used", "Status"]}
          rows={(dashboard.api_keys || []).map((key) => [
            key.label,
            key.created_at,
            key.last_used_at || "Never",
            key.status,
            <span className="flex gap-2" key={key.key_id}>
              <button className="ghost-button px-3 py-2 text-xs" disabled={busy || key.status !== "active"} onClick={() => keyAction("PATCH", key.key_id)} type="button">Rotate</button>
              <button className="ghost-button px-3 py-2 text-xs" disabled={busy || key.status !== "active"} onClick={() => keyAction("DELETE", key.key_id)} type="button">Revoke</button>
            </span>
          ])}
          empty="No API keys yet."
        />
      </section>

      <section id="usage" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Usage" detail="Truthful operational usage. Billing is hidden until real metering and payment flows exist." />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <Metric label="Events Received" value={String(usage?.events_received ?? 0)} />
          <Metric label="Packets Generated" value={String(usage?.packets_generated ?? 0)} />
          <Metric label="Active Actors" value={String(usage?.active_actors ?? 0)} />
          <Metric label="API Requests" value={String(usage?.api_requests ?? 0)} />
          <Metric label="Storage Used" value={usage?.storage_measured ? String(usage.storage_used) : "Not measured"} />
        </div>
      </section>

      <section id="logs" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Logs" detail="API/system interactions. Events are customer activity; logs are request behavior." />
        <p className="mb-4 text-sm text-mist/54">Why did this request fail? Open the log detail and use the plain-language reason plus corrected example.</p>
        <DataTable
          columns={["Time", "Request", "Status", "Duration"]}
          rows={logs.map((log) => [
            log.timestamp,
            `${log.method || ""} ${log.endpoint}`,
            log.allowed ? "Success" : "Error",
            "Not measured",
            log.rejection_reason || log.reason || log.public_safe_message || ""
          ])}
          empty="No logs yet."
        />
      </section>

      <section id="how-to-use" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="How to Use Memory Core" detail="Send events. Generate continuity packets. Use them inside your software." />
        <p className="mb-5 text-sm text-mist/54">Which events created the packet? Open a packet and inspect Source Events and Provenance.</p>
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Quickstart">
            <ol className="space-y-3 text-sm text-mist/64">
              <li>1. Copy your API key</li>
              <li>2. Send an event</li>
              <li>3. Generate a packet</li>
              <li>4. Use the packet inside your software</li>
            </ol>
          </Panel>
          <Panel title="cURL">
            <pre className="overflow-auto whitespace-pre-wrap text-xs text-mist/70">{curlExample}</pre>
          </Panel>
          <Panel title="Node.js">
            <pre className="overflow-auto whitespace-pre-wrap text-xs text-mist/70">{nodeExample}</pre>
          </Panel>
          <Panel title="Python">
            <pre className="overflow-auto whitespace-pre-wrap text-xs text-mist/70">{pythonExample}</pre>
          </Panel>
        </div>
      </section>

      <section id="settings" className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <SectionTitle title="Settings" detail="Simple controls first. Infrastructure details are kept under Advanced." />
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="General"><Activity label="Application Name" value={activeApp?.name || "My First Application"} /><Activity label="Timezone" value="Browser/default" /></Panel>
          <Panel title="Security"><Activity label="API Key Activity" value={`${dashboard.api_keys.length} key record(s)`} /><Activity label="Allowed Origins" value="Managed server-side" /></Panel>
          <Panel title="Data"><Activity label="Export Data" value="Planned" /><Activity label="Delete Actor Data" value="Requires backend confirmation flow before enabling" /></Panel>
          <Panel title="Advanced"><Activity label="Application ID" value={activeApp?.application_reference || "app_main"} /><Activity label="Storage Boundary" value="Visible in backend health/reporting, hidden from primary workflow" /></Panel>
        </div>
      </section>

      <p aria-live="polite" className="text-sm text-mist/54">{message}</p>
      {selectedEvent ? <Modal title="Event Detail" onClose={() => setSelectedEvent(null)}><TabsJson packet={selectedEvent as unknown as PacketDetail} empty="" /></Modal> : null}
      {selectedPacket ? <Modal title="Packet Detail" onClose={() => setSelectedPacket(null)}><HumanPacket packet={selectedPacket} /><TabsJson packet={selectedPacket} empty="" /></Modal> : null}
    </div>
  );
}

function validatePlayground(payload: Record<string, unknown>) {
  if (!payload.actor_id || typeof payload.actor_id !== "string") return "Validation: Actor ID is required.";
  if (!payload.event_type || typeof payload.event_type !== "string") return "Validation: Event Type is required.";
  if (payload.timestamp && Number.isNaN(Date.parse(String(payload.timestamp)))) return "Validation: Timestamp must be parseable.";
  if (payload.payload === undefined) return "Validation: Payload is required.";
  return "";
}

function Progress({ steps, oneTimeKey }: { steps: ActivationStep[]; oneTimeKey: string }) {
  const rendered = steps.length ? steps : [
    { event_type: "account_created", label: "Account created", completed: true },
    { event_type: "sandbox_key_created", label: "API key created", completed: Boolean(oneTimeKey) },
    { event_type: "first_event_ingested", label: "First event received", completed: false },
    { event_type: "first_continuity_packet_generated", label: "First packet generated", completed: false }
  ];
  return (
    <div className="grid gap-3">
      {rendered.map((step) => (
        <div className="flex items-center gap-3 text-sm" key={step.event_type}>
          <span className={step.completed ? "text-white" : "text-mist/36"}>{step.completed ? "✓" : "○"}</span>
          <span className={step.completed ? "text-white" : "text-mist/52"}>{step.label.replace("Default client/vault/namespace ready", "Memory Core ready").replace("Sandbox key created", "API key created")}</span>
        </div>
      ))}
      {oneTimeKey ? <div className="border border-white/20 p-4"><code className="break-all text-xs text-mist/78">{oneTimeKey}</code></div> : null}
    </div>
  );
}

function HumanPacket({ packet }: { packet: PacketDetail }) {
  return (
    <div className="grid gap-3">
      <Activity label="Current State" value={format(packet.current_state)} />
      <Activity label="Recent Changes" value={format(packet.active_information)} />
      <Activity label="Important History" value={format(packet.latent_information)} />
      <Activity label="Open Threads" value={format(packet.re_emergence_signals)} />
      <Activity label="Relevant Relationships" value={format(packet.lineage_information)} />
      <Activity label="Supporting Events" value={format((packet.provenance as Record<string, unknown> | undefined)?.source_event_ids)} />
    </div>
  );
}

function TabsJson({ packet, empty }: { packet: PacketDetail | null; empty: string }) {
  if (!packet) return <p className="text-sm text-mist/48">{empty}</p>;
  return (
    <div className="mt-4 grid gap-3">
      <HumanPacket packet={packet} />
      <details className="border border-white/[0.08] p-4">
        <summary className="cursor-pointer text-sm text-white">JSON / Timeline / Source Events / Provenance</summary>
        <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-5 text-mist/68">{JSON.stringify(packet, null, 2)}</pre>
      </details>
      <div className="flex flex-wrap gap-3">
        <button className="ghost-button px-3 py-2 text-xs" onClick={() => navigator.clipboard.writeText(JSON.stringify(packet, null, 2))} type="button">Copy JSON</button>
        <button className="ghost-button px-3 py-2 text-xs" onClick={() => navigator.clipboard.writeText(nodeExample)} type="button">Copy Node.js Example</button>
        <button className="ghost-button px-3 py-2 text-xs" onClick={() => navigator.clipboard.writeText(pythonExample)} type="button">Copy Python Example</button>
        <button className="ghost-button px-3 py-2 text-xs" onClick={() => navigator.clipboard.writeText(curlExample)} type="button">Copy cURL Example</button>
      </div>
    </div>
  );
}

function SectionTitle({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="mb-6">
      <p className="kimi-section-label">{title}</p>
      <h2 className="mt-3 font-display text-5xl text-white">{title}</h2>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-mist/58">{detail}</p>
    </div>
  );
}

function DataTable({ columns, rows, empty }: { columns: string[]; rows: ReactNode[][]; empty: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/38">
          <tr className="border-b border-white/[0.08]">{columns.map((column) => <th className="py-3 pr-4 font-normal" key={column}>{column}</th>)}<th /></tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr className="border-b border-white/[0.055] text-mist/62" key={index}>
              {row.map((cell, cellIndex) => <td className="py-4 pr-4" key={cellIndex}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="mt-4 text-sm text-mist/48">{empty}</p> : null}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="border border-white/[0.08] bg-white/[0.012] p-5"><h3 className="font-display text-2xl text-white">{title}</h3><div className="mt-4 text-sm leading-6 text-mist/58">{children}</div></section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="border border-white/10 bg-white/[0.012] p-5"><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">{label}</p><p className="mt-3 break-words text-xl text-white">{value}</p></div>;
}

function Activity({ label, value }: { label: string; value: string }) {
  return <div className="border-b border-white/[0.06] py-3"><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/36">{label}</p><p className="mt-2 break-words text-white">{value}</p></div>;
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8">
      <section className="max-h-[88vh] w-full max-w-5xl overflow-auto border border-white/14 bg-[var(--afternum-bg-panel)] p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-5"><h2 className="font-display text-4xl text-white">{title}</h2><button className="ghost-button px-3 py-2 text-xs" onClick={onClose} type="button">Close</button></div>
        <div className="mt-6 text-sm leading-6 text-mist/56">{children}</div>
      </section>
    </div>
  );
}

function State({ title, detail, children }: { title: string; detail: string; children?: ReactNode }) {
  return <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32"><p className="kimi-section-label">Memory Core</p><h1 className="mt-5 font-display text-[clamp(44px,7vw,92px)] leading-[0.96] text-white">{title}</h1><p className="mt-6 max-w-3xl text-base leading-7 text-mist/62">{detail}</p>{children}</section>;
}

function format(value: unknown) {
  if (value === undefined || value === null || value === "") return "Not available";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

const samplePlaygroundJson = `{
  "actor_id": "test_actor",
  "event_type": "project.updated",
  "timestamp": "2026-07-21T12:00:00Z",
  "payload": {
    "summary": "A test project changed deadline and added a blocker."
  }
}`;

const curlExample = `curl -X POST "$PRMR_API_BASE_URL/v1/events/ingest" \\
  -H "Authorization: Bearer <PRMR_API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{"events":[{"actor_reference":"actor_123","event_type":"project.updated","signal":"Deadline changed.","occurred_at":"2026-07-21T12:00:00Z","metadata":{"source_app":"your_app"}}]}'`;

const nodeExample = `await fetch(process.env.PRMR_API_BASE_URL + "/v1/continuity/packet", {
  method: "POST",
  headers: { Authorization: "Bearer " + process.env.PRMR_API_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ actor_reference: "actor_123" })
});`;

const pythonExample = `import os, requests
requests.post(
  os.environ["PRMR_API_BASE_URL"] + "/v1/events/ingest",
  headers={"Authorization": "Bearer " + os.environ["PRMR_API_KEY"]},
  json={"events": [{"actor_reference": "actor_123", "event_type": "project.updated", "signal": "Deadline changed."}]},
)`;
