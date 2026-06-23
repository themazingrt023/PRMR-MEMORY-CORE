import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { isLocalReviewEnabled, localOnlyRouteDisabledResponse } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type DemoReviewStatus =
  | "pending_demo_review"
  | "needs_followup"
  | "demo_approved"
  | "demo_declined"
  | "demo_scheduled_manually"
  | "demo_completed"
  | "archived";

type DemoRequestRecord = {
  demo_request_id: string;
  received_at: string;
  status: string;
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
  confirmations?: {
    understands_controlled_demo_only?: boolean;
    no_sensitive_data_without_approval?: boolean;
  };
};

type DemoReviewHistoryEntry = {
  timestamp: string;
  from_status: DemoReviewStatus;
  to_status: DemoReviewStatus;
  reviewer_notes: string;
  manual_scheduling_notes: string;
  proposed_demo_slot: string;
  draft_response: string;
  local_only: true;
  calendar_event_created: false;
  email_sent: false;
  api_key_issued: false;
  live_access_granted: false;
  billing_connected: false;
};

type DemoReviewRecord = {
  demo_request_id: string;
  status: DemoReviewStatus;
  reviewer_notes: string;
  manual_scheduling_notes: string;
  proposed_demo_slot: string;
  draft_response: string;
  updated_at: string;
  review_history: DemoReviewHistoryEntry[];
  local_only: true;
  calendar_event_created: false;
  email_sent: false;
  api_key_issued: false;
  live_access_granted: false;
  billing_connected: false;
};

const REPO_ROOT = path.resolve(process.cwd(), "..");
const REQUESTS_PATH = path.join(REPO_ROOT, "reports", "v063", "local_demo_requests_v063.json");
const REPORT_DIR = path.join(REPO_ROOT, "reports", "v064");
const STATE_PATH = path.join(REPORT_DIR, "local_demo_review_state_v064.json");
const PUBLIC_REPORT_PATH = path.join(REPORT_DIR, "public_demo_review_flow_v064.json");
const PRIVATE_REPORT_PATH = path.join(REPORT_DIR, "private_internal_demo_review_flow_v064.json");
const SUMMARY_PATH = path.join(REPORT_DIR, "demo_review_summary_v064.md");

const boundary =
  "V0.64 is a local demo scheduling/review workflow only. It is not calendar integration, automatic email sending, hosted onboarding, billing, live API access, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.";

const demoReviewStatuses: DemoReviewStatus[] = [
  "pending_demo_review",
  "needs_followup",
  "demo_approved",
  "demo_declined",
  "demo_scheduled_manually",
  "demo_completed",
  "archived"
];

const draftResponseLibrary: Record<DemoReviewStatus, string> = {
  pending_demo_review:
    "Thank you for the demo request. It remains under local founder/team review. No live API access is granted, no API key is issued, no production access is granted, no calendar invite has been sent automatically, and no sensitive data should be shared without approval.",
  needs_followup:
    "Thank you for the demo request. More detail is needed before a controlled demo can be reviewed. No live API access is granted, no API key is issued, no production access is granted, no calendar invite has been sent automatically, and no sensitive data should be shared without approval.",
  demo_approved:
    "Thank you for the demo request. It may proceed to manual scheduling review. No live API access is granted, no API key is issued, no production access is granted, no calendar invite has been sent automatically, and no sensitive data should be shared without approval.",
  demo_declined:
    "Thank you for the demo request. It is not a fit for a controlled demo at this time. No live API access is granted, no API key is issued, no production access is granted, and no calendar invite has been sent automatically.",
  demo_scheduled_manually:
    "A controlled demo slot has been noted manually for founder/team review. No live API access is granted, no API key is issued, no production access is granted, no calendar invite has been sent automatically, and no sensitive data should be shared without approval.",
  demo_completed:
    "The controlled demo is marked complete in local review records. No live API access is granted, no API key is issued, no production access is granted, and no calendar invite or email is sent automatically by this workflow.",
  archived:
    "This demo request is archived in local review records. No live API access is granted, no API key is issued, no production access is granted, no calendar invite has been sent automatically, and no sensitive data should be shared without approval."
};

