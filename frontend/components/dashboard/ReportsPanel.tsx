import { dashboardMockData } from "@/data/dashboardMockData";

export function ReportsPanel() {
  const panel = dashboardMockData.reportsPanel;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Reports</p>
      <h2 className="mt-4 font-display text-4xl text-white">Public-safe report previews.</h2>
      <p className="mt-4 max-w-3xl text-sm leading-6 text-mist/54">{panel.boundary}</p>

      <div className="mt-8 grid gap-4">
        {panel.reports.map((report) => (
          <article className="border border-white/[0.08] bg-white/[0.018] p-5" key={report.reportId}>
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">{report.reportId}</p>
                <h3 className="mt-2 font-display text-3xl text-white">{report.summary}</h3>
              </div>
              <span className="h-fit border border-white/14 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-mist/58">
                public safe
              </span>
            </div>
            <p className="mt-5 text-sm text-mist/54">
              Packet {report.packetId} / {report.eventCount} synthetic event.
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
