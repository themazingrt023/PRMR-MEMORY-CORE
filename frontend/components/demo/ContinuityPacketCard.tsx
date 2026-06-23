import { LabFrame } from "@/components/visual/LabFrame";
import type { ContinuityPacket } from "@/data/demoData";
import type { ConnectedContinuityPacket } from "@/data/demoConnection";

export function ContinuityPacketCard({ packet }: { packet: ContinuityPacket | ConnectedContinuityPacket }) {
  const normalized = normalizePacket(packet);

  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Continuity packet</h2>
      <p className="mt-3 text-sm text-mist/70">Current state: {normalized.currentState}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <SignalList title="Active signals" items={normalized.activeSignals} />
        <SignalList title="Stale signals" items={normalized.staleSignals} />
      </div>
      <p className="mt-4 text-sm leading-6 text-mist/62">{normalized.summary}</p>
      {normalized.evidence.length ? (
        <div className="mt-4 border border-silver/16 p-3">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">Evidence summary</p>
          <ul className="mt-2 space-y-1 text-sm leading-6 text-mist/62">
            {normalized.evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </LabFrame>
  );
}

function normalizePacket(packet: ContinuityPacket | ConnectedContinuityPacket) {
  if ("current_state" in packet) {
    return {
      currentState: packet.current_state,
      activeSignals: packet.active_signals,
      staleSignals: packet.stale_signals,
      evidence: packet.evidence,
      summary: packet.summary
    };
  }

  return {
    currentState: packet.currentState,
    activeSignals: packet.activeSignals,
    staleSignals: packet.staleSignals,
    evidence: packet.evidenceSummary,
    summary: packet.reviewBoundary
  };
}

function SignalList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="border border-silver/16 p-3">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/64">{title}</p>
      <ul className="mt-2 space-y-1 text-sm text-mist/70">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
