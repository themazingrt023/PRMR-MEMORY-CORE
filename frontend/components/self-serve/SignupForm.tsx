"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createSupabaseBrowserClient,
  supabaseBrowserConfigured
} from "@/lib/supabaseClient";

export function SignupForm() {
  const router = useRouter();
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
      setMessage("Complete every field, use at least 10 password characters, and accept the alpha boundary.");
      return;
    }
    if (!supabaseBrowserConfigured()) {
      setMessage("Account creation is temporarily unavailable. Please try again shortly.");
      return;
    }
    setBusy(true);
    setMessage("Creating your PRMR account...");
    try {
      const supabase = createSupabaseBrowserClient();
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { display_name: name },
          emailRedirectTo: `${window.location.origin}/auth/callback?next=/start`
        }
      });
      if (error) {
        setMessage(error.message);
        return;
      }
      if (data.session && data.user?.email_confirmed_at) {
        router.push("/start?confirmed=1");
        return;
      }
      sessionStorage.setItem("prmr-pending-verification-email", email);
      setMessage("Check your email to verify your PRMR account.");
      router.push("/verify-email");
    } catch {
      setMessage("We could not reach the account service. No workspace or API key was created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mt-10 space-y-6" onSubmit={submit}>
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Name" name="name" placeholder="Your name" />
        <Field label="Email" name="email" placeholder="developer@example.com" type="email" />
      </div>
      <Field label="Password" name="password" placeholder="At least 10 characters" type="password" />
      <label className="flex items-start gap-3 border-t border-white/[0.08] pt-5 text-sm leading-6 text-mist/58">
        <input
          checked={accepted}
          className="mt-1"
          onChange={(event) => setAccepted(event.target.checked)}
          type="checkbox"
        />
        <span>
          I understand PRMR API keys must stay server-side. Billing is not
          connected yet.
        </span>
      </label>
      <button
        className="silver-button px-7 py-4 font-mono text-xs uppercase tracking-[0.14em] disabled:opacity-40"
        disabled={busy}
        type="submit"
      >
        {busy ? "Creating account..." : "Create account"}
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
