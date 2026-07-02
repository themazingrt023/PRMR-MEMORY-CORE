"use client";

import { useState } from "react";
import { dashboardMockData, type DashboardKeyRecord } from "@/data/dashboardMockData";

type LocalKeyRecord = DashboardKeyRecord & {
  label: string;
  createdAt?: string;
};

type KeyResponse = {
  status: string;
  key?: {
    keyId: string;
    label: string;
    safeKeyPreview: string;
    status: "active";
    createdAt: string;
  };
  rawApiKey?: string;
  copyWarning?: string;
  error?: { message?: string };
};

const statusStyles = {
  active: "border-white/24 text-white",
  rotated: "border-silver/16 text-mist/62",
  revoked: "border-silver/12 text-mist/46"
};

export function ApiKeyPanel() {
  const [records, setRecords] = useState<LocalKeyRecord[]>(
    dashboardMockData.apiKeyPanel.records.map((record) => ({ ...record, label: record.label }))
  );
  const [label, setLabel] = useState("Development server");
  const [oneTimeKey, setOneTimeKey] = useState<string | null>(null);
  const [oneTimePreview, setOneTimePreview] = useState<string | null>(null);
  const [message, setMessage] = useState("Local synthetic controls are ready.");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function requestKey(method: "POST" | "PATCH", record?: LocalKeyRecord) {
    setBusy(true);
    setCopied(false);
    try {
      const response = await fetch("/api/dashboard/keys", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: record?.label || label, keyId: record?.keyId })
      });
      const payload = (await response.json()) as KeyResponse;
      if (!response.ok || !payload.key || !payload.rawApiKey) {
        setMessage(payload.error?.message || "Synthetic key action was blocked.");
        return;
      }
      const next: LocalKeyRecord = {
        keyId: payload.key.keyId,
        clientId: dashboardMockData.clientOverview.clientId,
        label: payload.key.label,
        safeKeyPreview: payload.key.safeKeyPreview,
        status: "active",
        vaultId: dashboardMockData.clientOverview.vaultId,
        namespace: dashboardMockData.clientOverview.namespace,
        lastUsedAt: "Not used",
        operatorNote: "Synthetic local key. Only the safe preview remains after dismissal.",
        createdAt: payload.key.createdAt
      };
      setRecords((current) => [
        ...(record ? current.map((item) => (item.keyId === record.keyId ? { ...item, status: "rotated" as const } : item)) : current),
        next
      ]);
      setOneTimeKey(payload.rawApiKey);
      setOneTimePreview(payload.key.safeKeyPreview);
      setMessage(method === "POST" ? "Synthetic key created." : "Synthetic replacement key created; the old key is rotated.");
    } catch {
      setMessage("The local synthetic key route could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(record: LocalKeyRecord) {
    setBusy(true);
    try {
      const response = await fetch("/api/dashboard/keys", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyId: record.keyId })
      });
      if (!response.ok) {
        setMessage("Synthetic revoke was blocked.");
        return;
      }
      setRecords((current) =>
        current.map((item) => (item.keyId === record.keyId ? { ...item, status: "revoked" as const } : item))
      );
      setMessage("Synthetic key revoked.");
    } finally {
      setBusy(false);
    }
  }

  async function copyOneTimeKey() {
    if (!oneTimeKey) return;
    await navigator.clipboard.writeText(oneTimeKey);
    setCopied(true);
  }

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="kimi-section-label">API Keys</p>
          <h2 className="mt-4 font-display text-4xl text-white">Create, rotate, and revoke.</h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-mist/54">
            This frontend console creates non-functional local keys only. The Python V0.92 service implements scoped
            copy-once keys that validate against protected PRMR operations.
          </p>
        </div>
        <div className="w-full max-w-md">
          <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/42" htmlFor="key-label">
            Key label
          </label>
          <div className="mt-2 flex gap-2">
            <input
              className="min-w-0 flex-1 border border-white/12 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-white/35"
              id="key-label"
              maxLength={64}
              onChange={(event) => setLabel(event.target.value)}
              value={label}
            />
            <button
              className="border border-white/22 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.14em] text-white transition hover:border-white/50 hover:bg-white/[0.06] disabled:opacity-40"
              disabled={busy || label.trim().length < 2}
              onClick={() => requestKey("POST")}
              type="button"
            >
              Create API Key
            </button>
          </div>
          <p className="mt-2 text-xs text-mist/42">{message}</p>
        </div>
      </div>

      {oneTimeKey ? (
        <div className="mt-7 border border-white/24 bg-white/[0.035] p-5" role="status">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-white">One-time key</p>
          <p className="mt-3 text-sm font-semibold text-white">Copy this key now. PRMR will not show it again.</p>
          <code className="mt-4 block overflow-x-auto border border-white/10 bg-black/30 p-4 font-mono text-xs text-mist/82">
            {oneTimeKey}
          </code>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className="border border-white/22 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-white hover:bg-white/[0.06]"
              onClick={copyOneTimeKey}
              type="button"
            >
              {copied ? "Copied" : "Copy key"}
            </button>
            <button
              className="border border-white/10 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/60 hover:text-white"
              onClick={() => setOneTimeKey(null)}
              type="button"
            >
              I have stored it
            </button>
          </div>
          <p className="mt-3 text-xs text-mist/40">Later views retain only {oneTimePreview}.</p>
        </div>
      ) : null}

      <div className="mt-7 space-y-3">
        {records.map((record) => (
          <article
            className="grid gap-4 border border-white/[0.08] bg-white/[0.012] p-4 lg:grid-cols-[1.1fr_1fr_auto_auto]"
            key={record.keyId}
          >
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">{record.label}</p>
              <p className="mt-2 break-words text-sm text-mist/64">{record.keyId}</p>
            </div>
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">Safe preview</p>
              <p className="mt-2 font-mono text-sm text-white">{record.safeKeyPreview}</p>
            </div>
            <div className={`h-fit border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] ${statusStyles[record.status]}`}>
              {record.status}
            </div>
            <div className="flex gap-2">
              <button
                className="border border-white/12 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/64 hover:border-white/30 hover:text-white disabled:opacity-30"
                disabled={busy || record.status !== "active"}
                onClick={() => requestKey("PATCH", record)}
                type="button"
              >
                Rotate
              </button>
              <button
                className="border border-white/12 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/52 hover:border-white/30 hover:text-white disabled:opacity-30"
                disabled={busy || record.status !== "active"}
                onClick={() => revoke(record)}
                type="button"
              >
                Revoke
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
