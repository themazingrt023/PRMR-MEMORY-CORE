import { dashboardMockData } from "@/data/dashboardMockData";

export function MemoryHealthPanel() {
  const health = dashboardMockData.memoryHealthPanel;
  const checks = [
    ["Reconstruction", health.reconstructionAvailable],
    ["Explanation", health.explanationAvailable],
    ["Least-harm action", health.leastHarmAvailable],
    ["Public report", health.publicReportAvailable]
  ] as const;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Memory Health</p>
      <h2 className="mt-4 font-display text-4xl text-white">Continuity state is visible, but limited.</h2>
      <p className="mt-4 max-w-3xl text-sm leading-6 text-mist/54">{health.healthNote}</p>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <HealthMetric label="Events" value={health.eventsReceived} />
        <HealthMetric label="Packets" value={health.packetsGenerated} />
        <HealthMetric label="Blocked" value={health.blockedRequestCount} />
      </div>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {checks.map(([label, enabled]) => (
          <div className="flex items-center justify-between border border-white/[0.08] px-4 py-3 text-sm" key={label}>
            <span className="text-mist/58">{label}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-white">{enabled ? "available" : "not available"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function HealthMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-white/[0.08] bg-white/[0.018] p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/38">{label}</p>
      <p className="mt-3 font-display text-5xl text-white">{value}</p>
    </div>
  );
}
