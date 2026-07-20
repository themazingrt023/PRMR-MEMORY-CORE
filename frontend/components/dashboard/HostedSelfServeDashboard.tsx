"use client";

import { useEffect, useState, type ReactNode } from "react";

type KeyRecord = {
  key_id: string;
  label: string;
  safe_key_preview: string;
  status: string;
  created_at: string;
  last_used_at?: string | null;
  application_reference?: string;
  environment?: string;
};

type ApplicationRecord = {
  application_reference: string;
  name: string;
  environment: string;
  status: string;
  created_at: string;
  event_count: number;
  packet_count: number;
  last_request?: string | null;
  last_successful_ingest?: string | null;
  last_packet?: string | null;
  health_status: string;
  associated_key_count: number;
};

type Dashboard = {
  account: { name: string; email: string; status: string };
  plan: {
    subscription: { plan_id: string; status: string; billing_status: string };
    usage: { requests_used: number; requests_limit: number; requests_remaining: number };
  };
  client_scope: { client_id: string; vault_id: string; namespace: string; status: string };
  applications: ApplicationRecord[];
  api_keys: KeyRecord[];
  request_logs: DashboardLog[];
  reports: ReportSummary[];
  billing: { live: boolean; status: string; message: string };
  support: { mode: string };
  activation?: {
    steps: { event_type: string; label: string; completed: boolean }[];
    completed_count: number;
    total_count: number;
  };
};

type StorageBoundary = {
  storage_backend?: string;
  storage_mode?: string;
  database_connected?: boolean;
  durable_storage_verified?: boolean;
  durable_storage_claim_allowed?: boolean;
  raw_key_storage?: boolean;
  raw_password_storage?: boolean;
  public_safe?: boolean;
  hosted_storage_boundary?: string;
};

type DashboardResponse = {
  status?: string;
  dashboard?: Dashboard;
  storage?: StorageBoundary;
  error?: { code?: string; message?: string };
};

type DashboardLog = {
  log_id?: string;
  timestamp: string;
  method?: string;
  endpoint: string;
  status: string;
  allowed?: boolean;
  reason?: string;
  rejection_reason?: string | null;
  latency_ms?: number | null;
  public_safe_message?: string;
  client_scope?: { client_id: string; vault_id: string; namespace: string };
};

type LogsResponse = {
  logs?: DashboardLog[];
  total_count?: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
};

type ReportSummary = {
  report_id: string;
  created_timestamp?: string | null;
  summary: string;
  packet_id?: string | null;
  endpoint_source?: string;
  event_count?: number;
  public_safe: boolean;
};

type ReportsResponse = {
  reports?: ReportSummary[];
  total_count?: number;
  limit?: number;
  offset?: number;
  has_more?: boolean;
};

type PacketDetail = Record<string, unknown>;

type ReportDetailResponse = {
  report?: ReportSummary & {
    older_report_format?: boolean;
    older_report_message?: string | null;
    packet?: PacketDetail | null;
  };
  error?: { code?: string; message?: string };
};

type PacketResponse = {
  packet?: PacketDetail;
  report_id?: string;
  error?: { code?: string; message?: string };
};

type PacketScope = {
  application_reference: string;
  actor_reference: string;
  workspace_reference: string;
  entity_reference: string;
  session_reference: string;
  allow_broad_scope: boolean;
};

type PlaygroundState = {
  api_key: string;
  application_reference: string;
  actor_reference: string;
  workspace_reference: string;
  entity_reference: string;
  event_type: string;
  signal: string;
};

const emptyPacketScope: PacketScope = {
  application_reference: "app_main",
  actor_reference: "",
  workspace_reference: "",
  entity_reference: "",
  session_reference: "",
  allow_broad_scope: false
};

const PAGE_SIZE = 25;

const defaultPlayground: PlaygroundState = {
  api_key: "",
  application_reference: "app_main",
  actor_reference: "user_123",
  workspace_reference: "workspace_demo",
  entity_reference: "entity_demo",
  event_type: "prmr.playground.first_event",
  signal: "A first sandbox event was sent to PRMR."
};

