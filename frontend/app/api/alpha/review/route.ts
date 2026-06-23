import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { isLocalReviewEnabled, localOnlyRouteDisabledResponse } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ReviewStatus =
  | "pending_review"
  | "needs_followup"
  | "approved_for_synthetic_demo"
  | "rejected_not_fit"
  | "archived";

type ReviewerIdentity = "founder" | "technical_reviewer" | "safety_reviewer" | "notes_only";

type StoredAlphaRequest = {
  request_id: string;
  received_at: string;
  status: string;
  name?: string;
  email?: string;
  organisation: string;
  role: string;
  use_case_category: string;
  use_case_description?: string;
  data_type_planned: string;
  confirmations?: {
    no_real_sensitive_data_without_approval?: boolean;
    understands_alpha_boundary?: boolean;
  };
};

type ReviewHistoryEntry = {
  timestamp: string;
  action: "status_update" | "reset_to_pending";
  from_status: ReviewStatus;
  to_status: ReviewStatus;
  reviewer_identity: ReviewerIdentity;
  reviewer_notes: string;
  draft_response: string;
  local_only: true;
  access_granted: false;
  api_key_issued: false;
  email_sent: false;
};

type ReviewRecord = {
  request_id: string;
  status: ReviewStatus;
  reviewer_identity: ReviewerIdentity;
  reviewer_notes: string;
  draft_response: string;
  updated_at: string;
  review_history: ReviewHistoryEntry[];
  local_only: true;
  live_access_granted: false;
  api_key_issued: false;
  email_sent: false;
};

type ReviewStore = {
  version: "0.61";
  storage_type: "local_alpha_review_ux_export_state";
  allowed_statuses: ReviewStatus[];
  reviewer_identities: ReviewerIdentity[];
  draft_response_library: Record<ReviewStatus, string>;
  filters_supported: string[];
  sorting_supported: string[];
  exports_supported: string[];
  boundary: string;
  lock_policy: string;
  automatic_access_granted: false;
  live_access_granted: false;
  api_key_issuing_enabled: false;
  email_sending_enabled: false;
  reviews: ReviewRecord[];
};

const REPO_ROOT = path.resolve(process.cwd(), "..");
const REQUESTS_PATH = path.join(REPO_ROOT, "reports", "v058", "local_alpha_requests_v058.json");
const V059_REVIEW_PATH = path.join(REPO_ROOT, "reports", "v059", "local_alpha_review_state_v059.json");
const V060_REVIEW_PATH = path.join(REPO_ROOT, "reports", "v060", "local_alpha_review_console_state_v060.json");
const REVIEW_PATH = path.join(REPO_ROOT, "reports", "v061", "local_alpha_review_ux_state_v061.json");
const SUMMARY_PATH = path.join(REPO_ROOT, "reports", "v061", "alpha_review_ux_export_summary_v061.md");
const PUBLIC_EXPORT_PATH = path.join(REPO_ROOT, "reports", "v061", "public_safe_alpha_review_export_v061.json");
const PRIVATE_EXPORT_PATH = path.join(REPO_ROOT, "reports", "v061", "private_local_alpha_review_export_v061.json");
const LOCK_PATH = path.join(REPO_ROOT, "reports", "v061", "alpha_review_write.lock");

const allowedStatuses: ReviewStatus[] = [
  "pending_review",
  "needs_followup",
  "approved_for_synthetic_demo",
  "rejected_not_fit",
  "archived"
];

const reviewerIdentities: ReviewerIdentity[] = ["founder", "technical_reviewer", "safety_reviewer", "notes_only"];

const filtersSupported = ["status", "use_case_category", "planned_data_type", "organisation_name_email_search"];
const sortingSupported = ["created_timestamp", "status", "use_case_category", "most_recently_reviewed"];
const exportsSupported = ["public_safe_review_summary_json", "private_local_review_json", "markdown_summary"];

const boundary =
  "This is a local review console only. It does not grant live access, issue API keys, send emails, process billing, or create hosted onboarding.";

