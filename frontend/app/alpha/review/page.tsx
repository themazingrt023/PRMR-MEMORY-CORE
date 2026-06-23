import { promises as fs } from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import {
  AlphaReviewWorkflow,
  type AlphaReviewRequest,
  type ReviewerIdentity,
  type ReviewStatus
} from "@/components/alpha/AlphaReviewWorkflow";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { isLocalReviewEnabled } from "@/lib/deploymentMode";

export const dynamic = "force-dynamic";

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

type ReviewRecord = {
  request_id: string;
  status: ReviewStatus;
  reviewer_identity?: string;
  reviewer_notes?: string;
  draft_response?: string;
  updated_at?: string;
  review_history?: Array<{
    timestamp?: string;
    action?: string;
    from_status?: string;
    to_status?: string;
    reviewer_identity?: string;
    reviewer_notes?: string;
  }>;
};

const repoRoot = path.resolve(process.cwd(), "..");
const requestStoragePath = path.join(repoRoot, "reports", "v058", "local_alpha_requests_v058.json");
const reviewStoragePath = path.join(repoRoot, "reports", "v061", "local_alpha_review_ux_state_v061.json");
const fallbackV060ReviewStoragePath = path.join(repoRoot, "reports", "v060", "local_alpha_review_console_state_v060.json");
const fallbackReviewStoragePath = path.join(repoRoot, "reports", "v059", "local_alpha_review_state_v059.json");

const allowedStatuses: ReviewStatus[] = [
  "pending_review",
  "needs_followup",
  "approved_for_synthetic_demo",
  "rejected_not_fit",
  "archived"
];

const reviewerIdentities: ReviewerIdentity[] = ["founder", "technical_reviewer", "safety_reviewer", "notes_only"];

const safetyNotice =
  "This is a local review console only. It does not grant live access, issue API keys, send emails, process billing, or create hosted onboarding.";

function asReviewStatus(value: string | undefined): ReviewStatus {
  return allowedStatuses.includes(value as ReviewStatus) ? (value as ReviewStatus) : "pending_review";
}

function asReviewerIdentity(value: string | undefined): ReviewerIdentity {
  return reviewerIdentities.includes(value as ReviewerIdentity) ? (value as ReviewerIdentity) : "notes_only";
}

async function readRequests(): Promise<StoredAlphaRequest[]> {
  try {
    const text = await fs.readFile(requestStoragePath, "utf-8");
    const parsed = JSON.parse(text) as { requests?: StoredAlphaRequest[] };
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

async function readReviews(): Promise<ReviewRecord[]> {
  try {
    const text = await fs.readFile(reviewStoragePath, "utf-8");
    const parsed = JSON.parse(text) as { reviews?: ReviewRecord[] };
    const reviews = Array.isArray(parsed.reviews) ? parsed.reviews : [];
    if (reviews.length) return reviews;
    const fallbackText =
      (await fs.readFile(fallbackV060ReviewStoragePath, "utf-8").catch(() => "")) ||
      (await fs.readFile(fallbackReviewStoragePath, "utf-8").catch(() => ""));
    if (!fallbackText) return reviews;
    const fallbackParsed = JSON.parse(fallbackText) as { reviews?: ReviewRecord[] };
    const fallbackReviews = Array.isArray(fallbackParsed.reviews) ? fallbackParsed.reviews : [];
    return fallbackReviews.length ? fallbackReviews : reviews;
  } catch {
    try {
      const text = await fs.readFile(fallbackReviewStoragePath, "utf-8");
      const parsed = JSON.parse(text) as { reviews?: ReviewRecord[] };
      return Array.isArray(parsed.reviews) ? parsed.reviews : [];
    } catch {
      return [];
    }
  }
}

function mergeReviewState(requests: StoredAlphaRequest[], reviews: ReviewRecord[]): AlphaReviewRequest[] {
  return requests.map((request) => {
    const review = reviews.find((item) => item.request_id === request.request_id);
    return {
      request_id: request.request_id,
      received_at: request.received_at,
      status: review?.status || asReviewStatus(request.status),
      name: request.name || "Local requester",
      email: request.email || "local@example.com",
      organisation: request.organisation,
      role: request.role,
      use_case_category: request.use_case_category,
      use_case_description: request.use_case_description || "",
      data_type_planned: request.data_type_planned,
      confirmations: {
        no_real_sensitive_data_without_approval:
          request.confirmations?.no_real_sensitive_data_without_approval === true,
        understands_alpha_boundary: request.confirmations?.understands_alpha_boundary === true
      },
      reviewer_notes: review?.reviewer_notes || "",
      draft_response: review?.draft_response || "",
      review_history_count: Array.isArray(review?.review_history) ? review.review_history.length : 0,
      review_history: Array.isArray(review?.review_history) ? review.review_history : [],
      reviewer_identity: asReviewerIdentity(review?.reviewer_identity),
      updated_at: review?.updated_at
    };
  });
}

export default async function AlphaReviewPage() {
  if (!isLocalReviewEnabled()) {
    notFound();
  }

  const [requests, reviews] = await Promise.all([readRequests(), readReviews()]);
  const mergedRequests = mergeReviewState(requests, reviews);

  return (
    <main className="min-h-screen bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="mx-auto max-w-[1280px] px-[5vw] pb-24 pt-32">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Local alpha review console</p>
        <h1 className="mt-5 font-display text-[clamp(40px,5vw,76px)] leading-tight text-white">
          Alpha requests for local founder/team review
        </h1>
        <p className="mt-5 max-w-3xl text-sm leading-7 text-mist/62">{safetyNotice}</p>

        <AlphaReviewWorkflow initialRequests={mergedRequests} />
      </section>
      <Footer />
    </main>
  );
}
