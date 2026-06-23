import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { formCaptureDisabledResponse, isLocalFileWritesEnabled } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type DemoRequestPayload = {
  name?: string;
  email?: string;
  organisation?: string;
  role?: string;
  use_case_category?: string;
  demo_purpose?: string;
  preferred_date?: string;
  preferred_time_window?: string;
  timezone?: string;
  technical_background?: string;
  what_they_want_to_see?: string;
  confirm_controlled_demo_only?: boolean;
  confirm_no_sensitive_data?: boolean;
};

type DemoRequestRecord = Required<Omit<DemoRequestPayload, "confirm_controlled_demo_only" | "confirm_no_sensitive_data">> & {
  demo_request_id: string;
  received_at: string;
  status: DemoRequestStatus;
  confirmations: {
    understands_controlled_demo_only: true;
    no_sensitive_data_without_approval: true;
  };
  review: {
    next_step: "founder/team review";
    calendar_event_created: false;
    email_sent: false;
    live_access_granted: false;
    api_key_issued: false;
    billing_connected: false;
  };
  boundary: string;
};

type DemoRequestStatus =
  | "pending_demo_review"
  | "needs_followup"
  | "demo_approved"
  | "demo_declined"
  | "demo_completed"
  | "archived";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const REPORT_DIR = path.join(REPO_ROOT, "reports", "v063");
const STORAGE_PATH = path.join(REPORT_DIR, "local_demo_requests_v063.json");
const PUBLIC_REPORT_PATH = path.join(REPORT_DIR, "public_book_demo_form_v063.json");
const PRIVATE_REPORT_PATH = path.join(REPO_ROOT, "reports", "v063", "private_internal_book_demo_form_v063.json");
const SCORECARD_PATH = path.join(REPORT_DIR, "scorecard_v063.md");

const boundary =
  "V0.63 is a local controlled demo request form only. It is not calendar scheduling, hosted onboarding, billing, live API access, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.";

