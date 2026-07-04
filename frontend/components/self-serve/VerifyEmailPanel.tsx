"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  createSupabaseBrowserClient,
  supabaseBrowserConfigured
} from "@/lib/supabaseClient";

export function VerifyEmailPanel() {
  const emailInput = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState(
    "Use the verification link we sent to your inbox."
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (emailInput.current) {
      emailInput.current.value =
        sessionStorage.getItem("prmr-pending-verification-email") || "";
    }
  }, []);

  async function resend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim().toLowerCase();
    if (!supabaseBrowserConfigured()) {
      setMessage("Email verification is temporarily unavailable. Please try again shortly.");
      return;
    }
    if (!email.includes("@")) {
      setMessage("Enter the email address used during signup.");
      return;
    }
    setBusy(true);
    const supabase = createSupabaseBrowserClient();
    const { error } = await supabase.auth.resend({
      type: "signup",
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/start`
      }
    });
    setMessage(
      error
        ? "We could not resend the verification email. Please wait a moment and try again."
        : "Verification email requested. Check your inbox and spam folder."
    );
    setBusy(false);
  }

  return (
    <div className="mt-10 max-w-2xl border border-white/10 bg-white/[0.015] p-6">
      <p className="text-sm leading-6 text-mist/62">
        PRMR will not provision a client scope or permit API-key creation until
        your email is verified and your account session is active.
      </p>
      <form className="mt-6 flex flex-col gap-3 sm:flex-row" onSubmit={resend}>
        <input
          className="field-input"
          name="email"
          placeholder="developer@example.com"
          ref={emailInput}
          type="email"
        />
        <button
          className="ghost-button shrink-0 px-5 py-3 font-mono text-xs uppercase disabled:opacity-40"
          disabled={busy}
          type="submit"
        >
          {busy ? "Requesting..." : "Resend confirmation"}
        </button>
      </form>
      <p aria-live="polite" className="mt-4 text-sm text-mist/48">
        {message}
      </p>
      <Link className="mt-5 inline-block text-sm text-white/70 underline" href="/login">
        Return to login
      </Link>
    </div>
  );
}
