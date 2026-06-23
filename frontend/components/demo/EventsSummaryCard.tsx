import { LabFrame } from "@/components/visual/LabFrame";
import type { DemoEventSummary } from "@/data/demoConnection";

export function EventsSummaryCard({ events }: { events: DemoEventSummary[] }) {
  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Synthetic events</h2>
      <div className="mt-4 space-y-3">
        {events.map((event) => (
          <div className="border border-silver/14 p-3" key={event.event_id}>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-silver/54">{event.status} / {event.signal}</p>
            <p className="mt-2 text-sm leading-6 text-mist/68">
              {event.from} -&gt; {event.to}
            </p>
          </div>
        ))}
      </div>
    </LabFrame>
  );
}