const draftResponseLibrary: Record<ReviewStatus, string> = {
  pending_review:
    "Thank you for the alpha request. It remains in local review. No live access is granted, no production API access is granted, no API key is issued, and no sensitive data should be sent unless explicitly approved. The next step is founder/team review only.",
  needs_followup:
    "Thank you for the alpha request. Before review can continue, please share more detail about the intended local/synthetic evaluation and planned dataset boundaries. No live access is granted, no production API access is granted, no API key is issued, and no sensitive data should be sent unless explicitly approved. The next step is follow-up review only.",
  approved_for_synthetic_demo:
    "Thank you for the alpha request. This request may be considered for a synthetic/local demo review. No live access is granted, no production API access is granted, no API key is issued, and no sensitive data should be sent unless explicitly approved. The next step is synthetic demo review only.",
  rejected_not_fit:
    "Thank you for the alpha request. It is not a fit for the current controlled-alpha scope. No live access is granted, no production API access is granted, no API key is issued, and no sensitive data should be sent unless explicitly approved.",
  archived:
    "This request is locally archived for review records. No live access is granted, no production API access is granted, no API key is issued, no message is sent automatically, and no sensitive data should be sent unless explicitly approved."
};

function clean(value: unknown, max = 1400) {
  return String(value || "").trim().slice(0, max);
}

function isReviewStatus(value: string): value is ReviewStatus {
  return allowedStatuses.includes(value as ReviewStatus);
}

function isReviewerIdentity(value: string): value is ReviewerIdentity {
  return reviewerIdentities.includes(value as ReviewerIdentity);
}

function draftResponseFor(status: ReviewStatus, request?: StoredAlphaRequest) {
  const organisation = request?.organisation || "your project";
  return `${draftResponseLibrary[status]} Local reference: ${organisation}. This draft is not sent automatically.`;
}

function emptyStore(reviews: ReviewRecord[] = []): ReviewStore {
  return {
    version: "0.61",
    storage_type: "local_alpha_review_ux_export_state",
    allowed_statuses: allowedStatuses,
    reviewer_identities: reviewerIdentities,
    draft_response_library: draftResponseLibrary,
    filters_supported: filtersSupported,
    sorting_supported: sortingSupported,
    exports_supported: exportsSupported,
    boundary,
    lock_policy: "Simple local lock file with short retry window protects local JSON writes. This is not database locking or hosted multi-user admin security.",
    automatic_access_granted: false,
    live_access_granted: false,
    api_key_issuing_enabled: false,
    email_sending_enabled: false,
    reviews
  };
}

function statusCounts(requests: StoredAlphaRequest[], reviews: ReviewRecord[]) {
  const counts = Object.fromEntries(allowedStatuses.map((status) => [status, 0])) as Record<ReviewStatus, number>;
  const reviewById = new Map(reviews.map((review) => [review.request_id, review]));
  for (const request of requests) {
    const status = reviewById.get(request.request_id)?.status || (isReviewStatus(request.status) ? request.status : "pending_review");
    counts[status] += 1;
  }
  return counts;
}

