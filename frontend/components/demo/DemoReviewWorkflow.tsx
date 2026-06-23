"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";

export type DemoReviewStatus =
  | "pending_demo_review"
  | "needs_followup"
  | "demo_approved"
  | "demo_declined"
  | "demo_scheduled_manually"
  | "demo_completed"
  | "archived";

export type DemoReviewRequest = {
  demo_request_id: string;
  received_at: string;
  status: DemoReviewStatus;
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
  confirmations: {
    understands_controlled_demo_only: boolean;
    no_sensitive_data_without_approval: boolean;
  };
  reviewer_notes: string;
  manual_scheduling_notes: string;
  proposed_demo_slot: string;
  draft_response: string;
  review_history_count: number;
  updated_at?: string;
};

type SortMode = "created_timestamp" | "preferred_date" | "status" | "use_case_category" | "most_recently_reviewed";

const statuses: DemoReviewStatus[] = [
  "pending_demo_review",
  "needs_followup",
  "demo_approved",
  "demo_declined",
  "demo_scheduled_manually",
  "demo_completed",
  "archived"
];

const statusLabels: Record<DemoReviewStatus, string> = {
  pending_demo_review: "Pending review",
  needs_followup: "Needs follow-up",
  demo_approved: "Approved",
  demo_declined: "Declined",
  demo_scheduled_manually: "Scheduled manually",
  demo_completed: "Completed",
  archived: "Archived"
};

const sortLabels: Record<SortMode, string> = {
  created_timestamp: "Created timestamp",
  preferred_date: "Preferred date",
  status: "Status",
  use_case_category: "Use case category",
  most_recently_reviewed: "Most recently reviewed"
};

