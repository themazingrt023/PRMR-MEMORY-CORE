"use client";

import { useMemo, useState } from "react";

export type ReviewStatus =
  | "pending_review"
  | "needs_followup"
  | "approved_for_synthetic_demo"
  | "rejected_not_fit"
  | "archived";

export type ReviewerIdentity = "founder" | "technical_reviewer" | "safety_reviewer" | "notes_only";

export type AlphaReviewRequest = {
  request_id: string;
  received_at: string;
  status: ReviewStatus;
  name: string;
  email: string;
  organisation: string;
  role: string;
  use_case_category: string;
  use_case_description: string;
  data_type_planned: string;
  confirmations: {
    no_real_sensitive_data_without_approval: boolean;
    understands_alpha_boundary: boolean;
  };
  reviewer_identity: ReviewerIdentity;
  reviewer_notes: string;
  draft_response: string;
  review_history_count: number;
  review_history: Array<{
    timestamp?: string;
    action?: string;
    from_status?: string;
    to_status?: string;
    reviewer_identity?: string;
    reviewer_notes?: string;
  }>;
  updated_at?: string;
};

type SortMode = "created_timestamp" | "status" | "use_case_category" | "most_recently_reviewed";
type ReviewAction = "status_update" | "reset_status";
type ExportKind = "public_safe_json" | "private_local_json" | "markdown_summary";
type PendingConfirmation = {
  requestId: string;
  newStatus: ReviewStatus;
  action: ReviewAction;
  label: string;
} | null;

const statuses: ReviewStatus[] = [
  "pending_review",
  "needs_followup",
  "approved_for_synthetic_demo",
  "rejected_not_fit",
  "archived"
];

const reviewerIdentities: ReviewerIdentity[] = ["founder", "technical_reviewer", "safety_reviewer", "notes_only"];

const statusLabels: Record<ReviewStatus, string> = {
  pending_review: "Pending review",
  needs_followup: "Needs follow-up",
  approved_for_synthetic_demo: "Synthetic demo review",
  rejected_not_fit: "Not fit",
  archived: "Archived"
};

const reviewerLabels: Record<ReviewerIdentity, string> = {
  founder: "Founder",
  technical_reviewer: "Technical reviewer",
  safety_reviewer: "Safety reviewer",
  notes_only: "Notes only"
};

const sortLabels: Record<SortMode, string> = {
  created_timestamp: "Created timestamp",
  status: "Status",
  use_case_category: "Use case category",
  most_recently_reviewed: "Most recently reviewed"
};

const exportPaths: Record<ExportKind, string> = {
  public_safe_json: "reports/v061/public_safe_alpha_review_export_v061.json",
  private_local_json: "reports/v061/private_local_alpha_review_export_v061.json",
  markdown_summary: "reports/v061/alpha_review_ux_export_summary_v061.md"
};