async function readRequests(): Promise<StoredAlphaRequest[]> {
  try {
    const text = await fs.readFile(REQUESTS_PATH, "utf-8");
    const parsed = JSON.parse(text) as { requests?: StoredAlphaRequest[] };
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

function migrateV059Review(item: Partial<ReviewRecord>): ReviewRecord | null {
  if (!item.request_id || !isReviewStatus(String(item.status || ""))) return null;
  const status = item.status as ReviewStatus;
  const history = Array.isArray(item.review_history)
    ? item.review_history.map((entry) => {
        const historyEntry = entry as Partial<ReviewHistoryEntry>;
        const fromStatus = String(historyEntry.from_status || "");
        const toStatus = String(historyEntry.to_status || "");
        const historyReviewerIdentity = String(historyEntry.reviewer_identity || "");
        return {
          timestamp: String(historyEntry.timestamp || item.updated_at || new Date().toISOString()),
          action: (historyEntry.action || "status_update") as "status_update" | "reset_to_pending",
          from_status: isReviewStatus(fromStatus) ? fromStatus : "pending_review",
          to_status: isReviewStatus(toStatus) ? toStatus : status,
          reviewer_identity: isReviewerIdentity(historyReviewerIdentity) ? historyReviewerIdentity : "notes_only",
          reviewer_notes: String(historyEntry.reviewer_notes || item.reviewer_notes || ""),
          draft_response: String(historyEntry.draft_response || item.draft_response || draftResponseLibrary[status]),
          local_only: true,
          access_granted: false,
          api_key_issued: false,
          email_sent: false
        } as ReviewHistoryEntry;
      })
    : [];

  const reviewerIdentity = String(item.reviewer_identity || "");

  return {
    request_id: String(item.request_id),
    status,
    reviewer_identity: isReviewerIdentity(reviewerIdentity) ? reviewerIdentity : "notes_only",
    reviewer_notes: String(item.reviewer_notes || ""),
    draft_response: String(item.draft_response || draftResponseLibrary[status]),
    updated_at: String(item.updated_at || new Date().toISOString()),
    review_history: history,
    local_only: true,
    live_access_granted: false,
    api_key_issued: false,
    email_sent: false
  };
}

async function readReviewStore(): Promise<ReviewStore> {
  try {
    const text = await fs.readFile(REVIEW_PATH, "utf-8");
    const parsed = JSON.parse(text) as Partial<ReviewStore>;
    const reviews = Array.isArray(parsed.reviews)
      ? parsed.reviews.map((item) => migrateV059Review(item)).filter((item): item is ReviewRecord => item !== null)
      : [];
    if (reviews.length === 0) {
      const fallbackText = (await fs.readFile(V060_REVIEW_PATH, "utf-8").catch(() => "")) || (await fs.readFile(V059_REVIEW_PATH, "utf-8").catch(() => ""));
      if (fallbackText) {
        const fallbackParsed = JSON.parse(fallbackText) as { reviews?: Partial<ReviewRecord>[] };
        const fallbackReviews = Array.isArray(fallbackParsed.reviews)
          ? fallbackParsed.reviews.map((item) => migrateV059Review(item)).filter((item): item is ReviewRecord => item !== null)
          : [];
        if (fallbackReviews.length) return emptyStore(fallbackReviews);
      }
    }
    return emptyStore(reviews);
  } catch {
    try {
      const text = (await fs.readFile(V060_REVIEW_PATH, "utf-8").catch(() => "")) || (await fs.readFile(V059_REVIEW_PATH, "utf-8"));
      const parsed = JSON.parse(text) as { reviews?: Partial<ReviewRecord>[] };
      const reviews = Array.isArray(parsed.reviews)
        ? parsed.reviews.map((item) => migrateV059Review(item)).filter((item): item is ReviewRecord => item !== null)
        : [];
      return emptyStore(reviews);
    } catch {
      return emptyStore();
    }
  }
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function withLocalWriteLock<T>(operation: () => Promise<T>): Promise<T> {
  await fs.mkdir(path.dirname(LOCK_PATH), { recursive: true });
  let handle: Awaited<ReturnType<typeof fs.open>> | undefined;

  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      handle = await fs.open(LOCK_PATH, "wx");
      await handle.writeFile(
        JSON.stringify(
          {
            created_at: new Date().toISOString(),
            policy: "local_write_lock_short_retry_not_database_locking"
          },
          null,
          2
        ),
        "utf-8"
      );
      break;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "EEXIST") throw error;
      await sleep(75);
    }
  }

  if (!handle) {
    throw new Error("Local review write lock is busy. Retry the local action.");
  }

  try {
    return await operation();
  } finally {
    await handle.close();
    await fs.rm(LOCK_PATH, { force: true });
  }
}

async function writeReviewStore(store: ReviewStore) {
  await fs.mkdir(path.dirname(REVIEW_PATH), { recursive: true });
  const tempPath = `${REVIEW_PATH}.tmp`;
  await fs.writeFile(tempPath, JSON.stringify(emptyStore(store.reviews), null, 2), "utf-8");
  await fs.rename(tempPath, REVIEW_PATH);
}

function buildPublicExport(requests: StoredAlphaRequest[], store: ReviewStore) {
  return {
    version: "0.61",
    title: "Alpha Review UX + Export Public Summary",
    result_scope: "local controlled-alpha review console evidence",
    boundary,
    total_requests: requests.length,
    counts_by_status: statusCounts(requests, store.reviews),
    allowed_statuses: allowedStatuses,
    reviewer_identity_options: reviewerIdentities,
    filters_supported: filtersSupported,
    sorting_supported: sortingSupported,
    exports_supported: exportsSupported,
    access_and_delivery: {
      live_access_granted: false,
      api_keys_issued: 0,
      emails_sent: 0,
      external_services_connected: false,
      billing_processed: false,
      hosted_onboarding_created: false
    },
    local_write_policy: "V0.61 uses a simple local lock file and atomic rename for local writes. This is not a database, not hosted admin, and not full multi-user concurrency control.",
    public_privacy_boundary: "Full personal request details are excluded from this public-safe export."
  };
}

