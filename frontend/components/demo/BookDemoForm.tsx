"use client";

import type { FormEvent, ReactNode } from "react";
import { useState } from "react";

type FormState = {
  name: string;
  email: string;
  organisation: string;
  role: string;
  use_case_category: string;
  demo_purpose: string;
  preferred_date: string;
  preferred_time_window: string;
  timezone: string;
  technical_background: string;
  what_they_want_to_see: string;
  confirm_controlled_demo_only: boolean;
  confirm_no_sensitive_data: boolean;
};

const useCaseCategories = [
  "AI agent memory",
  "Customer support continuity",
  "SaaS user-history continuity",
  "Education progress continuity",
  "Legal/research case continuity",
  "Fraud/risk sandbox evaluation",
  "Company knowledge continuity",
  "Accelerator / competition review",
  "Technical collaboration",
  "Other"
];

const initialForm: FormState = {
  name: "",
  email: "",
  organisation: "",
  role: "",
  use_case_category: useCaseCategories[0],
  demo_purpose: "",
  preferred_date: "",
  preferred_time_window: "",
  timezone: "",
  technical_background: "",
  what_they_want_to_see: "",
  confirm_controlled_demo_only: false,
  confirm_no_sensitive_data: false
};

export function BookDemoForm() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [requestId, setRequestId] = useState("");

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    setRequestId("");

    const response = await fetch("/api/demo/book", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(form)
    });
    const result = await response.json();
    setIsSubmitting(false);

    if (!response.ok) {
      setMessage(result?.error?.message || "Demo request could not be saved locally.");
      return;
    }

    setRequestId(result.demo_request_id);
    setMessage(
      "Demo request saved locally for founder/team review. No calendar event, email, API key, billing, or live access was created."
    );
    setForm(initialForm);
  }

  return (
    <section className="mx-auto max-w-6xl px-6 pb-24 pt-32">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="panel p-8">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Controlled demo request</p>
          <h1 className="mt-4 font-display text-[clamp(42px,5vw,72px)] leading-tight text-mist">
            Request a controlled PRMR Memory Core walkthrough.
          </h1>
          <p className="mt-5 text-sm leading-7 text-mist/68">
            Use this form to request a local controlled demo conversation. Demo requests are reviewed manually by the
            founder/team before any follow-up.
          </p>
          <div className="mt-6 border border-silver/14 bg-white/[0.03] p-5">
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/60">Boundary</p>
            <p className="mt-3 text-sm leading-7 text-mist/66">
              This does not grant live access, API keys, production use, or certified status. Demo requests are reviewed
              manually.
            </p>
          </div>
          <p className="mt-5 text-xs leading-6 text-mist/44">
            Do not submit real sensitive data. This form does not connect to calendars, email, CRM, payment systems, or
            external services.
          </p>
        </div>

        <form className="panel grid gap-5 p-6" onSubmit={submitRequest}>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name">
              <input
                className="field-input"
                onChange={(event) => updateField("name", event.target.value)}
                required
                value={form.name}
              />
            </Field>
            <Field label="Email">
              <input
                className="field-input"
                onChange={(event) => updateField("email", event.target.value)}
                required
                type="email"
                value={form.email}
              />
            </Field>
            <Field label="Organisation / project">
              <input
                className="field-input"
                onChange={(event) => updateField("organisation", event.target.value)}
                required
                value={form.organisation}
              />
            </Field>
            <Field label="Role">
              <input
                className="field-input"
                onChange={(event) => updateField("role", event.target.value)}
                required
                value={form.role}
              />
            </Field>
          </div>

          <Field label="Use case category">
            <select
              className="field-input"
              onChange={(event) => updateField("use_case_category", event.target.value)}
              required
              value={form.use_case_category}
            >
              {useCaseCategories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Demo purpose">
            <textarea
              className="field-input min-h-24 resize-y"
              onChange={(event) => updateField("demo_purpose", event.target.value)}
              required
              value={form.demo_purpose}
            />
          </Field>

          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Preferred date">
              <input
                className="field-input"
                onChange={(event) => updateField("preferred_date", event.target.value)}
                required
                type="date"
                value={form.preferred_date}
              />
            </Field>
            <Field label="Preferred time window">
              <input
                className="field-input"
                onChange={(event) => updateField("preferred_time_window", event.target.value)}
                placeholder="e.g. 10:00-12:00"
                required
                value={form.preferred_time_window}
              />
            </Field>
            <Field label="Timezone">
              <input
                className="field-input"
                onChange={(event) => updateField("timezone", event.target.value)}
                placeholder="e.g. Europe/London"
                required
                value={form.timezone}
              />
            </Field>
          </div>

          <Field label="Technical background">
            <textarea
              className="field-input min-h-24 resize-y"
              onChange={(event) => updateField("technical_background", event.target.value)}
              required
              value={form.technical_background}
            />
          </Field>

          <Field label="What they want to see">
            <textarea
              className="field-input min-h-24 resize-y"
              onChange={(event) => updateField("what_they_want_to_see", event.target.value)}
              required
              value={form.what_they_want_to_see}
            />
          </Field>

          <label className="flex gap-3 text-sm leading-6 text-mist/68">
            <input
              checked={form.confirm_controlled_demo_only}
              className="mt-1"
              onChange={(event) => updateField("confirm_controlled_demo_only", event.target.checked)}
              required
              type="checkbox"
            />
            I understand this is a controlled demo request only. It does not grant live access, API keys, production
            use, or certified status.
          </label>

          <label className="flex gap-3 text-sm leading-6 text-mist/68">
            <input
              checked={form.confirm_no_sensitive_data}
              className="mt-1"
              onChange={(event) => updateField("confirm_no_sensitive_data", event.target.checked)}
              required
              type="checkbox"
            />
            I will not submit real sensitive data without explicit approval.
          </label>

          <button className="liquid-glass-btn justify-center" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Saving Local Request" : "Request Demo Review"}
          </button>

          {message ? (
            <div className="border border-silver/14 bg-white/[0.03] p-4 text-sm leading-6 text-mist/70">
              <p>{message}</p>
              {requestId ? <p className="mt-2 font-mono text-xs uppercase tracking-[0.14em] text-silver/52">{requestId}</p> : null}
            </div>
          ) : null}
        </form>
      </div>
    </section>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="grid gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">{label}</span>
      {children}
    </label>
  );
}
