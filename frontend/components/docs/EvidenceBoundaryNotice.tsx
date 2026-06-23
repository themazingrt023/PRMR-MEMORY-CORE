import { boundaryStatement } from "@/data/evidence";

export function EvidenceBoundaryNotice() {
  return (
    <aside className="mb-8 border border-silver/28 bg-white/[0.035] p-5 text-sm leading-6 text-mist/78">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-silver/58">Boundary</p>
      <p className="mt-3">{boundaryStatement}</p>
      <p className="mt-3 text-mist/58">
        Current docs describe internal/local controlled-alpha evidence and local demo wiring. External validation and
        production hardening are future milestones.
      </p>
    </aside>
  );
}