function buildPrivateExport(requests: StoredAlphaRequest[], store: ReviewStore) {
  return {
    ...buildPublicExport(requests, store),
    title: "Alpha Review Console Private Local Trace",
    request_details: requests,
    review_records: store.reviews
  };
}

async function writeExports(requests: StoredAlphaRequest[], store: ReviewStore) {
  const counts = statusCounts(requests, store.reviews);
  await fs.mkdir(path.dirname(PUBLIC_EXPORT_PATH), { recursive: true });
  await fs.writeFile(`${PUBLIC_EXPORT_PATH}.tmp`, JSON.stringify(buildPublicExport(requests, store), null, 2), "utf-8");
  await fs.rename(`${PUBLIC_EXPORT_PATH}.tmp`, PUBLIC_EXPORT_PATH);
  await fs.writeFile(`${PRIVATE_EXPORT_PATH}.tmp`, JSON.stringify(buildPrivateExport(requests, store), null, 2), "utf-8");
  await fs.rename(`${PRIVATE_EXPORT_PATH}.tmp`, PRIVATE_EXPORT_PATH);

  const markdown = `# PRMR Memory Core V0.61 Local Alpha Review UX + Export Summary

${boundary}

This summary is local controlled-alpha console evidence only. It does not grant live access, billing, production API keys, hosted onboarding, bank approval, compliance approval, legal approval, external security certification, or real-world validation.

## Local vs Future Hosted Admin Boundary

The current console is local file-based review only. Future hosted admin would need authentication, database storage, permissions, audit logs, encryption, deployment security, backup strategy, and operational monitoring. V0.61 does not provide those hosted-admin capabilities.

## Multi-Write Handling

V0.61 uses a simple local lock file plus atomic rename for local JSON writes. This reduces accidental overlapping local writes, but it is not database locking and not full multi-user hosted admin concurrency control.

## Counts

- Total local requests: ${requests.length}
- Locally reviewed requests: ${store.reviews.length}
- Automatic access granted: 0
- API keys issued: 0
- Emails sent: 0

## Status Counts

${allowedStatuses.map((status) => `- ${status}: ${counts[status]}`).join("\n")}

## Console Capabilities

- Filters: ${filtersSupported.join(", ")}
- Sorting: ${sortingSupported.join(", ")}
- Reviewer identities: ${reviewerIdentities.join(", ")}
- Manual exports: ${exportsSupported.join(", ")}
`;

  await fs.writeFile(`${SUMMARY_PATH}.tmp`, markdown, "utf-8");
  await fs.rename(`${SUMMARY_PATH}.tmp`, SUMMARY_PATH);
}

export async function GET(request: Request) {
  if (!isLocalReviewEnabled()) {
    return localOnlyRouteDisabledResponse();
  }

  const url = new URL(request.url);
  const exportMode = url.searchParams.get("export");
  const requests = await readRequests();
  const store = await readReviewStore();
  await withLocalWriteLock(async () => {
    await writeReviewStore(store);
    await writeExports(requests, store);
  });

  if (exportMode === "public") {
    return NextResponse.json(buildPublicExport(requests, store));
  }

  if (exportMode === "private") {
    return NextResponse.json(buildPrivateExport(requests, store));
  }

  return NextResponse.json({
    status: "ok",
    allowed_statuses: allowedStatuses,
    reviewer_identities: reviewerIdentities,
    draft_response_library: draftResponseLibrary,
    filters_supported: filtersSupported,
    sorting_supported: sortingSupported,
    exports_supported: exportsSupported,
    boundary,
    automatic_access_granted: false,
    live_access_granted: false,
    api_key_issued: false,
    email_sent: false,
    total_requests: requests.length,
    reviews: store.reviews
  });
}