export function HostedSelfServeDashboard() {
  const [payload, setPayload] = useState<DashboardResponse | null>(null);
  const [logs, setLogs] = useState<DashboardLog[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsHasMore, setLogsHasMore] = useState(false);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [reportsTotal, setReportsTotal] = useState(0);
  const [reportsHasMore, setReportsHasMore] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportDetailResponse["report"] | null>(null);
  const [packetResult, setPacketResult] = useState<PacketResponse | null>(null);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [label, setLabel] = useState("Sandbox server key");
  const [applicationName, setApplicationName] = useState("My First Application");
  const [applicationReference, setApplicationReference] = useState("app_main");
  const [applicationEnvironment, setApplicationEnvironment] = useState("sandbox");
  const [packetScope, setPacketScope] = useState<PacketScope>(emptyPacketScope);
  const [oneTimeKey, setOneTimeKey] = useState("");
  const [playground, setPlayground] = useState<PlaygroundState>(defaultPlayground);
  const [playgroundEventResult, setPlaygroundEventResult] = useState<Record<string, unknown> | null>(null);
  const [playgroundPacketResult, setPlaygroundPacketResult] = useState<PacketResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadDashboard() {
    const response = await fetch("/api/dashboard/state", { cache: "no-store" });
    const body = (await response.json().catch(() => ({}))) as DashboardResponse;
    setPayload(body);
    return body;
  }

  async function loadLogs(offset = 0, append = false) {
    const response = await fetch(`/api/dashboard/logs?limit=${PAGE_SIZE}&offset=${offset}`, { cache: "no-store" });
    const body = (await response.json().catch(() => ({}))) as LogsResponse;
    setLogs((current) => append ? [...current, ...(body.logs || [])] : body.logs || []);
    setLogsTotal(body.total_count || 0);
    setLogsHasMore(Boolean(body.has_more));
  }

  async function loadReports(offset = 0, append = false) {
    const response = await fetch(`/api/dashboard/reports?limit=${PAGE_SIZE}&offset=${offset}`, { cache: "no-store" });
    const body = (await response.json().catch(() => ({}))) as ReportsResponse;
    setReports((current) => append ? [...current, ...(body.reports || [])] : body.reports || []);
    setReportsTotal(body.total_count || 0);
    setReportsHasMore(Boolean(body.has_more));
  }

  async function loadAll() {
    setLoading(true);
    try {
      const body = await loadDashboard();
      if (body.dashboard) {
        await Promise.all([loadLogs(), loadReports()]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await loadAll();
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const stored = window.sessionStorage.getItem("prmr_one_time_activation_key") || "";
    if (stored) {
      setOneTimeKey(stored);
      setPlayground((current) => ({ ...current, api_key: stored }));
      window.sessionStorage.removeItem("prmr_one_time_activation_key");
      setMessage("Copy this key now. PRMR will not show it again.");
    }
  }, []);

  async function keyAction(method: "POST" | "PATCH" | "DELETE", keyId?: string) {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/keys", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          method === "POST"
            ? { label, application_reference: applicationReference, environment: applicationEnvironment }
            : { key_id: keyId }
        )
      });
      const body = (await response.json().catch(() => ({}))) as {
        raw_api_key?: string;
        error?: { message?: string };
      };
      if (!response.ok) {
        setMessage(body.error?.message || "The key action was blocked.");
        return;
      }
      if (body.raw_api_key) {
        setOneTimeKey(body.raw_api_key);
        setMessage("Copy this key now. PRMR will not show it again.");
      } else {
        setMessage(method === "DELETE" ? "Key revoked." : "Key updated.");
      }
      await loadAll();
    } catch {
      setMessage("The hosted key service could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function createApplication() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: applicationName,
          application_reference: applicationReference,
          environment: applicationEnvironment
        })
      });
      const body = (await response.json().catch(() => ({}))) as { error?: { message?: string; code?: string } };
      if (!response.ok) {
        setMessage(body.error?.message || body.error?.code || "Application creation was blocked.");
        return;
      }
      setPacketScope((current) => ({ ...current, application_reference: applicationReference }));
      setMessage("Application created.");
      await loadDashboard();
    } catch {
      setMessage("The application service could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function generatePacket() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/packet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(packetScope)
      });
      const body = (await response.json().catch(() => ({}))) as PacketResponse;
      if (!response.ok) {
        setMessage(body.error?.message || "Packet generation was blocked.");
        return;
      }
      setPacketResult(body);
      await Promise.all([loadDashboard(), loadLogs(), loadReports()]);
    } catch {
      setMessage("The packet service could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function sendPlaygroundEvent() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/playground/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(playground)
      });
      const body = (await response.json().catch(() => ({}))) as Record<string, unknown> & { error?: { message?: string; code?: string } };
      if (!response.ok) {
        setMessage(body.error?.message || body.error?.code || "The playground event was blocked.");
        return;
      }
      setPlaygroundEventResult(body);
      setMessage("First sandbox event accepted through the public API contract.");
      await Promise.all([loadDashboard(), loadLogs()]);
    } catch {
      setMessage("The hosted playground event route could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function generatePlaygroundPacket() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/playground/packet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(playground)
      });
      const body = (await response.json().catch(() => ({}))) as PacketResponse;
      if (!response.ok) {
        setMessage(body.error?.message || "The playground packet was blocked.");
        return;
      }
      setPlaygroundPacketResult(body);
      setMessage("Continuity packet generated from your sandbox event history.");
      await Promise.all([loadDashboard(), loadLogs(), loadReports()]);
    } catch {
      setMessage("The hosted playground packet route could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function openReport(reportId: string) {
    const response = await fetch(`/api/dashboard/reports/${encodeURIComponent(reportId)}`, { cache: "no-store" });
    const body = (await response.json().catch(() => ({}))) as ReportDetailResponse;
    if (response.ok && body.report) setSelectedReport(body.report);
    else setMessage(body.error?.message || "The report could not be opened.");
  }

  async function logout() {
    await fetch("/api/self-serve/logout", { method: "POST" });
    window.location.href = "/signup";
  }

  if (loading) {
    return <State title="Loading workspace" detail="Checking your hosted self-serve session..." />;
  }
  if (!payload?.dashboard) {
    return (
      <State
        title="Dashboard access is locked"
        detail="Create a hosted Free workspace first. If activation is unavailable, the Render backend still needs a verified server-side Postgres connection."
      >
        <a className="silver-button mt-7 inline-block px-6 py-4 font-mono text-xs uppercase tracking-[0.14em]" href="/signup">
          Create workspace
        </a>
      </State>
    );
  }

  const dashboard = payload.dashboard;
  const scope = dashboard.client_scope;
  const env = [
    "PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com",
    "PRMR_API_KEY=<YOUR_PRMR_KEY>",
    "",
    "# Optional explicit scope assertions:",
    `PRMR_CLIENT_ID=${scope.client_id}`,
    `PRMR_VAULT_ID=${scope.vault_id}`,
    `PRMR_NAMESPACE=${scope.namespace}`
  ].join("\n");

  return (
    <div className="relative mx-auto max-w-[1500px] space-y-6 px-6 pb-24 pt-32">
      <section className="border border-white/12 bg-[var(--afternum-bg-panel)] p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="kimi-section-label">Afternum API Dashboard</p>
            <h1 className="mt-5 font-display text-[clamp(44px,6vw,84px)] leading-[0.96] text-white">
              {dashboard.account.name}
            </h1>
            <p className="mt-5 text-sm text-mist/58">{dashboard.account.email}</p>
          </div>
          <button className="ghost-button px-4 py-3 font-mono text-[10px] uppercase tracking-[0.14em]" onClick={logout} type="button">
            Sign out
          </button>
        </div>
      </section>

      <PlanStorageBand
        dashboard={dashboard}
        onUpgrade={() => setUpgradeOpen(true)}
        storage={payload.storage}
      />

      <ActivationPlayground
        activation={dashboard.activation}
        busy={busy}
        message={message}
        oneTimeKey={oneTimeKey}
        onStored={() => setOneTimeKey("")}
        playground={playground}
        setPlayground={setPlayground}
        eventResult={playgroundEventResult}
        packetResult={playgroundPacketResult}
        onSendEvent={sendPlaygroundEvent}
        onGeneratePacket={generatePlaygroundPacket}
      />

      <section className="grid gap-5 border border-white/10 bg-white/[0.012] p-6 lg:grid-cols-3">
        <Info label="Client ID" value={scope.client_id} />
        <Info label="Vault ID" value={scope.vault_id} />
        <Info label="Namespace" value={scope.namespace} />
      </section>

      <ApplicationsSection
        applications={dashboard.applications || []}
        busy={busy}
        environment={applicationEnvironment}
        message={message}
        name={applicationName}
        onCreate={createApplication}
        onEnvironment={setApplicationEnvironment}
        onName={setApplicationName}
        onReference={setApplicationReference}
        reference={applicationReference}
      />

      <ApiKeySection
        apiKeys={dashboard.api_keys}
        busy={busy}
        label={label}
        message={message}
        onAction={keyAction}
        onLabel={setLabel}
        oneTimeKey={oneTimeKey}
        onStored={() => setOneTimeKey("")}
      />

      <section className="grid gap-6 lg:grid-cols-2">
        <Panel title="Server quickstart">
          <pre className="overflow-x-auto whitespace-pre-wrap border border-white/10 bg-black/25 p-4 font-mono text-xs leading-6 text-mist/72">{env}</pre>
          <p className="mt-4 text-sm text-mist/48">
            Bearer authentication is sufficient; PRMR resolves this key&apos;s scope. Optional scope headers are checked when supplied.
            Keep the key server-side and never place it in frontend code.
          </p>
        </Panel>
        <StorageBoundaryPanel storage={payload.storage} />
      </section>

      <PacketTester
        applications={dashboard.applications || []}
        busy={busy}
        packetResult={packetResult}
        packetScope={packetScope}
        setPacketScope={setPacketScope}
        onGenerate={generatePacket}
      />

      <section className="grid gap-6 xl:grid-cols-2">
        <RequestLogsPanel
          hasMore={logsHasMore}
          logs={logs}
          onMore={() => loadLogs(logs.length, true)}
          total={logsTotal}
        />
        <ReportsPanel
          hasMore={reportsHasMore}
          onMore={() => loadReports(reports.length, true)}
          onOpen={openReport}
          reports={reports}
          total={reportsTotal}
        />
      </section>

      {selectedReport ? <ReportDetailModal report={selectedReport} onClose={() => setSelectedReport(null)} /> : null}
      {upgradeOpen ? <UpgradeModal onClose={() => setUpgradeOpen(false)} /> : null}
    </div>
  );
}