export function DemoReviewWorkflow({ initialRequests }: { initialRequests: DemoReviewRequest[] }) {
  const [requests, setRequests] = useState(initialRequests);
  const [statusFilter, setStatusFilter] = useState<DemoReviewStatus | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [timezoneFilter, setTimezoneFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("created_timestamp");
  const [reviewerNotes, setReviewerNotes] = useState(Object.fromEntries(initialRequests.map((item) => [item.demo_request_id, item.reviewer_notes || ""])));
  const [schedulingNotes, setSchedulingNotes] = useState(Object.fromEntries(initialRequests.map((item) => [item.demo_request_id, item.manual_scheduling_notes || ""])));
  const [proposedSlots, setProposedSlots] = useState(Object.fromEntries(initialRequests.map((item) => [item.demo_request_id, item.proposed_demo_slot || ""])));
  const [savingId, setSavingId] = useState("");
  const [message, setMessage] = useState("");

  const categories = useMemo(() => Array.from(new Set(requests.map((item) => item.use_case_category))).sort(), [requests]);
  const timezones = useMemo(() => Array.from(new Set(requests.map((item) => item.timezone))).sort(), [requests]);
  const counts = useMemo(() => statuses.map((status) => ({ status, count: requests.filter((item) => item.status === status).length })), [requests]);

  const filteredRequests = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return requests
      .filter((item) => statusFilter === "all" || item.status === statusFilter)
      .filter((item) => categoryFilter === "all" || item.use_case_category === categoryFilter)
      .filter((item) => timezoneFilter === "all" || item.timezone === timezoneFilter)
      .filter((item) => {
        if (!query) return true;
        return [item.name, item.email, item.organisation, item.role].join(" ").toLowerCase().includes(query);
      })
      .sort((a, b) => {
        if (sortMode === "preferred_date") return a.preferred_date.localeCompare(b.preferred_date);
        if (sortMode === "status") return a.status.localeCompare(b.status);
        if (sortMode === "use_case_category") return a.use_case_category.localeCompare(b.use_case_category);
        if (sortMode === "most_recently_reviewed") {
          return new Date(b.updated_at || b.received_at).getTime() - new Date(a.updated_at || a.received_at).getTime();
        }
        return new Date(b.received_at).getTime() - new Date(a.received_at).getTime();
      });
  }, [categoryFilter, requests, searchQuery, sortMode, statusFilter, timezoneFilter]);

  async function updateReview(requestId: string, newStatus: DemoReviewStatus) {
    setSavingId(requestId);
    setMessage("");

    const response = await fetch("/api/demo/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        demo_request_id: requestId,
        new_status: newStatus,
        reviewer_notes: reviewerNotes[requestId] || "",
        manual_scheduling_notes: schedulingNotes[requestId] || "",
        proposed_demo_slot: proposedSlots[requestId] || ""
      })
    });
    const result = await response.json();
    setSavingId("");

    if (!response.ok) {
      setMessage(result?.error?.message || "Local demo review update failed.");
      return;
    }

    setRequests((current) =>
      current.map((item) =>
        item.demo_request_id === requestId
          ? {
              ...item,
              status: result.demo_review_status,
              reviewer_notes: result.reviewer_notes,
              manual_scheduling_notes: result.manual_scheduling_notes,
              proposed_demo_slot: result.proposed_demo_slot,
              draft_response: result.draft_response,
              review_history_count: result.review_history_count,
              updated_at: new Date().toISOString()
            }
          : item
      )
    );
    setMessage("Local demo review updated. No calendar event, email, API key, live access, or billing action was created.");
  }

  return (
    <div className="mt-10">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total demo requests" value={requests.length} />
        <Metric label="Visible after filters" value={filteredRequests.length} />
        <Metric label="Calendar events created" value={0} />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-7">
        {counts.map((item) => (
          <button
            className={`border p-4 text-left transition ${
              statusFilter === item.status ? "border-silver/50 bg-white/[0.06]" : "border-silver/12 bg-[var(--afternum-bg-panel)] hover:border-silver/34"
            }`}
            key={item.status}
            onClick={() => setStatusFilter(statusFilter === item.status ? "all" : item.status)}
            type="button"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-silver/50">{statusLabels[item.status]}</p>
            <p className="mt-3 font-display text-3xl text-white">{item.count}</p>
          </button>
        ))}
      </div>

      <div className="mt-6 border border-silver/14 bg-[var(--afternum-bg-panel)] p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/58">Local demo review safety notice</p>
        <p className="mt-3 text-sm leading-7 text-mist/64">
          This is a local demo review workflow only. It does not create calendar events, send emails, grant live access,
          issue API keys, process billing, or create hosted onboarding.
        </p>
      </div>

      <div className="mt-5 grid gap-4 border border-silver/12 bg-[var(--afternum-bg-panel)] p-5 lg:grid-cols-5">
        <FilterSelect label="Status" value={statusFilter} onChange={(value) => setStatusFilter(value as DemoReviewStatus | "all")}>
          <option value="all">All statuses</option>
          {statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
        </FilterSelect>
        <FilterSelect label="Use case category" value={categoryFilter} onChange={setCategoryFilter}>
          <option value="all">All categories</option>
          {categories.map((category) => <option key={category} value={category}>{category}</option>)}
        </FilterSelect>
        <FilterSelect label="Timezone" value={timezoneFilter} onChange={setTimezoneFilter}>
          <option value="all">All timezones</option>
          {timezones.map((timezone) => <option key={timezone} value={timezone}>{timezone}</option>)}
        </FilterSelect>
        <FilterSelect label="Sort by" value={sortMode} onChange={(value) => setSortMode(value as SortMode)}>
          {(Object.keys(sortLabels) as SortMode[]).map((mode) => <option key={mode} value={mode}>{sortLabels[mode]}</option>)}
        </FilterSelect>
        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Search name / email / organisation</span>
          <input className="field-input" onChange={(event) => setSearchQuery(event.target.value)} value={searchQuery} />
        </label>
      </div>

      {message ? <div className="mt-5 border border-silver/16 bg-white/[0.03] p-4 text-sm leading-6 text-mist/70">{message}</div> : null}

      <div className="mt-8 grid gap-5">
        {filteredRequests.map((request) => (
          <article className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-5" key={request.demo_request_id}>
            <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
              <div>
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h2 className="font-display text-3xl text-white">{request.organisation}</h2>
                    <p className="mt-2 text-sm leading-6 text-mist/54">{request.use_case_category}</p>
                  </div>
                  <span className="w-fit border border-silver/28 bg-white/[0.04] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-silver/78">
                    {statusLabels[request.status]}
                  </span>
                </div>
                <dl className="mt-5 grid gap-4 text-sm leading-6 text-mist/66 md:grid-cols-2">
                  <Info label="Request ID" value={request.demo_request_id} />
                  <Info label="Name / email" value={`${request.name} / ${request.email}`} />
                  <Info label="Role" value={request.role} />
                  <Info label="Preferred date" value={request.preferred_date} />
                  <Info label="Preferred time window" value={request.preferred_time_window} />
                  <Info label="Timezone" value={request.timezone} />
                  <Info label="Current status" value={statusLabels[request.status]} />
                  <Info label="Review history count" value={String(request.review_history_count)} />
                  <Info
                    label="Boundary confirmations"
                    value={request.confirmations.understands_controlled_demo_only && request.confirmations.no_sensitive_data_without_approval ? "Confirmed" : "Needs manual check"}
                  />
                </dl>
                <p className="mt-5 text-sm leading-7 text-mist/60">{request.demo_purpose}</p>
                <p className="mt-3 text-sm leading-7 text-mist/50">{request.what_they_want_to_see}</p>
                <p className="mt-3 text-xs leading-6 text-mist/42">{request.technical_background}</p>
              </div>

              <div className="border border-silver/10 bg-black/20 p-4">
                <label className="grid gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Reviewer notes</span>
                  <textarea className="field-input min-h-24 resize-y" onChange={(event) => setReviewerNotes((current) => ({ ...current, [request.demo_request_id]: event.target.value }))} value={reviewerNotes[request.demo_request_id] || ""} />
                </label>
                <label className="mt-4 grid gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Manual scheduling notes</span>
                  <textarea
                    className="field-input min-h-28 resize-y"
                    onChange={(event) => setSchedulingNotes((current) => ({ ...current, [request.demo_request_id]: event.target.value }))}
                    placeholder="Proposed date/time, platform placeholder, what to show, required preparation, demo scenario to use."
                    value={schedulingNotes[request.demo_request_id] || ""}
                  />
                </label>
                <label className="mt-4 grid gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Proposed demo slot</span>
                  <input className="field-input" onChange={(event) => setProposedSlots((current) => ({ ...current, [request.demo_request_id]: event.target.value }))} value={proposedSlots[request.demo_request_id] || ""} />
                </label>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {statuses.map((status) => (
                    <button className="border border-silver/16 px-3 py-3 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/68 transition hover:border-silver/44 hover:text-white disabled:opacity-50" disabled={savingId === request.demo_request_id} key={status} onClick={() => updateReview(request.demo_request_id, status)} type="button">
                      {statusLabels[status]}
                    </button>
                  ))}
                </div>
                <div className="mt-5 border border-silver/10 bg-white/[0.02] p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Draft response preview</p>
                  <p className="mt-3 text-sm leading-6 text-mist/62">{request.draft_response || "Choose a local demo review status to generate a draft response."}</p>
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-5">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/54">{label}</p>
      <p className="mt-3 font-display text-4xl text-white">{value}</p>
    </div>
  );
}

function FilterSelect({ children, label, onChange, value }: { children: ReactNode; label: string; onChange: (value: string) => void; value: string }) {
  return (
    <label className="grid gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">{label}</span>
      <select className="field-input" onChange={(event) => onChange(event.target.value)} value={value}>{children}</select>
    </label>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/40">{label}</dt>
      <dd className="mt-1 break-words text-mist/68">{value}</dd>
    </div>
  );
}
