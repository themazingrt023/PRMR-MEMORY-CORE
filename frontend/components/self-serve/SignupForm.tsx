"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const plans = [
  { id: "free", name: "Free", detail: "100 requests/month", state: "Hosted MVP when backend is active" },
  { id: "builder", name: "Builder", detail: "10,000 requests/month", state: "Billing is not live" },
  { id: "controlled_pilot", name: "Controlled Pilot", detail: "Custom, from £250", state: "Manual approval" }
] as const;

export function SignupForm() {
  const router = useRouter();
  const [plan, setPlan] = useState("free");
  const [accepted, setAccepted] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    const email = String(form.get("email") || "").trim().toLowerCase();
    const password = String(form.get("password") || "");
    if (name.length < 2 || !email.includes("@") || password.length < 10 || !accepted) {
      setMessage("Complete every field, use at least 10 password characters, and accept the MVP boundary.");
      return;
    }
    setBusy(true);
    setMessage("Creating account and recording local/test verification...");
    try {
      const response = await fetch("/api/self-serve/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password, plan })
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: { message?: string; code?: string };
      };
      if (!response.ok) {
        setMessage(
          payload.error?.message ||
            "Hosted self-serve activation is not available yet. The backend may still need its V0.94 deployment."
        );
        return;
      }
      setMessage("Workspace active. Opening your dashboard...");
      router.push("/dashboard");
    } catch {
      setMessage("The hosted backend could not be reached. No account or API key was created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mt-10 space-y-6" onSubmit={submit}>
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Name" name="name" placeholder="Your name" />
        <Field label="Email" name="email" placeholder="you@company.com" type="email" />
      </div>
      <Field label="Password" name="password" placeholder="At least 10 characters" type="password" />
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
      <label className="flex items-start gap-3 border-t border-white/[0.08] pt-5 text-sm leading-6 text-mist/58">
        <input
          checked={accepted}
          className="mt-1"
          onChange={(event) => setAccepted(event.target.checked)}
          type="checkbox"
        />
        <span>
          I understand V0.94 uses local/test verification and MVP sessions. Email delivery and payment processing are
          not connected, and API keys must stay in server-side environment variables.
        </span>
      </label>
      <button
        className="silver-button px-7 py-4 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40"
        disabled={busy}
        type="submit"
      >
        {busy ? "Activating..." : "Activate workspace"}
      </button>
      <p aria-live="polite" className="text-sm text-mist/48">{message}</p>
    </form>
  );
}

function Field({
  label,
  name,
  placeholder,
  type = "text"
}: {
  label: string;
  name: string;
  placeholder: string;
  type?: string;
}) {
  return (
    <label>
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/48">{label}</span>
      <input className="field-input mt-2" name={name} placeholder={placeholder} required type={type} />
    </label>
  );
}
