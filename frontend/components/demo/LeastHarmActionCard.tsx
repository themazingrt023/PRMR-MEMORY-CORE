import { LabFrame } from "@/components/visual/LabFrame";
import type { LeastHarmAction } from "@/data/demoData";
import type { ConnectedLeastHarmAction } from "@/data/demoConnection";

export function LeastHarmActionCard({ action }: { action: LeastHarmAction | ConnectedLeastHarmAction }) {
  const normalized = normalizeAction(action);

  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Least-harm action</h2>
      <p className="mt-3 text-sm text-mist/74">Recommended label: {normalized.label}</p>
      <p className="mt-3 text-sm leading-6 text-mist/62">{normalized.meaning}</p>
      <p className="mt-3 font-mono text-xs uppercase tracking-[0.2em] text-silver/64">Allowed actions</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {normalized.allowedActions.map((item) => (
          <span className="border border-silver/18 px-3 py-1 text-xs text-mist/70" key={item}>
            {item}
          </span>
        ))}
      </div>
      <p className="mt-4 text-sm text-mist/62">
        Final decision: {normalized.notFinalDecision ? "not made by this shell" : "needs review"}
      </p>
    </LabFrame>
  );
}

function normalizeAction(action: LeastHarmAction | ConnectedLeastHarmAction) {
  if ("allowed_actions" in action || "not_final_decision" in action) {
    return {
      label: action.label,
      meaning: "meaning" in action ? action.meaning : "",
      allowedActions: action.allowed_actions || [],
      notFinalDecision: action.not_final_decision
    };
  }

  return {
    label: action.label,
    meaning: "",
    allowedActions: action.allowedActions,
    notFinalDecision: action.notFinalDecision
  };
}
