"use client";

import { useEffect, useState } from "react";

type KeyRecord = {
  key_id: string;
  label: string;
  safe_key_preview: string;
  status: string;
  created_at: string;
  last_used_at?: string | null;
};

type Dashboard = {
  account: { name: string; email: string; status: string };
  plan: {
    subscription: { plan_id: string; status: string; billing_status: string };
    usage: { requests_used: number; requests_limit: number; requests_remaining: number };
  };
  client_scope: {
    client_id: string;
    vault_id: string;
    namespace: string;
    status: string;
  };
  api_keys: KeyRecord[];
  request_logs: Array<{
    timestamp: string;
    endpoint: string;
    status: string;
    reason: string;
    public_safe_message: string;
  }>;
  reports: Array<{
    report_id: string;
    summary: string;
    public_safe: boolean;
  }>;
  billing: { live: boolean; status: string; message: string };
  support: { mode: string };
};

type DashboardResponse = {
  status?: string;
  dashboard?: Dashboard;
  storage?: {
    storage_mode: string;
    durable_storage_verified: boolean;
    durable_storage_claim_allowed: boolean;
    hosted_storage_boundary: string;
  };
  error?: { code?: string; message?: string };
};

export function HostedSelfServeDashboard() {
  const [payload, setPayload] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [label, setLabel] = useState("Development server");
  const [oneTimeKey, setOneTimeKey] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    const response = await fetch("/api/dashboard/state", { cache: "no-store" });
    const body = (await response.json().catch(() => ({}))) as DashboardResponse;
    setPayload(body);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  async function keyAction(method: "POST" | "PATCH" | "DELETE", keyId?: string) {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/dashboard/keys", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(method === "POST" ? { label } : { key_id: keyId })
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
      await load();
    } catch {
      setMessage("The hosted key service could not be reached.");
    } finally {
      setBusy(false);
    }
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
    `PRMR_CLIENT_ID=${scope.client_id}`,
    `PRMR_VAULT_ID=${scope.vault_id}`,
    `PRMR_NAMESPACE=${scope.namespace}`
  ].join("\n");

  return (
    <div className="relative mx-auto max-w-[1500px] space-y-6 px-6 pb-24 pt-32">
      <section className="border border-white/12 bg-[var(--afternum-bg-panel)] p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="kimi-section-label">Hosted Self-Serve Workspace</p>
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

      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Plan" value={dashboard.plan.subscription.plan_id} />
        <Metric label="Requests used" value={String(dashboard.plan.usage.requests_used)} />
        <Metric label="Requests left" value={String(dashboard.plan.usage.requests_remaining)} />
        <Metric label="Storage" value={payload.storage?.storage_mode || "unverified"} />
      </div>

      <section className="grid gap-5 border border-white/10 bg-white/[0.012] p-6 lg:grid-cols-3">
        <Info label="Client ID" value={scope.client_id} />
        <Info label="Vault ID" value={scope.vault_id} />
        <Info label="Namespace" value={scope.namespace} />
      </section>

      <section className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6">
        <p className="kimi-section-label">API Keys</p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input className="field-input max-w-md" onChange={(event) => setLabel(event.target.value)} value={label} />
          <button
            className="silver-button px-5 py-3 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40"
            disabled={busy || label.trim().length < 2}
            onClick={() => keyAction("POST")}
            type="button"
          >
            Create API Key
          </button>
        </div>
        <p className="mt-3 text-sm text-mist/48">{message}</p>
        {oneTimeKey ? (
          <div className="mt-5 border border-white/25 bg-white/[0.03] p-5">
            <p className="text-sm font-semibold text-white">Copy this key now. PRMR will not show it again.</p>
            <code className="mt-4 block overflow-x-auto border border-white/10 bg-black/30 p-4 text-xs text-mist/80">
              {oneTimeKey}
            </code>
            <div className="mt-4 flex gap-3">
              <button className="ghost-button px-4 py-2 text-xs" onClick={() => navigator.clipboard.writeText(oneTimeKey)} type="button">
                Copy key
              </button>
              <button className="ghost-button px-4 py-2 text-xs" onClick={() => setOneTimeKey("")} type="button">
                I stored it
              </button>
            </div>
          </div>
        ) : null}
        <div className="mt-6 space-y-3">
          {dashboard.api_keys.length ? dashboard.api_keys.map((key) => (
            <article className="grid gap-4 border border-white/[0.08] p-4 md:grid-cols-[1fr_1fr_auto]" key={key.key_id}>
              <div>
                <p className="text-sm text-white">{key.label}</p>
                <p className="mt-2 font-mono text-xs text-mist/48">{key.safe_key_preview}</p>
              </div>
              <p className="font-mono text-xs uppercase tracking-[0.12em] text-mist/54">{key.status}</p>
              <div className="flex gap-2">
                <button className="ghost-button px-3 py-2 text-xs disabled:opacity-30" disabled={busy || key.status !== "active"} onClick={() => keyAction("PATCH", key.key_id)} type="button">
                  Rotate
                </button>
                <button className="ghost-button px-3 py-2 text-xs disabled:opacity-30" disabled={busy || key.status !== "active"} onClick={() => keyAction("DELETE", key.key_id)} type="button">
                  Revoke
                </button>
              </div>
            </article>
          )) : <p className="text-sm text-mist/48">No API key yet.</p>}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <Panel title="Server quickstart">
          <pre className="overflow-x-auto whitespace-pre-wrap border border-white/10 bg-black/25 p-4 font-mono text-xs leading-6 text-mist/72">{env}</pre>
          <p className="mt-4 text-sm text-mist/48">Keep the key server-side. Never place it in frontend code.</p>
        </Panel>
        <Panel title="Storage boundary">
          <p>{payload.storage?.hosted_storage_boundary || "Hosted durable storage has not been verified."}</p>
          <p className="mt-3">Real email, Stripe billing, and production authentication hardening remain unfinished.</p>
        </Panel>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <Panel title={`Request logs (${dashboard.request_logs.length})`}>
          {dashboard.request_logs.slice(-8).reverse().map((row) => (
            <div className="border-t border-white/[0.07] py-3 text-sm" key={`${row.timestamp}-${row.endpoint}`}>
              <span className="text-white">{row.endpoint}</span>
              <span className="ml-3 text-mist/46">{row.status} / {row.reason}</span>
            </div>
          ))}
          {!dashboard.request_logs.length ? <p>No requests recorded yet.</p> : null}
        </Panel>
        <Panel title={`Continuity reports (${dashboard.reports.length})`}>
          {dashboard.reports.map((report) => (
            <div className="border-t border-white/[0.07] py-3 text-sm" key={report.report_id}>
              <p className="font-mono text-xs text-white">{report.report_id}</p>
              <p className="mt-2">{report.summary}</p>
            </div>
          ))}
          {!dashboard.reports.length ? <p>No reports generated yet.</p> : null}
        </Panel>
      </section>
    </div>
  );
}

function State({ title, detail, children }: { title: string; detail: string; children?: React.ReactNode }) {
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

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-white/10 bg-[var(--afternum-bg-panel)] p-6 text-sm leading-6 text-mist/56">
      <h2 className="font-display text-3xl text-white">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}
