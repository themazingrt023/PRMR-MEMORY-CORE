import { promises as fs } from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import { DemoReviewWorkflow, type DemoReviewRequest, type DemoReviewStatus } from "@/components/demo/DemoReviewWorkflow";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";
import { isLocalReviewEnabled } from "@/lib/deploymentMode";

export const dynamic = "force-dynamic";

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

type DemoReviewRecord = {
  demo_request_id: string;
  status: DemoReviewStatus;
  reviewer_notes?: string;
  manual_scheduling_notes?: string;
  proposed_demo_slot?: string;
  draft_response?: string;
  updated_at?: string;
  review_history?: unknown[];
};

const repoRoot = path.resolve(process.cwd(), "..");
const requestStoragePath = path.join(repoRoot, "reports", "v063", "local_demo_requests_v063.json");
const reviewStoragePath = path.join(repoRoot, "reports", "v064", "local_demo_review_state_v064.json");

const statuses: DemoReviewStatus[] = [
  "pending_demo_review",
  "needs_followup",
  "demo_approved",
  "demo_declined",
  "demo_scheduled_manually",
  "demo_completed",
  "archived"
];

function asStatus(value: string | undefined): DemoReviewStatus {
  return statuses.includes(value as DemoReviewStatus) ? (value as DemoReviewStatus) : "pending_demo_review";
}

async function readRequests(): Promise<DemoRequestRecord[]> {
  try {
    const text = await fs.readFile(requestStoragePath, "utf-8");
    const parsed = JSON.parse(text) as { requests?: DemoRequestRecord[] };
    return Array.isArray(parsed.requests) ? parsed.requests : [];
  } catch {
    return [];
  }
}

async function readReviews(): Promise<DemoReviewRecord[]> {
  try {
    const text = await fs.readFile(reviewStoragePath, "utf-8");
    const parsed = JSON.parse(text) as { reviews?: DemoReviewRecord[] };
    return Array.isArray(parsed.reviews) ? parsed.reviews : [];
  } catch {
    return [];
  }
}

function mergeRequests(requests: DemoRequestRecord[], reviews: DemoReviewRecord[]): DemoReviewRequest[] {
  return requests.map((request) => {
    const review = reviews.find((item) => item.demo_request_id === request.demo_request_id);
    return {
      demo_request_id: request.demo_request_id,
      received_at: request.received_at,
      status: review?.status || asStatus(request.status),
      name: request.name,
      email: request.email,
      organisation: request.organisation,
      role: request.role,
      use_case_category: request.use_case_category,
      demo_purpose: request.demo_purpose,
      preferred_date: request.preferred_date,
      preferred_time_window: request.preferred_time_window,
      timezone: request.timezone,
      technical_background: request.technical_background,
      what_they_want_to_see: request.what_they_want_to_see,
      confirmations: {
        understands_controlled_demo_only: request.confirmations?.understands_controlled_demo_only === true,
        no_sensitive_data_without_approval: request.confirmations?.no_sensitive_data_without_approval === true
      },
      reviewer_notes: review?.reviewer_notes || "",
      manual_scheduling_notes: review?.manual_scheduling_notes || "",
      proposed_demo_slot: review?.proposed_demo_slot || "",
      draft_response: review?.draft_response || "",
      review_history_count: Array.isArray(review?.review_history) ? review.review_history.length : 0,
      updated_at: review?.updated_at
    };
  });
}

export default async function BookDemoReviewPage() {
  if (!isLocalReviewEnabled()) {
    notFound();
  }

  const [requests, reviews] = await Promise.all([readRequests(), readReviews()]);
  const merged = mergeRequests(requests, reviews);

  return (
    <main className="relative overflow-hidden">
      <DataRainBackground className="opacity-16" />
      <Navigation />
      <section className="mx-auto max-w-[1400px] px-6 pb-24 pt-32">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Local demo review workflow</p>
        <h1 className="mt-5 font-display text-[clamp(42px,5vw,76px)] leading-tight text-white">
          Demo requests for manual scheduling review
        </h1>
        <p className="mt-5 max-w-4xl text-sm leading-7 text-mist/64">
          This is a local demo review workflow only. It does not create calendar events, send emails, grant live access,
          issue API keys, process billing, or create hosted onboarding.
        </p>
        <DemoReviewWorkflow initialRequests={merged} />
      </section>
      <Footer />
    </main>
  );
}
