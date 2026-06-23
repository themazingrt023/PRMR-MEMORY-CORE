import { dashboardMockData } from "@/data/dashboardMockData";

export function UsageOverview() {
  const usage = dashboardMockData.usageOverview;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Usage Overview</p>
      <h2 className="mt-4 font-display text-4xl text-white">Local request evidence.</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <UsageMetric label="Allowed" value={usage.allowedRequestCount} />
        <UsageMetric label="Blocked" value={usage.blockedRequestCount} />
        <UsageMetric label="Total" value={usage.totalRequestCount} />
      </div>
      <div className="mt-8 border-t border-white/[0.07] pt-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">Milestone comparison</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {Object.entries(usage.priorMilestoneComparison).map(([version, value]) => (
            <div className="flex items-center justify-between border border-white/[0.08] px-4 py-3 text-sm text-mist/64" key={version}>
              <span className="font-mono uppercase tracking-[0.14em]">{version}</span>
              <span className="text-white">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function UsageMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-white/[0.08] bg-white/[0.018] p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/38">{label}</p>
      <p className="mt-3 font-display text-5xl text-white">{value}</p>
    </div>
  );
}