function PlanStorageBand({ dashboard, storage, onUpgrade }: { dashboard: Dashboard; storage?: StorageBoundary; onUpgrade: () => void }) {
  const usage = dashboard.plan.usage;
  return (
    <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
      <div className="border border-white/10 bg-[var(--afternum-bg-panel)] p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">Current plan</p>
        <p className="mt-3 text-2xl capitalize text-white">{dashboard.plan.subscription.plan_id}</p>
        <p className="mt-2 text-sm text-mist/50">{usage.requests_limit} requests/month. {usage.requests_remaining} remaining.</p>
        <button className="silver-button mt-5 px-4 py-3 font-mono text-xs uppercase tracking-[0.14em]" onClick={onUpgrade} type="button">
          Upgrade plan
        </button>
      </div>
      <Metric label="Requests used" value={String(usage.requests_used)} />
      <Metric label="Requests left" value={String(usage.requests_remaining)} />
      <Metric label="Storage" value={storage?.storage_mode || "unverified"} />
    </section>
  );
}

function ActivationPlayground({
  activation,
  busy,
  message,
  oneTimeKey,
  onStored,
  playground,
  setPlayground,
  eventResult,
  packetResult,
  onSendEvent,
  onGeneratePacket
}: {
  activation?: Dashboard["activation"];
  busy: boolean;
  message: string;
  oneTimeKey: string;
  onStored: () => void;
  playground: PlaygroundState;
  setPlayground: (value: PlaygroundState) => void;
  eventResult: Record<string, unknown> | null;
  packetResult: PacketResponse | null;
  onSendEvent: () => void;
  onGeneratePacket: () => void;
}) {
  function update(field: keyof PlaygroundState, value: string) {
    setPlayground({ ...playground, [field]: value });
  }
  return (
    <section className="border border-white/12 bg-[var(--afternum-bg-panel)] p-6">
      <div className="grid gap-8 xl:grid-cols-[0.95fr_1.05fr]">
        <div>
          <p className="kimi-section-label">First run</p>
          <h2 className="mt-4 font-display text-[clamp(34px,4vw,58px)] leading-none text-white">
            Send events. Receive continuity.
          </h2>
          <p className="mt-5 max-w-xl text-sm leading-7 text-mist/60">
            Your sandbox starts with one application, one scoped client/vault/namespace,
            and one copy-once server key. Use synthetic data here; keep live product keys server-side.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {(activation?.steps || []).map((step) => (
              <div className="border border-white/[0.08] bg-white/[0.012] p-4" key={step.event_type}>
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">
                  {step.completed ? "Complete" : "Pending"}
                </p>
                <p className="mt-2 text-sm text-white">{step.label}</p>
              </div>
            ))}
          </div>
          {oneTimeKey ? (
            <div className="mt-6 border border-white/25 bg-white/[0.03] p-5">
              <p className="text-sm font-semibold text-white">Copy this API key now. PRMR will not show it again.</p>
              <code className="mt-4 block overflow-x-auto border border-white/10 bg-black/30 p-4 text-xs text-mist/80">{oneTimeKey}</code>
              <div className="mt-4 flex flex-wrap gap-3">
                <button className="ghost-button px-4 py-2 text-xs" onClick={() => navigator.clipboard.writeText(oneTimeKey)} type="button">
                  Copy key
                </button>
                <button className="ghost-button px-4 py-2 text-xs" onClick={onStored} type="button">
                  I stored it
                </button>
              </div>
            </div>
          ) : null}
        </div>
        <div className="border border-white/[0.08] bg-white/[0.012] p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/42">Public API playground</p>
          <div className="mt-5 grid gap-3">
            <input
              className="field-input"
              onChange={(event) => update("api_key", event.target.value)}
              placeholder="Paste your PRMR API key for this sandbox test only"
              type="password"
              value={playground.api_key}
            />
            <div className="grid gap-3 md:grid-cols-2">
              <input className="field-input" onChange={(event) => update("application_reference", event.target.value)} value={playground.application_reference} />
              <input className="field-input" onChange={(event) => update("actor_reference", event.target.value)} value={playground.actor_reference} />
              <input className="field-input" onChange={(event) => update("workspace_reference", event.target.value)} value={playground.workspace_reference} />
              <input className="field-input" onChange={(event) => update("entity_reference", event.target.value)} value={playground.entity_reference} />
            </div>
            <input className="field-input" onChange={(event) => update("event_type", event.target.value)} value={playground.event_type} />
            <textarea className="field-input min-h-24" onChange={(event) => update("signal", event.target.value)} value={playground.signal} />
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button className="silver-button px-5 py-3 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40" disabled={busy || !playground.api_key} onClick={onSendEvent} type="button">
              Send Test Event
            </button>
            <button className="ghost-button px-5 py-3 text-xs disabled:opacity-40" disabled={busy || !playground.api_key} onClick={onGeneratePacket} type="button">
              Generate Packet
            </button>
          </div>
          <p aria-live="polite" className="mt-4 text-sm text-mist/52">{message}</p>
          {eventResult ? (
            <p className="mt-4 border border-white/[0.08] p-3 text-sm text-mist/64">
              Event result: {String(eventResult.status || "ok")} / accepted {String(eventResult.accepted_event_count ?? "unknown")}
            </p>
          ) : null}
          {packetResult?.packet ? <PacketFields packet={packetResult.packet} /> : null}
        </div>
      </div>
    </section>
  );
}

