import { LabFrame } from "@/components/visual/LabFrame";
import type { ConnectedDenialPath } from "@/data/demoConnection";

export function DenialPathCard({ denialPath }: { denialPath: ConnectedDenialPath }) {
  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Denial path proof</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Outcome label="Wrong-key access" passed={denialPath.wrong_key_denied} code={denialPath.wrong_key_result} />
        <Outcome label="Cross-client access" passed={denialPath.cross_client_denied} code={denialPath.cross_client_result} />
      </div>
      <p className="mt-4 text-sm leading-6 text-mist/58">
        The frontend receives only this public denial result. Raw keys, vault secrets, and private diagnostics stay server-side.
      </p>
    </LabFrame>
  );
}

function Outcome({ label, passed, code }: { label: string; passed: boolean; code?: string }) {
  return (
    <div className="border border-silver/16 p-3">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">{label}</p>
      <p className="mt-2 text-sm text-mist/74">{passed ? "Denied" : "Needs review"}</p>
      <p className="mt-1 text-xs text-mist/44">{code || "no code"}</p>
    </div>
  );
}