function clean(value: unknown, max = 1400) {
  return String(value || "").trim().slice(0, max);
}

function isDemoReviewStatus(value: string): value is DemoReviewStatus {
  return demoReviewStatuses.includes(value as DemoReviewStatus);
}

async function readRequests(): Promise<DemoRequestRecord[]> {
  try {
    const text = await fs.readFile(REQUESTS_PATH, "utf-8");
    const parsed = JSON.parse(text) as { requests?: DemoRequestRecord[] };
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

async function readReviewState(): Promise<DemoReviewRecord[]> {
  try {
    const text = await fs.readFile(STATE_PATH, "utf-8");
    const parsed = JSON.parse(text) as { reviews?: DemoReviewRecord[] };
    return Array.isArray(parsed.reviews) ? parsed.reviews : [];
  } catch {
    return [];
  }
}

function statusCounts(requests: DemoRequestRecord[], reviews: DemoReviewRecord[]) {
  const counts = Object.fromEntries(demoReviewStatuses.map((status) => [status, 0])) as Record<DemoReviewStatus, number>;
  const reviewById = new Map(reviews.map((review) => [review.demo_request_id, review]));
  for (const request of requests) {
    const status = reviewById.get(request.demo_request_id)?.status || (isDemoReviewStatus(request.status) ? request.status : "pending_demo_review");
    counts[status] += 1;
  }
  return counts;
}

async function writeJsonAtomic(filePath: string, value: unknown) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.tmp`;
  await fs.writeFile(tempPath, JSON.stringify(value, null, 2), "utf-8");
  await fs.rename(tempPath, filePath);
}

async function writeExports(requests: DemoRequestRecord[], reviews: DemoReviewRecord[]) {
  const publicReport = {
    version: "0.64",
    title: "Demo Scheduling / Review Flow",
    result_scope: "local manual demo review workflow evidence",
    boundary,
    total_demo_requests: requests.length,
    statuses: demoReviewStatuses,
    counts_by_status: statusCounts(requests, reviews),
    safety: {
      calendar_events_created: 0,
      emails_sent: 0,
      api_keys_issued: 0,
      live_access_granted: false,
      billing_connected: false,
      public_report_excludes_personal_details: true
    }
  };

  const privateReport = {
    ...publicReport,
    title: "Demo Scheduling / Review Flow Private Local Trace",
    request_details: requests,
    review_records: reviews
  };

  const summary = `# V0.64 Demo Scheduling / Review Flow Summary

${boundary}

This is local/manual demo review evidence only. It does not create calendar events, send emails, issue API keys, grant live access, process billing, or create hosted onboarding.

## Counts

- Total demo requests: ${requests.length}
- Local review records: ${reviews.length}

## Status Counts

${demoReviewStatuses.map((status) => `- ${status}: ${statusCounts(requests, reviews)[status]}`).join("\n")}

## Manual Scheduling Boundary

Manual scheduling notes may include proposed date/time, platform placeholder, what to show, required preparation, and demo scenario. These notes do not create a real meeting.
`;

  await writeJsonAtomic(PUBLIC_REPORT_PATH, publicReport);
  await writeJsonAtomic(PRIVATE_REPORT_PATH, privateReport);
  await fs.mkdir(path.dirname(SUMMARY_PATH), { recursive: true });
  await fs.writeFile(`${SUMMARY_PATH}.tmp`, summary, "utf-8");
  await fs.rename(`${SUMMARY_PATH}.tmp`, SUMMARY_PATH);
}

async function writeReviewState(reviews: DemoReviewRecord[]) {
  const requests = await readRequests();
  await writeJsonAtomic(STATE_PATH, {
    version: "0.64",
    storage_type: "local_demo_review_state",
    statuses: demoReviewStatuses,
    draft_response_library: draftResponseLibrary,
    boundary,
    calendar_integration_enabled: false,
    email_sending_enabled: false,
    api_key_issuing_enabled: false,
    live_access_granting_enabled: false,
    billing_enabled: false,
    reviews
  });
  await writeExports(requests, reviews);
}

export async function GET() {
  if (!isLocalReviewEnabled()) {
    return localOnlyRouteDisabledResponse();
  }

  const requests = await readRequests();
  const reviews = await readReviewState();
  await writeExports(requests, reviews);
  return NextResponse.json({
    status: "ok",
    total_demo_requests: requests.length,
    statuses: demoReviewStatuses,
    draft_response_library: draftResponseLibrary,
    counts_by_status: statusCounts(requests, reviews),
    reviews,
    calendar_event_created: false,
    email_sent: false,
    api_key_issued: false,
    live_access_granted: false,
    billing_connected: false,
    boundary
  });
}

export async function POST(request: Request) {
  if (!isLocalReviewEnabled()) {
    return localOnlyRouteDisabledResponse();
  }

  const body = (await request.json().catch(() => ({}))) as {
    demo_request_id?: string;
    new_status?: string;
    reviewer_notes?: string;
    manual_scheduling_notes?: string;
    proposed_demo_slot?: string;
  };

  const demoRequestId = clean(body.demo_request_id, 140);
  const newStatus = clean(body.new_status, 80);
  const reviewerNotes = clean(body.reviewer_notes, 1400);
  const manualSchedulingNotes = clean(body.manual_scheduling_notes, 1800);
  const proposedDemoSlot = clean(body.proposed_demo_slot, 240);

  if (!demoRequestId || !newStatus) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "validation_failed",
          message: "demo_request_id and new_status are required."
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!isDemoReviewStatus(newStatus)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_demo_review_status",
          message: "Use one of the allowed local demo review statuses.",
          statuses: demoReviewStatuses
        },
        boundary
      },
      { status: 400 }
    );
  }

  const requests = await readRequests();
  const demoRequest = requests.find((item) => item.demo_request_id === demoRequestId);
  if (!demoRequest) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "demo_request_not_found",
          message: "No local demo request exists for that demo_request_id."
        },
        boundary
      },
      { status: 404 }
    );
  }

  const reviews = await readReviewState();
  const existingIndex = reviews.findIndex((item) => item.demo_request_id === demoRequestId);
  const existing = existingIndex >= 0 ? reviews[existingIndex] : undefined;
  const previousStatus = existing?.status || (isDemoReviewStatus(demoRequest.status) ? demoRequest.status : "pending_demo_review");
  const now = new Date().toISOString();
  const draftResponse = `${draftResponseLibrary[newStatus]} Local request: ${demoRequest.organisation}. Draft only; not sent automatically.`;
  const historyEntry: DemoReviewHistoryEntry = {
    timestamp: now,
    from_status: previousStatus,
    to_status: newStatus,
    reviewer_notes: reviewerNotes,
    manual_scheduling_notes: manualSchedulingNotes,
    proposed_demo_slot: proposedDemoSlot,
    draft_response: draftResponse,
    local_only: true,
    calendar_event_created: false,
    email_sent: false,
    api_key_issued: false,
    live_access_granted: false,
    billing_connected: false
  };

  const nextRecord: DemoReviewRecord = {
    demo_request_id: demoRequestId,
    status: newStatus,
    reviewer_notes: reviewerNotes,
    manual_scheduling_notes: manualSchedulingNotes,
    proposed_demo_slot: proposedDemoSlot,
    draft_response: draftResponse,
    updated_at: now,
    review_history: [...(existing?.review_history || []), historyEntry],
    local_only: true,
    calendar_event_created: false,
    email_sent: false,
    api_key_issued: false,
    live_access_granted: false,
    billing_connected: false
  };

  const nextReviews = [...reviews];
  if (existingIndex >= 0) {
    nextReviews[existingIndex] = nextRecord;
  } else {
    nextReviews.push(nextRecord);
  }
  await writeReviewState(nextReviews);

  return NextResponse.json({
    status: "ok",
    demo_request_id: demoRequestId,
    demo_review_status: newStatus,
    reviewer_notes: reviewerNotes,
    manual_scheduling_notes: manualSchedulingNotes,
    proposed_demo_slot: proposedDemoSlot,
    draft_response: draftResponse,
    review_history_count: nextRecord.review_history.length,
    calendar_event_created: false,
    email_sent: false,
    api_key_issued: false,
    live_access_granted: false,
    billing_connected: false,
    boundary
  });
}