function ApiKeySection({
  apiKeys,
  busy,
  label,
  message,
  onAction,
  onLabel,
  oneTimeKey,
  onStored
}: {
  apiKeys: KeyRecord[];
  busy: boolean;
  label: string;
  message: string;
  onAction: (method: "POST" | "PATCH" | "DELETE", keyId?: string) => void;
  onLabel: (value: string) => void;
  oneTimeKey: string;
  onStored: () => void;
}) {
  return (
    <section className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">API Keys</p>
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <input className="field-input max-w-md" onChange={(event) => onLabel(event.target.value)} value={label} />
        <button
          className="silver-button px-5 py-3 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40"
          disabled={busy || label.trim().length < 2}
          onClick={() => onAction("POST")}
          type="button"
        >
          Create API Key
        </button>
      </div>
      <p className="mt-3 text-sm text-mist/48">{message}</p>
      {oneTimeKey ? (
        <div className="mt-5 border border-white/25 bg-white/[0.03] p-5">
          <p className="text-sm font-semibold text-white">Copy this key now. PRMR will not show it again.</p>
          <code className="mt-4 block overflow-x-auto border border-white/10 bg-black/30 p-4 text-xs text-mist/80">{oneTimeKey}</code>
          <div className="mt-4 flex gap-3">
            <button className="ghost-button px-4 py-2 text-xs" onClick={() => navigator.clipboard.writeText(oneTimeKey)} type="button">
              Copy key
            </button>
            <button className="ghost-button px-4 py-2 text-xs" onClick={onStored} type="button">
              I stored it
            </button>
          </div>
        </div>
      ) : null}
      <div className="mt-6 space-y-3">
        {apiKeys.length ? apiKeys.map((key) => (
          <article className="grid gap-4 border border-white/[0.08] p-4 md:grid-cols-[1fr_1fr_auto]" key={key.key_id}>
            <div>
              <p className="text-sm text-white">{key.label}</p>
              <p className="mt-2 font-mono text-xs text-mist/48">{key.safe_key_preview}</p>
              <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/36">
                {key.application_reference || "app_main"} / {key.environment || "production"}
              </p>
            </div>
            <p className="font-mono text-xs uppercase tracking-[0.12em] text-mist/54">{key.status}</p>
            <div className="flex gap-2">
              <button className="ghost-button px-3 py-2 text-xs disabled:opacity-30" disabled={busy || key.status !== "active"} onClick={() => onAction("PATCH", key.key_id)} type="button">
                Rotate
              </button>
              <button className="ghost-button px-3 py-2 text-xs disabled:opacity-30" disabled={busy || key.status !== "active"} onClick={() => onAction("DELETE", key.key_id)} type="button">
                Revoke
              </button>
            </div>
          </article>
        )) : <p className="text-sm text-mist/48">No API key yet.</p>}
      </div>
    </section>
  );
}

