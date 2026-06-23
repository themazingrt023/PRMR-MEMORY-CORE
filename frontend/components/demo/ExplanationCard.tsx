import { LabFrame } from "@/components/visual/LabFrame";
import type { PublicExplanation } from "@/data/demoData";
import type { ConnectedExplanation } from "@/data/demoConnection";

export function ExplanationCard({ explanation }: { explanation: PublicExplanation | ConnectedExplanation }) {
  const normalized = normalizeExplanation(explanation);

  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Public-safe explanation</h2>
      <p className="mt-3 text-sm leading-6 text-mist/74">{normalized.summary}</p>
      <p className="mt-3 text-sm leading-6 text-mist/74">{normalized.nextStep}</p>
      <p className="mt-4 border border-silver/16 p-3 text-xs leading-5 text-mist/58">
        {normalized.boundary}
      </p>
    </LabFrame>
  );
}

function normalizeExplanation(explanation: PublicExplanation | ConnectedExplanation) {
  if ("public_safe_summary" in explanation) {
    return {
      summary: explanation.public_safe_summary,
      nextStep: explanation.next_step || "",
      boundary: explanation.review_boundary
    };
  }

  return {
    summary: explanation.summary,
    nextStep: explanation.nextStep,
    boundary: explanation.boundary
  };
}