export async function POST(request: Request) {
  if (!isLocalReviewEnabled()) {
    return localOnlyRouteDisabledResponse();
  }

  const body = (await request.json().catch(() => ({}))) as {
    action?: string;
    request_id?: string;
    new_status?: string;
    reviewer_notes?: string;
    reviewer_identity?: string;
  };

  const action = clean(body.action || "status_update", 60);
  const requestId = clean(body.request_id, 140);
  const requestedStatus = action === "reset_status" ? "pending_review" : clean(body.new_status, 80);
  const reviewerNotes = clean(body.reviewer_notes, 1400);
  const reviewerIdentity = clean(body.reviewer_identity || "notes_only", 80);

  if (action === "export") {
    const requests = await readRequests();
    const store = await readReviewStore();
    await withLocalWriteLock(async () => {
      await writeReviewStore(store);
      await writeExports(requests, store);
    });
    return NextResponse.json({
      status: "ok",
      action: "export",
      public_export: "reports/v061/public_safe_alpha_review_export_v061.json",
      private_export: "reports/v061/private_local_alpha_review_export_v061.json",
      markdown_summary: "reports/v061/alpha_review_ux_export_summary_v061.md",
      lock_policy: "simple local lock file with retry; not database locking",
      automatic_access_granted: false,
      api_key_issued: false,
      email_sent: false,
      boundary
    });
  }

  if (!requestId || !requestedStatus) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "validation_failed",
          message: "request_id and new_status are required for local review updates."
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!isReviewStatus(requestedStatus)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_review_status",
          message: "Use one of the allowed local review statuses.",
          allowed_statuses: allowedStatuses
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!isReviewerIdentity(reviewerIdentity)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_reviewer_identity",
          message: "Use one of the local reviewer identity placeholders.",
          reviewer_identities: reviewerIdentities
        },
        boundary
      },
      { status: 400 }
    );
  }

  const requests = await readRequests();
  const alphaRequest = requests.find((item) => item.request_id === requestId);

  if (!alphaRequest) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "request_not_found",
          message: "No local alpha request exists for that request_id."
        },
        boundary
      },
      { status: 404 }
    );
  }

  const store = await readReviewStore();
  const existingIndex = store.reviews.findIndex((item) => item.request_id === requestId);
  const existing = existingIndex >= 0 ? store.reviews[existingIndex] : undefined;
  const previousStatus = existing?.status || (isReviewStatus(alphaRequest.status) ? alphaRequest.status : "pending_review");
  const nextStatus = requestedStatus;
  const now = new Date().toISOString();
  const draftResponse = draftResponseFor(nextStatus, alphaRequest);
  const historyEntry: ReviewHistoryEntry = {
    timestamp: now,
    action: action === "reset_status" ? "reset_to_pending" : "status_update",
    from_status: previousStatus,
    to_status: nextStatus,
    reviewer_identity: reviewerIdentity,
    reviewer_notes: reviewerNotes,
    draft_response: draftResponse,
    local_only: true,
    access_granted: false,
    api_key_issued: false,
    email_sent: false
  };

  const nextRecord: ReviewRecord = {
    request_id: requestId,
    status: nextStatus,
    reviewer_identity: reviewerIdentity,
    reviewer_notes: reviewerNotes,
    draft_response: draftResponse,
    updated_at: now,
    review_history: [...(existing?.review_history || []), historyEntry],
    local_only: true,
    live_access_granted: false,
    api_key_issued: false,
    email_sent: false
  };

  const nextReviews = [...store.reviews];
  if (existingIndex >= 0) {
    nextReviews[existingIndex] = nextRecord;
  } else {
    nextReviews.push(nextRecord);
  }

  const nextStore = emptyStore(nextReviews);
  await withLocalWriteLock(async () => {
    await writeReviewStore(nextStore);
    await writeExports(requests, nextStore);
  });

  return NextResponse.json({
    status: "ok",
    action: historyEntry.action,
    request_id: requestId,
    review_status: nextStatus,
    reviewer_identity: reviewerIdentity,
    reviewer_notes: reviewerNotes,
    draft_response: draftResponse,
    review_history_count: nextRecord.review_history.length,
    reset_appended_history: historyEntry.action === "reset_to_pending",
    local_only: true,
    no_live_service_access_granted: true,
    automatic_access_granted: false,
    api_key_issued: false,
    email_sent: false,
    lock_policy: "simple local lock file with retry; not database locking",
    boundary
  });
}
