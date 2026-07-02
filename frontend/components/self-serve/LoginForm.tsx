"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function LoginForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setMessage("Checking your hosted session...");
    try {
      const response = await fetch("/api/self-serve/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(form.get("email") || ""),
          password: String(form.get("password") || "")
        })
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: { message?: string };
      };
      if (!response.ok) {
        setMessage(
          payload.error?.message ||
            "Hosted login is unavailable. The V0.94 Render deployment may not be active yet."
        );
        return;
      }
      router.push("/dashboard");
    } catch {
      setMessage("The hosted login service could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mt-10 max-w-2xl space-y-5" onSubmit={submit}>
      <label className="block">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/48">Email</span>
        <input className="field-input mt-2" name="email" placeholder="you@company.com" required type="email" />
      </label>
      <label className="block">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/48">Password</span>
        <input className="field-input mt-2" minLength={10} name="password" placeholder="Your password" required type="password" />
      </label>
      <button className="silver-button px-6 py-4 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40" disabled={busy} type="submit">
        {busy ? "Signing in..." : "Sign in"}
      </button>
      <p className="text-sm text-mist/48">{message}</p>
    </form>
  );
}