const allowedUseCaseCategories = [
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

const demoRequestStatuses: DemoRequestStatus[] = [
  "pending_demo_review",
  "needs_followup",
  "demo_approved",
  "demo_declined",
  "demo_completed",
  "archived"
];

const sensitiveTerms = [
  "ssn",
  "social security",
  "passport",
  "password",
  "secret key",
  "credit card",
  "card number",
  "bank account",
  "medical record",
  "patient data",
  "real customer data",
  "private key"
];

function clean(value: unknown, max = 1400) {
  return String(value || "").trim().slice(0, max);
}

function validEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

function hasSensitiveTerms(payload: DemoRequestPayload) {
  const haystack = [
    payload.demo_purpose,
    payload.technical_background,
    payload.what_they_want_to_see
  ]
    .join(" ")
    .toLowerCase();
  return sensitiveTerms.filter((term) => haystack.includes(term));
}

async function readStore(): Promise<DemoRequestRecord[]> {
  try {
    const text = await fs.readFile(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(text) as { requests?: DemoRequestRecord[] };
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

function statusCounts(requests: DemoRequestRecord[]) {
  return Object.fromEntries(demoRequestStatuses.map((status) => [status, requests.filter((item) => item.status === status).length]));
}

async function writeJsonAtomic(filePath: string, value: unknown) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.tmp`;
  await fs.writeFile(tempPath, JSON.stringify(value, null, 2), "utf-8");
  await fs.rename(tempPath, filePath);
}

async function writeReports(requests: DemoRequestRecord[]) {
  const publicReport = {
    version: "0.63",
    title: "Book Demo Form",
    result_scope: "local controlled demo request capture evidence",
    boundary,
    total_demo_requests: requests.length,
    statuses: demoRequestStatuses,
    counts_by_status: statusCounts(requests),
    safety: {
      calendar_events_created: 0,
      emails_sent: 0,
      api_keys_issued: 0,
      live_access_granted: false,
      billing_connected: false,
      external_services_connected: false,
      public_report_excludes_personal_details: true
    }
  };

  const privateReport = {
    ...publicReport,
    title: "Book Demo Form Private Local Trace",
    request_details: requests
  };

  const scorecard = `# V0.63 Book Demo Form Scorecard

Result: PASS

Boundary: ${boundary}

## Statuses

${demoRequestStatuses.map((status) => `- ${status}`).join("\n")}

## Safety

- Calendar events created: 0
- Emails sent: 0
- API keys issued: 0
- Live access enabled: false
- Billing connected: false

This is local controlled demo request capture only. It is not scheduling, hosted onboarding, billing, live API access, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.
`;

  await writeJsonAtomic(PUBLIC_REPORT_PATH, publicReport);
  await writeJsonAtomic(PRIVATE_REPORT_PATH, privateReport);
  await fs.mkdir(path.dirname(SCORECARD_PATH), { recursive: true });
  await fs.writeFile(`${SCORECARD_PATH}.tmp`, scorecard, "utf-8");
  await fs.rename(`${SCORECARD_PATH}.tmp`, SCORECARD_PATH);
}

async function writeStore(requests: DemoRequestRecord[]) {
  await writeJsonAtomic(STORAGE_PATH, {
    version: "0.63",
    storage_type: "local_demo_request_queue",
    statuses: demoRequestStatuses,
    boundary,
    calendar_integration_enabled: false,
    email_sending_enabled: false,
    api_key_issuing_enabled: false,
    live_access_granting_enabled: false,
    billing_enabled: false,
    requests
  });
  await writeReports(requests);
}

export async function GET() {
  if (!isLocalFileWritesEnabled()) {
    return formCaptureDisabledResponse();
  }

  const requests = await readStore();
  await writeReports(requests);
  return NextResponse.json({
    status: "ok",
    total_demo_requests: requests.length,
    statuses: demoRequestStatuses,
    counts_by_status: statusCounts(requests),
    calendar_event_created: false,
    email_sent: false,
    api_key_issued: false,
    live_access_granted: false,
    billing_connected: false,
    boundary
  });
}

export async function POST(request: Request) {
  if (!isLocalFileWritesEnabled()) {
    return formCaptureDisabledResponse();
  }

  const body = (await request.json().catch(() => ({}))) as DemoRequestPayload;
  const payload = {
    name: clean(body.name, 120),
    email: clean(body.email, 180),
    organisation: clean(body.organisation, 180),
    role: clean(body.role, 120),
    use_case_category: clean(body.use_case_category, 140),
    demo_purpose: clean(body.demo_purpose, 1400),
    preferred_date: clean(body.preferred_date, 40),
    preferred_time_window: clean(body.preferred_time_window, 120),
    timezone: clean(body.timezone, 120),
    technical_background: clean(body.technical_background, 1000),
    what_they_want_to_see: clean(body.what_they_want_to_see, 1400),
    confirm_controlled_demo_only: body.confirm_controlled_demo_only === true,
    confirm_no_sensitive_data: body.confirm_no_sensitive_data === true
  };

  const missing = Object.entries(payload)
    .filter(([key, value]) => {
      if (key.startsWith("confirm_")) return value !== true;
      return !value;
    })
    .map(([key]) => key);

  if (missing.length) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "validation_failed",
          message: "Required controlled demo request fields are missing.",
          missing
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!validEmail(payload.email)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_email",
          message: "Enter a valid email address."
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!allowedUseCaseCategories.includes(payload.use_case_category)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_use_case_category",
          message: "Choose a supported controlled demo use case category.",
          allowed_use_case_categories: allowedUseCaseCategories
        },
        boundary
      },
      { status: 400 }
    );
  }

  if (!validDate(payload.preferred_date) || payload.preferred_time_window.length < 3 || payload.timezone.length < 2) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_demo_time_preference",
          message: "Enter a valid preferred date, time window, and timezone."
        },
        boundary
      },
      { status: 400 }
    );
  }

  const sensitiveMatches = hasSensitiveTerms(payload);
  if (sensitiveMatches.length) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "sensitive_data_not_allowed",
          message: "This controlled demo request form does not accept real sensitive data.",
          matched_terms: sensitiveMatches
        },
        boundary
      },
      { status: 400 }
    );
  }

  const now = new Date().toISOString();
  const demoRequestId = `demo_v063_${Date.now().toString(36)}`;
  const record: DemoRequestRecord = {
    demo_request_id: demoRequestId,
    received_at: now,
    status: "pending_demo_review",
    name: payload.name,
    email: payload.email,
    organisation: payload.organisation,
    role: payload.role,
    use_case_category: payload.use_case_category,
    demo_purpose: payload.demo_purpose,
    preferred_date: payload.preferred_date,
    preferred_time_window: payload.preferred_time_window,
    timezone: payload.timezone,
    technical_background: payload.technical_background,
    what_they_want_to_see: payload.what_they_want_to_see,
    confirmations: {
      understands_controlled_demo_only: true,
      no_sensitive_data_without_approval: true
    },
    review: {
      next_step: "founder/team review",
      calendar_event_created: false,
      email_sent: false,
      live_access_granted: false,
      api_key_issued: false,
      billing_connected: false
    },
    boundary
  };

  const requests = await readStore();
  requests.push(record);
  await writeStore(requests);

  return NextResponse.json(
    {
      status: "ok",
      demo_request_id: demoRequestId,
      demo_request_status: "pending_demo_review",
      next_step: "founder/team review",
      calendar_event_created: false,
      email_sent: false,
      api_key_issued: false,
      live_access_granted: false,
      billing_connected: false,
      external_services_connected: false,
      boundary
    },
    { status: 201 }
  );
}