export function AlphaReviewWorkflow({ initialRequests }: { initialRequests: AlphaReviewRequest[] }) {
  const [requests, setRequests] = useState(initialRequests);
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [dataTypeFilter, setDataTypeFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("created_timestamp");
  const [reviewerIdentity, setReviewerIdentity] = useState<ReviewerIdentity>("founder");
  const [notesById, setNotesById] = useState(
    Object.fromEntries(initialRequests.map((request) => [request.request_id, request.reviewer_notes || ""]))
  );
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation>(null);
  const [confirmationText, setConfirmationText] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const categories = useMemo(() => {
    return Array.from(new Set(requests.map((request) => request.use_case_category))).sort();
  }, [requests]);

  const dataTypes = useMemo(() => {
    return Array.from(new Set(requests.map((request) => request.data_type_planned))).sort();
  }, [requests]);

  const counts = useMemo(() => {
    return statuses.map((status) => ({
      status,
      count: requests.filter((request) => request.status === status).length
    }));
  }, [requests]);

  const filteredRequests = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return requests
      .filter((request) => statusFilter === "all" || request.status === statusFilter)
      .filter((request) => categoryFilter === "all" || request.use_case_category === categoryFilter)
      .filter((request) => dataTypeFilter === "all" || request.data_type_planned === dataTypeFilter)
      .filter((request) => {
        if (!query) return true;
        return [request.organisation, request.name, request.email, request.role]
          .join(" ")
          .toLowerCase()
          .includes(query);
      })
      .sort((a, b) => {
        if (sortMode === "status") return a.status.localeCompare(b.status);
        if (sortMode === "use_case_category") return a.use_case_category.localeCompare(b.use_case_category);
        if (sortMode === "most_recently_reviewed") {
          return new Date(b.updated_at || b.received_at).getTime() - new Date(a.updated_at || a.received_at).getTime();
        }
        return new Date(b.received_at).getTime() - new Date(a.received_at).getTime();
      });
  }, [categoryFilter, dataTypeFilter, requests, searchQuery, sortMode, statusFilter]);

  function requestReviewAction(requestId: string, newStatus: ReviewStatus, action: ReviewAction) {
    const needsConfirmation = action === "reset_status" || newStatus === "rejected_not_fit" || newStatus === "archived";
    if (!needsConfirmation) {
      void submitReview(requestId, newStatus, action);
      return;
    }

    setPendingConfirmation({
      requestId,
      newStatus,
      action,
      label: action === "reset_status" ? "Reset to pending review" : statusLabels[newStatus]
    });
    setConfirmationText("");
    setMessage("Type CONFIRM to apply this local status change. This is a UI confirmation step only, not authentication.");
  }

  async function submitReview(requestId: string, newStatus: ReviewStatus, action: ReviewAction) {
    setSavingId(requestId);
    setMessage("");

    const response = await fetch("/api/alpha/review", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        action,
        request_id: requestId,
        new_status: newStatus,
        reviewer_identity: reviewerIdentity,
        reviewer_notes: notesById[requestId] || ""
      })
    });

    const result = await response.json();
    setSavingId(null);

    if (!response.ok) {
      setMessage(result?.error?.message || "Local review update failed.");
      return;
    }

    setPendingConfirmation(null);
    setConfirmationText("");

    const historyEntry = {
      timestamp: new Date().toISOString(),
      action: result.action,
      from_status: "",
      to_status: result.review_status,
      reviewer_identity: result.reviewer_identity,
      reviewer_notes: result.reviewer_notes
    };

    setRequests((current) =>
      current.map((request) =>
        request.request_id === requestId
          ? {
              ...request,
              status: result.review_status,
              reviewer_identity: result.reviewer_identity,
              reviewer_notes: result.reviewer_notes,
              draft_response: result.draft_response,
              review_history_count: result.review_history_count,
              review_history: [...request.review_history, historyEntry],
              updated_at: new Date().toISOString()
            }
          : request
      )
    );
    setMessage(
      action === "reset_status"
        ? "Request reset to pending review. History was appended, not deleted."
        : "Local review state updated. No email was sent, no API key was issued, and no access was granted."
    );
  }

  async function runManualExport(exportKind: ExportKind) {
    setMessage("");
    const response = await fetch("/api/alpha/review", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ action: "export", export_kind: exportKind })
    });
    const result = await response.json();
    if (!response.ok) {
      setMessage(result?.error?.message || "Manual export failed.");
      return;
    }
    setMessage(
      `Manual export refreshed for ${exportKind}: ${result.public_export}, ${result.private_export}, ${result.markdown_summary}. No emails, keys, or access were issued.`
    );
  }

  return (
    <div className="mt-10">
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total requests" value={requests.length} />
        <Metric label="Visible after filters" value={filteredRequests.length} />
        <Metric label="API keys issued" value={0} />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-5">
        {counts.map((item) => (
          <button
            className={`border p-4 text-left transition ${
              statusFilter === item.status
                ? "border-silver/50 bg-white/[0.06]"
                : "border-silver/12 bg-[var(--afternum-bg-panel)] hover:border-silver/34"
            }`}
            key={item.status}
            onClick={() => setStatusFilter(statusFilter === item.status ? "all" : item.status)}
            type="button"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">{statusLabels[item.status]}</p>
            <p className="mt-3 font-display text-3xl text-white">{item.count}</p>
          </button>
        ))}
      </div>

      <div className="mt-6 rounded-none border border-silver/14 bg-[var(--afternum-bg-panel)] p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/58">Local admin safety notice</p>
        <p className="mt-3 text-sm leading-7 text-mist/64">
          This is a local review console only. It does not grant live access, issue API keys, send emails, process
          billing, or create hosted onboarding.
        </p>
        <p className="mt-3 text-xs leading-6 text-mist/48">
          Current console state is local file-based review only. A future hosted admin would need authentication,
          database storage, permissions, audit logs, encryption, deployment security, backup strategy, and operational
          monitoring. V0.61 does not provide those hosted-admin capabilities.
        </p>
      </div>

      <div className="mt-5 grid gap-4 border border-silver/12 bg-[var(--afternum-bg-panel)] p-5 lg:grid-cols-4">
        <div className="lg:col-span-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/58">Review controls</p>
          <p className="mt-2 text-xs leading-6 text-mist/48">
            Reviewer identity values are local metadata labels only. They are not login, authentication, permissions, or
            hosted admin roles.
          </p>
        </div>
        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Status filter</span>
          <select
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setStatusFilter(event.target.value as ReviewStatus | "all")}
            value={statusFilter}
          >
            <option value="all">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Category filter</span>
          <select
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setCategoryFilter(event.target.value)}
            value={categoryFilter}
          >
            <option value="all">All categories</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Planned data filter</span>
          <select
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setDataTypeFilter(event.target.value)}
            value={dataTypeFilter}
          >
            <option value="all">All planned data</option>
            {dataTypes.map((dataType) => (
              <option key={dataType} value={dataType}>
                {dataType}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Sort by</span>
          <select
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            value={sortMode}
          >
            {(Object.keys(sortLabels) as SortMode[]).map((mode) => (
              <option key={mode} value={mode}>
                {sortLabels[mode]}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-2 lg:col-span-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">
            Search organisation / project / name / email
          </span>
          <input
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search local request queue"
            value={searchQuery}
          />
        </label>

        <label className="grid gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">
            Reviewer identity placeholder
          </span>
          <select
            className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
            onChange={(event) => setReviewerIdentity(event.target.value as ReviewerIdentity)}
            value={reviewerIdentity}
          >
            {reviewerIdentities.map((identity) => (
              <option key={identity} value={identity}>
                {reviewerLabels[identity]}
              </option>
            ))}
          </select>
        </label>

        <div className="grid gap-2 lg:col-span-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">Manual export area</p>
          <div className="grid gap-3 md:grid-cols-3">
            {(Object.keys(exportPaths) as ExportKind[]).map((kind) => (
              <button
                className="border border-silver/18 px-4 py-3 text-left transition hover:border-silver/44"
                key={kind}
                onClick={() => runManualExport(kind)}
                type="button"
              >
                <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-mist/72">
                  {kind.replaceAll("_", " ")}
                </span>
                <span className="mt-2 block break-words text-xs leading-5 text-mist/42">{exportPaths[kind]}</span>
              </button>
            ))}
          </div>
          <p className="text-xs leading-6 text-mist/42">
            Export buttons refresh local files only. Public export excludes full personal request details; private export
            stays local.
          </p>
        </div>
      </div>

      {pendingConfirmation ? (
        <div className="mt-5 border border-silver/24 bg-white/[0.04] p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/68">Local confirmation required</p>
          <p className="mt-3 text-sm leading-7 text-mist/64">
            Confirm `{pendingConfirmation.label}` for request `{pendingConfirmation.requestId}`. This does not grant
            access, issue an API key, or send a message.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <input
              className="border border-silver/14 bg-black/30 px-3 py-3 text-sm text-mist outline-none focus:border-silver/42"
              onChange={(event) => setConfirmationText(event.target.value)}
              placeholder="Type CONFIRM"
              value={confirmationText}
            />
            <button
              className="border border-silver/18 px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-mist/72 transition hover:border-silver/44 hover:text-white disabled:opacity-40"
              disabled={confirmationText !== "CONFIRM" || savingId === pendingConfirmation.requestId}
              onClick={() =>
                submitReview(pendingConfirmation.requestId, pendingConfirmation.newStatus, pendingConfirmation.action)
              }
              type="button"
            >
              Confirm local change
            </button>
            <button
              className="border border-silver/12 px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-mist/54 transition hover:border-silver/34 hover:text-white"
              onClick={() => {
                setPendingConfirmation(null);
                setConfirmationText("");
                setMessage("");
              }}
              type="button"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {message ? (
        <div className="mt-5 border border-silver/16 bg-white/[0.03] p-4 text-sm leading-6 text-mist/70">{message}</div>
      ) : null}

      <div className="mt-8 grid gap-5">
        {filteredRequests.length ? (
          filteredRequests.map((request) => (
            <article className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-5" key={request.request_id}>
              <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
                <div>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h2 className="font-display text-3xl text-white">{request.organisation}</h2>
                      <p className="mt-2 text-sm leading-6 text-mist/54">{request.use_case_category}</p>
                    </div>
                      <span className="w-fit border border-silver/28 bg-white/[0.04] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-silver/78 shadow-[0_0_24px_rgba(255,255,255,0.04)]">
                      {statusLabels[request.status]}
                    </span>
                  </div>

                  <dl className="mt-5 grid gap-4 text-sm leading-6 text-mist/66 md:grid-cols-2">
                    <Info label="Request ID" value={request.request_id} />
                    <Info label="Created" value={request.received_at} />
                    <Info label="Most recently reviewed" value={request.updated_at || "Not reviewed yet"} />
                    <Info label="Reviewer identity" value={reviewerLabels[request.reviewer_identity]} />
                    <Info label="Name" value={request.name} />
                    <Info label="Email" value={request.email} />
                    <Info label="Role" value={request.role} />
                    <Info label="Planned data" value={request.data_type_planned} />
                    <Info
                      label="Boundary confirmations"
                      value={
                        request.confirmations.no_real_sensitive_data_without_approval &&
                        request.confirmations.understands_alpha_boundary
                          ? "Confirmed"
                          : "Needs manual check"
                      }
                    />
                  </dl>

                  <p className="mt-5 text-sm leading-7 text-mist/58">{request.use_case_description}</p>

                  <div className="mt-5 border border-silver/10 bg-white/[0.02] p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">History timeline</p>
                    {request.review_history.length ? (
                      <div className="mt-3 grid gap-3">
                        {request.review_history.slice(-4).map((entry, index) => (
                          <div className="border-l border-silver/18 pl-3 text-xs leading-5 text-mist/50" key={`${entry.timestamp}-${index}`}>
                            <p className="font-mono uppercase tracking-[0.12em] text-silver/50">
                              {entry.action || "status_update"} / {entry.to_status || request.status}
                            </p>
                            <p>{entry.timestamp || "local timestamp unavailable"}</p>
                            <p>{entry.reviewer_identity || "notes_only"}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-mist/48">No local review history yet.</p>
                    )}
                  </div>
                </div>

                <div className="border border-silver/10 bg-black/20 p-4">
                  <label
                    className="font-mono text-[11px] uppercase tracking-[0.16em] text-silver/54"
                    htmlFor={`notes-${request.request_id}`}
                  >
                    Reviewer notes
                  </label>
                  <textarea
                    className="mt-3 min-h-28 w-full resize-y border border-silver/14 bg-black/30 p-3 text-sm leading-6 text-mist outline-none transition focus:border-silver/42"
                    id={`notes-${request.request_id}`}
                    onChange={(event) =>
                      setNotesById((current) => ({ ...current, [request.request_id]: event.target.value }))
                    }
                    placeholder="Local founder/team notes. These are not emailed."
                    value={notesById[request.request_id] || ""}
                  />

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {statuses.map((status) => (
                      <button
                        className="border border-silver/16 px-3 py-3 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/68 transition hover:border-silver/44 hover:text-white disabled:opacity-50"
                        disabled={savingId === request.request_id}
                        key={status}
                        onClick={() => requestReviewAction(request.request_id, status, "status_update")}
                        type="button"
                      >
                        {statusLabels[status]}
                      </button>
                    ))}
                  </div>

                  <button
                    className="mt-3 w-full border border-silver/16 px-3 py-3 font-mono text-[10px] uppercase tracking-[0.12em] text-mist/68 transition hover:border-silver/44 hover:text-white disabled:opacity-50"
                    disabled={savingId === request.request_id}
                    onClick={() => requestReviewAction(request.request_id, "pending_review", "reset_status")}
                    type="button"
                  >
                    Reset to pending review
                  </button>

                  <div className="mt-5 border border-silver/10 bg-white/[0.02] p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/48">
                      Draft response preview
                    </p>
                    <p className="mt-3 text-sm leading-6 text-mist/62">
                      {request.draft_response || "Choose a local review status to generate a draft response."}
                    </p>
                    <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/36">
                      Review history entries: {request.review_history_count}
                    </p>
                  </div>
                </div>
              </div>
            </article>
          ))
        ) : (
          <div className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6 text-sm leading-7 text-mist/58">
            No local alpha requests match the current filters.
          </div>
        )}
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

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-[0.16em] text-silver/40">{label}</dt>
      <dd className="mt-1 break-words text-mist/68">{value}</dd>
    </div>
  );
}
