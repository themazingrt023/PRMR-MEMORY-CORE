"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { LabFrame } from "@/components/visual/LabFrame";

const categories = [
  "AI agent memory",
  "Customer support continuity",
  "SaaS user-history continuity",
  "Education progress continuity",
  "Legal/research case continuity",
  "Fraud/risk sandbox evaluation",
  "Company knowledge continuity",
  "Other"
];

type FormState = {
  name: string;
  email: string;
  organisation: string;
  role: string;
  use_case_category: string;
  use_case_description: string;
  data_type_planned: string;
  confirm_no_sensitive_data: boolean;
  confirm_alpha_boundary: boolean;
};

type Submission = {
  request_id: string;
  review_status: string;
  message: string;
  next_step: string;
  no_live_service_access_granted: boolean;
};

const initialState: FormState = {
  name: "",
  email: "",
  organisation: "",
  role: "",
  use_case_category: categories[0],
  use_case_description: "",
  data_type_planned: "",
  confirm_no_sensitive_data: false,
  confirm_alpha_boundary: false
};

export function RequestAccessForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<Submission | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSubmission(null);

    try {
      const response = await fetch("/api/alpha/request", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(form)
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") {
        throw new Error(payload.error?.message || "Alpha request could not be saved locally.");
      }
      setSubmission(payload);
      setForm(initialState);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Alpha request could not be saved locally.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <LabFrame className="mt-6 p-8">
      <h2 className="font-display text-3xl text-silver">Request controlled alpha access</h2>
      <p className="mt-3 text-sm leading-7 text-mist/62">
        Submissions are stored locally for founder/team review. No live service access is granted by this form.
      </p>

      <form className="mt-7 grid gap-5" onSubmit={submit}>
        <div className="grid gap-5 md:grid-cols-2">
          <TextField label="Name" value={form.name} onChange={(value) => update("name", value)} required />
          <TextField label="Email" type="email" value={form.email} onChange={(value) => update("email", value)} required />
          <TextField label="Organisation / project" value={form.organisation} onChange={(value) => update("organisation", value)} required />
          <TextField label="Role" value={form.role} onChange={(value) => update("role", value)} required />
        </div>

        <label className="grid gap-2 text-sm text-mist/72">
          Use case category
          <select
            className="border border-silver/18 bg-[var(--afternum-bg-panel)] px-3 py-3 text-mist outline-none transition focus:border-silver/46"
            value={form.use_case_category}
            onChange={(event) => update("use_case_category", event.target.value)}
          >
            {categories.map((category) => (
              <option key={category}>{category}</option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 text-sm text-mist/72">
          Intended use case description
          <textarea
            className="min-h-32 resize-y border border-silver/18 bg-[var(--afternum-bg-panel)] px-3 py-3 text-mist outline-none transition focus:border-silver/46"
            onChange={(event) => update("use_case_description", event.target.value)}
            placeholder="Describe the continuity problem you want to evaluate with synthetic, anonymised, or approved data."
            required
            value={form.use_case_description}
          />
        </label>

        <label className="grid gap-2 text-sm text-mist/72">
          Data type planned
          <textarea
            className="min-h-24 resize-y border border-silver/18 bg-[var(--afternum-bg-panel)] px-3 py-3 text-mist outline-none transition focus:border-silver/46"
            onChange={(event) => update("data_type_planned", event.target.value)}
            placeholder="Example: synthetic support tickets, anonymised project events, approved demo logs."
            required
            value={form.data_type_planned}
          />
        </label>

        <Checkbox
          checked={form.confirm_no_sensitive_data}
          label="I confirm no real sensitive data will be uploaded without explicit approval."
          onChange={(checked) => update("confirm_no_sensitive_data", checked)}
        />
        <Checkbox
          checked={form.confirm_alpha_boundary}
          label="I understand this is not production or certified access, and no live service access is granted by this form."
          onChange={(checked) => update("confirm_alpha_boundary", checked)}
        />

        <button className="liquid-glass-btn w-fit" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Submitting for Review" : "Request Controlled Alpha Access"}
        </button>
      </form>

      {error ? (
        <div className="mt-6 border border-silver/18 p-4 text-sm leading-6 text-mist/70">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/58">Needs review</p>
          <p className="mt-2">{error}</p>
        </div>
      ) : null}

      {submission ? (
        <div className="mt-6 border border-silver/24 bg-white/[0.035] p-5">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/58">Request received locally</p>
          <h3 className="mt-3 font-display text-2xl text-white">Status: {submission.review_status}</h3>
          <p className="mt-3 text-sm leading-6 text-mist/70">Request ID: {submission.request_id}</p>
          <p className="mt-2 text-sm leading-6 text-mist/70">Next step: {submission.next_step}</p>
          <p className="mt-2 text-sm leading-6 text-mist/54">
            No live service access is granted by this form.
          </p>
        </div>
      ) : null}
    </LabFrame>
  );
}

function TextField({
  label,
  onChange,
  required,
  type = "text",
  value
}: {
  label: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  value: string;
}) {
  return (
    <label className="grid gap-2 text-sm text-mist/72">
      {label}
      <input
        className="border border-silver/18 bg-[var(--afternum-bg-panel)] px-3 py-3 text-mist outline-none transition focus:border-silver/46"
        onChange={(event) => onChange(event.target.value)}
        placeholder={label}
        required={required}
        type={type}
        value={value}
      />
    </label>
  );
}

function Checkbox({
  checked,
  label,
  onChange
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 text-sm leading-6 text-mist/70">
      <input
        checked={checked}
        className="mt-1"
        onChange={(event) => onChange(event.target.checked)}
        required
        type="checkbox"
      />
      {label}
    </label>
  );
}
