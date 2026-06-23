import { LabFrame } from "@/components/visual/LabFrame";
import type { ConnectedReconstruction } from "@/data/demoConnection";

export function ReconstructionCard({ reconstruction }: { reconstruction: ConnectedReconstruction }) {
  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Reconstructed state</h2>
      <p className="mt-3 text-sm leading-6 text-mist/74">{reconstruction.state}</p>
      <p className="mt-4 font-mono text-xs uppercase tracking-[0.2em] text-silver/64">
        Confidence: {reconstruction.confidence_label}
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <SignalColumn title="Active" items={reconstruction.active_signals || []} />
        <SignalColumn title="Stale" items={reconstruction.stale_signals || []} />
      </div>
    </LabFrame>
  );
}

function SignalColumn({ title, items }: { title: string; items: string[] }) {
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
