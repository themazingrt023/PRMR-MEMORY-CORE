"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createSupabaseBrowserClient,
  supabaseBrowserConfigured
} from "@/lib/supabaseClient";

export function LoginForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("verified") === "1") {
      setMessage("Email verified. Sign in to continue.");
    } else if (params.get("error") === "auth_callback_failed") {
      setMessage("We could not complete email verification. Please sign in or request a new verification email.");
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim().toLowerCase();
    const password = String(form.get("password") || "");
    if (!supabaseBrowserConfigured()) {
      setMessage("Account sign-in is temporarily unavailable. Please try again shortly.");
      return;
    }
    setBusy(true);
    setMessage("Signing in...");
    try {
      const supabase = createSupabaseBrowserClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      });
      if (error) {
        setMessage(
          error.message.toLowerCase().includes("confirm")
            ? "Verify your email before signing in."
            : "We could not sign you in. Check your email and password, then try again."
        );
        return;
      }
      if (!data.user?.email_confirmed_at) {
        await supabase.auth.signOut();
        setMessage("Verify your email before signing in.");
        return;
      }
      router.push("/start");
    } catch {
      setMessage("We could not reach the account service. Please try again in a moment.");
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
      <p aria-live="polite" className="text-sm text-mist/48">{message}</p>
    </form>
  );
}