function ApplicationsSection({
  applications,
  busy,
  environment,
  message,
  name,
  onCreate,
  onEnvironment,
  onName,
  onReference,
  reference
}: {
  applications: ApplicationRecord[];
  busy: boolean;
  environment: string;
  message: string;
  name: string;
  onCreate: () => void;
  onEnvironment: (value: string) => void;
  onName: (value: string) => void;
  onReference: (value: string) => void;
  reference: string;
}) {
  return (
    <section className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Applications</p>
      <div className="mt-5 grid gap-3 lg:grid-cols-[1.2fr_1fr_0.8fr_auto]">
        <input className="field-input" onChange={(event) => onName(event.target.value)} placeholder="Application name" value={name} />
        <input className="field-input" onChange={(event) => onReference(event.target.value)} placeholder="application_reference" value={reference} />
        <select className="field-input" onChange={(event) => onEnvironment(event.target.value)} value={environment}>
          <option value="sandbox">sandbox</option>
          <option value="production">production</option>
          <option value="staging">staging</option>
          <option value="development">development</option>
          <option value="test">test</option>
        </select>
        <button className="silver-button px-5 py-3 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40" disabled={busy || name.trim().length < 2} onClick={onCreate} type="button">
          Create Application
        </button>
      </div>
      <p className="mt-3 text-sm text-mist/48">{message}</p>
      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        {applications.map((app) => (
          <article className="border border-white/[0.08] bg-white/[0.018] p-4" key={`${app.application_reference}-${app.environment}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm text-white">{app.name}</p>
                <p className="mt-2 font-mono text-xs text-mist/48">{app.application_reference}</p>
              </div>
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-mist/44">{app.environment}</p>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
              <Info label="Events" value={String(app.event_count || 0)} />
              <Info label="Packets" value={String(app.packet_count || 0)} />
              <Info label="Health" value={app.health_status || "ready"} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function PacketTester({
  applications,
  busy,
  packetResult,
  packetScope,
  setPacketScope,
  onGenerate
}: {
  applications: ApplicationRecord[];
  busy: boolean;
  packetResult: PacketResponse | null;
  packetScope: PacketScope;
  setPacketScope: (value: PacketScope) => void;
  onGenerate: () => void;
}) {
  function update(field: keyof PacketScope, value: string | boolean) {
    setPacketScope({ ...packetScope, [field]: value });
  }
  return (
    <Panel title="Continuity packet tester">
      <p>
        Generate a deterministic continuity packet for a requested application, actor, workspace, or entity.
        This uses server-side dashboard authentication and does not expose API keys.
      </p>
      <div className="mt-5 grid gap-3 lg:grid-cols-5">
        <select className="field-input" onChange={(event) => update("application_reference", event.target.value)} value={packetScope.application_reference}>
          <option value="">application optional</option>
          {applications.map((app) => (
            <option key={app.application_reference} value={app.application_reference}>{app.application_reference}</option>
          ))}
        </select>
        <input className="field-input" onChange={(event) => update("actor_reference", event.target.value)} placeholder="actor_reference" value={packetScope.actor_reference} />
        <input className="field-input" onChange={(event) => update("workspace_reference", event.target.value)} placeholder="workspace_reference" value={packetScope.workspace_reference} />
        <input className="field-input" onChange={(event) => update("entity_reference", event.target.value)} placeholder="entity_reference" value={packetScope.entity_reference} />
        <input className="field-input" onChange={(event) => update("session_reference", event.target.value)} placeholder="session_reference optional" value={packetScope.session_reference} />
      </div>
      <label className="mt-4 flex items-center gap-3 text-sm text-mist/54">
        <input checked={packetScope.allow_broad_scope} onChange={(event) => update("allow_broad_scope", event.target.checked)} type="checkbox" />
        Allow deliberate broad packet when the scope matches multiple actors, workspaces, or entities.
      </label>
      <button className="silver-button mt-5 px-5 py-3 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40" disabled={busy} onClick={onGenerate} type="button">
        Generate Continuity Packet
      </button>
      {packetResult?.packet ? <PacketFields packet={packetResult.packet} /> : null}
    </Panel>
  );
}

function RequestLogsPanel({ logs, total, hasMore, onMore }: { logs: DashboardLog[]; total: number; hasMore: boolean; onMore: () => void }) {
  return (
    <Panel title={`Request logs (${total})`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/38">
            <tr className="border-b border-white/[0.08]">
              <th className="py-3 pr-4 font-normal">Time</th>
              <th className="py-3 pr-4 font-normal">Method</th>
              <th className="py-3 pr-4 font-normal">Endpoint</th>
              <th className="py-3 pr-4 font-normal">Status</th>
              <th className="py-3 pr-4 font-normal">Reason</th>
              <th className="py-3 font-normal">Log ID</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((row, index) => (
              <tr className="border-b border-white/[0.055] text-mist/62" key={row.log_id || `${row.timestamp}-${row.endpoint}-${index}`}>
                <td className="py-4 pr-4 font-mono text-xs">{row.timestamp}</td>
                <td className="py-4 pr-4 font-mono text-xs">{row.method || ""}</td>
                <td className="py-4 pr-4 font-mono text-xs text-white">{row.endpoint}</td>
                <td className={row.allowed ? "py-4 pr-4 text-white" : "py-4 pr-4 text-mist/44"}>{row.allowed ? "allowed" : "denied"}</td>
                <td className="py-4 pr-4">{row.rejection_reason || row.reason || "allowed"}</td>
                <td className="py-4 font-mono text-xs text-mist/42">{row.log_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!logs.length ? <p>No requests recorded yet.</p> : null}
      {hasMore ? <button className="ghost-button mt-5 px-4 py-2 text-xs" onClick={onMore} type="button">Load more</button> : null}
    </Panel>
  );
}

function ReportsPanel({ reports, total, hasMore, onMore, onOpen }: { reports: ReportSummary[]; total: number; hasMore: boolean; onMore: () => void; onOpen: (reportId: string) => void }) {
  return (
    <Panel title={`Continuity reports (${total})`}>
      <div className="space-y-3">
        {reports.map((report) => (
          <article className="border border-white/[0.08] bg-white/[0.018] p-4" key={report.report_id}>
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">{report.report_id}</p>
                <h3 className="mt-2 font-display text-2xl text-white">{report.summary}</h3>
                <p className="mt-2 text-xs text-mist/44">Packet {report.packet_id || "limited"} / {report.event_count ?? "unknown"} events</p>
              </div>
              <button className="ghost-button h-fit px-4 py-2 text-xs" onClick={() => onOpen(report.report_id)} type="button">
                View detail
              </button>
            </div>
          </article>
        ))}
      </div>
      {!reports.length ? <p>No reports generated yet.</p> : null}
      {hasMore ? <button className="ghost-button mt-5 px-4 py-2 text-xs" onClick={onMore} type="button">Load more</button> : null}
    </Panel>
  );
}

function ReportDetailModal({ report, onClose }: { report: NonNullable<ReportDetailResponse["report"]>; onClose: () => void }) {
  return (
    <Modal title="Continuity report detail" onClose={onClose}>
      <p className="font-mono text-xs text-mist/46">{report.report_id}</p>
      <p className="mt-3 text-white">{report.summary}</p>
      {report.older_report_format ? <p className="mt-4 text-sm text-mist/50">{report.older_report_message}</p> : null}
      {report.packet ? <PacketFields packet={report.packet} /> : null}
    </Modal>
  );
}

function PacketFields({ packet }: { packet: PacketDetail }) {
  const fields = [
    "current_state",
    "active_information",
    "latent_information",
    "lineage_information",
    "causal_signature",
    "recursive_horizon",
    "coherence_score",
    "recoverability_score",
    "re_emergence_signals",
    "decayed_signals",
    "repeated_patterns",
    "state_transition_summary",
    "event_count",
    "last_updated"
  ];
  return (
    <div className="mt-6 grid gap-3">
      {fields.map((field) => (
        <div className="border border-white/[0.08] p-4" key={field}>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">{field}</p>
          <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-5 text-mist/68">{formatValue(packet[field])}</pre>
        </div>
      ))}
    </div>
  );
}

function StorageBoundaryPanel({ storage }: { storage?: StorageBoundary }) {
  return (
    <Panel title="Storage boundary">
      <p>
        PRMR stores account, key metadata, usage logs, reports, and continuity state in hosted managed Postgres.
        Raw API keys are shown once and are not stored. Stored key material remains hashed.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Info label="Storage backend" value={storage?.storage_backend || "unknown"} />
        <Info label="Storage mode" value={storage?.storage_mode || "unknown"} />
        <Info label="Database connected" value={String(Boolean(storage?.database_connected))} />
        <Info label="Durable storage verified" value={String(Boolean(storage?.durable_storage_verified))} />
        <Info label="Raw key storage" value="false" />
        <Info label="Raw password storage" value="false" />
        <Info label="Public safe" value={String(storage?.public_safe ?? true)} />
      </div>
      <p className="mt-5 text-mist/48">{storage?.hosted_storage_boundary || "Hosted storage boundary has not been verified for this session."}</p>
    </Panel>
  );
}

function UpgradeModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Upgrade plan" onClose={onClose}>
      <p className="text-mist/62">
        Billing is not connected yet. Builder and Pilot access are currently handled manually during controlled beta.
      </p>
      <div className="mt-6 grid gap-3">
        <Tier name="Free" detail="100 requests/month" />
        <Tier name="Builder" detail="10,000 requests/month. Manual beta access." />
        <Tier name="Controlled Pilot" detail="Custom/manual access." />
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <a className="silver-button px-4 py-3 text-xs" href="/contact">Request Builder access</a>
        <a className="ghost-button px-4 py-3 text-xs" href="/contact">Request Controlled Pilot</a>
        <a className="ghost-button px-4 py-3 text-xs" href="/contact">Contact Afternum</a>
      </div>
    </Modal>
  );
}

function Tier({ name, detail }: { name: string; detail: string }) {
  return (
    <div className="border border-white/[0.08] p-4">
      <p className="text-white">{name}</p>
      <p className="mt-2 text-sm text-mist/50">{detail}</p>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-8">
      <section className="max-h-[88vh] w-full max-w-5xl overflow-auto border border-white/14 bg-[var(--afternum-bg-panel)] p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-5">
          <h2 className="font-display text-4xl text-white">{title}</h2>
          <button className="ghost-button px-3 py-2 text-xs" onClick={onClose} type="button">Close</button>
        </div>
        <div className="mt-6 text-sm leading-6 text-mist/56">{children}</div>
      </section>
    </div>
  );
}

function formatValue(value: unknown) {
  if (value === undefined || value === null || value === "") return "Not available";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function State({ title, detail, children }: { title: string; detail: string; children?: ReactNode }) {
  return (
    <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
      <p className="kimi-section-label">PRMR Dashboard</p>
      <h1 className="mt-5 font-display text-[clamp(44px,7vw,92px)] leading-[0.96] text-white">{title}</h1>
      <p className="mt-6 max-w-3xl text-base leading-7 text-mist/62">{detail}</p>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/10 bg-white/[0.012] p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">{label}</p>
      <p className="mt-3 break-words text-xl text-white">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/38">{label}</p>
      <p className="mt-3 break-all text-sm text-mist/72">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6 text-sm leading-6 text-mist/56">
      <h2 className="font-display text-3xl text-white">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}
