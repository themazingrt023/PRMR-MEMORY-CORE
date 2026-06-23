import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { formCaptureDisabledResponse, isLocalFileWritesEnabled } from "@/lib/deploymentMode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type AlphaRequestPayload = {
  name?: string;
  email?: string;
  organisation?: string;
  role?: string;
  use_case_category?: string;
  use_case_description?: string;
  data_type_planned?: string;
  confirm_no_sensitive_data?: boolean;
  confirm_alpha_boundary?: boolean;
};

const REPO_ROOT = path.resolve(process.cwd(), "..");
const STORAGE_PATH = path.join(REPO_ROOT, "reports", "v058", "local_alpha_requests_v058.json");

const allowedCategories = new Set([
  "AI agent memory",
  "Customer support continuity",
  "SaaS user-history continuity",
  "Education progress continuity",
  "Legal/research case continuity",
  "Fraud/risk sandbox evaluation",
  "Company knowledge continuity",
  "Other"
]);

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
  "real customer data"
];

function clean(value: unknown, max = 1000) {
  return String(value || "").trim().slice(0, max);
}

function validEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function findSensitiveTerms(payload: AlphaRequestPayload) {
  const haystack = `${payload.use_case_description || ""} ${payload.data_type_planned || ""}`.toLowerCase();
  return sensitiveTerms.filter((term) => haystack.includes(term));
}

async function readStore() {
  try {
    const text = await fs.readFile(STORAGE_PATH, "utf-8");
    const parsed = JSON.parse(text);
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

async function writeStore(requests: unknown[]) {
  await fs.mkdir(path.dirname(STORAGE_PATH), { recursive: true });
  await fs.writeFile(
    STORAGE_PATH,
    JSON.stringify(
      {
        version: "0.58",
        storage_type: "local_alpha_request_review_queue",
        automatic_access_granted: false,
        requests
      },
      null,
      2
    ),
    "utf-8"
  );
}

export async function POST(request: Request) {
  if (!isLocalFileWritesEnabled()) {
    return formCaptureDisabledResponse();
  }

  const body = (await request.json().catch(() => ({}))) as AlphaRequestPayload;

  const payload = {
    name: clean(body.name, 120),
    email: clean(body.email, 180),
    organisation: clean(body.organisation, 180),
    role: clean(body.role, 120),
    use_case_category: clean(body.use_case_category, 120),
    use_case_description: clean(body.use_case_description, 1400),
    data_type_planned: clean(body.data_type_planned, 600),
    confirm_no_sensitive_data: body.confirm_no_sensitive_data === true,
    confirm_alpha_boundary: body.confirm_alpha_boundary === true
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
          message: "Required alpha request fields are missing.",
          missing
        },
        boundary: "No live service access is granted by this form."
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
        boundary: "No live service access is granted by this form."
      },
      { status: 400 }
    );
  }

  if (!allowedCategories.has(payload.use_case_category)) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "invalid_use_case_category",
          message: "Choose a supported alpha use case category."
        },
        boundary: "No live service access is granted by this form."
      },
      { status: 400 }
    );
  }

  const sensitiveMatches = findSensitiveTerms(body);
  if (sensitiveMatches.length) {
    return NextResponse.json(
      {
        status: "error",
        error: {
          code: "sensitive_data_not_allowed",
          message: "This local alpha request form does not accept real sensitive data descriptions.",
          matched_terms: sensitiveMatches
        },
        boundary: "Use synthetic, anonymised, or explicitly approved datasets only."
      },
      { status: 400 }
    );
  }

  const now = new Date().toISOString();
  const requestId = `alpha_v058_${Date.now().toString(36)}`;
  const summary = {
    request_id: requestId,
    received_at: now,
    status: "pending_review",
    name: payload.name,
    email: payload.email,
    organisation: payload.organisation,
    role: payload.role,
    use_case_category: payload.use_case_category,
    use_case_description: payload.use_case_description,
    data_type_planned: payload.data_type_planned,
    confirmations: {
      no_real_sensitive_data_without_approval: true,
      understands_alpha_boundary: true
    },
    review: {
      next_step: "founder/team review",
      no_live_service_access_granted: true,
      automatic_access_granted: false,
      real_credential_issued: false
    },
    boundary: "Synthetic, anonymised, or approved data only. No live service access is granted by this form."
  };

  const requests = await readStore();
  requests.push(summary);
  await writeStore(requests);

  return NextResponse.json(
    {
      status: "ok",
      request_id: requestId,
      review_status: "pending_review",
      message: "Request received locally.",
      next_step: "founder/team review",
      no_live_service_access_granted: true,
      automatic_access_granted: false,
      api_key_issued: false,
      boundary: "Synthetic, anonymised, or approved data only. No live service access is granted by this form."
    },
    { status: 201 }
  );
}
