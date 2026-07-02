"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createSupabaseBrowserClient,
  supabaseBrowserConfigured
} from "@/lib/supabaseClient";

const plans = [
  { id: "free", name: "Free", detail: "100 requests/month", state: "Can activate after confirmation" },
  { id: "builder", name: "Builder", detail: "10,000 requests/month", state: "Beta selection, unbilled" },
  { id: "controlled_pilot", name: "Controlled Pilot", detail: "Custom", state: "Manual approval" }
] as const;

export function StartFlow() {
  const router = useRouter();
  const [plan, setPlan] = useState("free");
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
      setMessage("Confirm your email before selecting and activating a plan.");
      return;
    }
    setBusy(true);
    setMessage("Asking PRMR to verify your identity and plan...");
    try {
      const response = await fetch("/api/self-serve/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan })
      });
      const payload = (await response.json().catch(() => ({}))) as {
        provisioned?: boolean;
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
      if (plan !== "free" || !payload.provisioned) {
        setMessage(
          plan === "builder"
            ? "Builder is recorded as an unbilled beta selection. Stripe is not connected."
            : "Controlled Pilot remains a manual approval path."
        );
        return;
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
      <fieldset>
        <legend className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/48">Choose a plan</legend>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {plans.map((item) => (
            <label
              className={`cursor-pointer border p-4 transition ${
                plan === item.id ? "border-white/45 bg-white/[0.05]" : "border-white/10 hover:border-white/25"
              }`}
              key={item.id}
            >
              <input
                checked={plan === item.id}
                className="sr-only"
                name="plan"
                onChange={() => setPlan(item.id)}
                type="radio"
                value={item.id}
              />
              <span className="block font-display text-2xl text-white">{item.name}</span>
              <span className="mt-2 block text-sm text-mist/64">{item.detail}</span>
              <span className="mt-3 block font-mono text-[10px] uppercase tracking-[0.12em] text-mist/38">
                {item.state}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <button
        className="silver-button px-6 py-4 font-mono text-xs uppercase disabled:opacity-35"
        disabled={!confirmed || busy}
        onClick={activate}
        type="button"
      >
        {busy ? "Checking access..." : plan === "free" ? "Activate Free workspace" : "Record plan selection"}
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
