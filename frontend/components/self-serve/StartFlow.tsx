"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createSupabaseBrowserClient,
  supabaseBrowserConfigured
} from "@/lib/supabaseClient";

export function StartFlow() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function loadIdentity() {
      if (!supabaseBrowserConfigured()) {
        setMessage("Account access is temporarily unavailable. Please try again shortly.");
        setLoading(false);
        return;
      }
      const supabase = createSupabaseBrowserClient();
      const { data, error } = await supabase.auth.getUser();
      if (error || !data.user) {
        setMessage("Sign in with a verified account to continue.");
        setLoading(false);
        return;
      }
      setEmail(data.user.email || "");
      setConfirmed(Boolean(data.user.email_confirmed_at));
      setLoading(false);
    }
    void loadIdentity();
  }, []);

  async function activate() {
    if (!confirmed) {
      setMessage("Confirm your email before activating your PRMR workspace.");
      return;
    }
    setBusy(true);
    setMessage("Creating your sandbox workspace, default scope, and copy-once server key...");
    try {
      const response = await fetch("/api/self-serve/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: "free" })
      });
      const payload = (await response.json().catch(() => ({}))) as {
        provisioned?: boolean;
        raw_api_key?: string;
        safe_key_preview?: string;
        next_step?: string;
        error?: { message?: string; code?: string };
      };
      if (!response.ok) {
        const code = payload.error?.code || "";
        if (
          code.includes("session") ||
          code.includes("token") ||
          code.includes("confirmation") ||
          response.status === 401 ||
          response.status === 403
        ) {
          setMessage("We could not verify your account session. Please sign in again, then return to this page.");
        } else if (response.status >= 500) {
          setMessage("We could not reach the PRMR backend. Please try again in a moment.");
        } else {
          setMessage("We could not activate your workspace. Please try again.");
        }
        return;
      }
      if (!payload.provisioned) {
        setMessage("PRMR could not finish workspace provisioning. Please try again.");
        return;
      }
      if (payload.raw_api_key) {
        window.sessionStorage.setItem("prmr_one_time_activation_key", payload.raw_api_key);
      }
      router.push("/dashboard");
    } catch {
      setMessage("We could not reach the PRMR backend. Please try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="mt-10 text-sm text-mist/54">Checking your account session...</p>;
  }

  return (
    <div className="mt-10 space-y-6">
      <section className="border border-white/10 bg-white/[0.015] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/42">Confirmed identity</p>
            <p className="mt-3 text-sm text-white">{email || "No authenticated identity"}</p>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/54">
            {confirmed ? "Email confirmed" : "Confirmation required"}
          </span>
        </div>
      </section>
      <section className="grid gap-3 md:grid-cols-3">
        {[
          ["1", "Workspace", "Create your PRMR account scope."],
          ["2", "Sandbox key", "Copy one server-side API key once."],
          ["3", "First packet", "Send an event and generate continuity."]
        ].map(([step, title, detail]) => (
          <article className="border border-white/10 bg-white/[0.015] p-5" key={step}>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/38">Step {step}</p>
            <h2 className="mt-3 font-display text-2xl text-white">{title}</h2>
            <p className="mt-2 text-sm text-mist/58">{detail}</p>
          </article>
        ))}
      </section>
      <button
        className="silver-button px-6 py-4 font-mono text-xs uppercase disabled:opacity-35"
        disabled={!confirmed || busy}
        onClick={activate}
        type="button"
      >
        {busy ? "Activating..." : "Activate Sandbox Workspace"}
      </button>
      {!confirmed ? (
        <a className="ml-4 text-sm text-white/70 underline" href="/verify-email">
          Confirm email
        </a>
      ) : null}
      <p aria-live="polite" className="text-sm text-mist/54">{message}</p>
    </div>
  );
}
