import { dashboardMockData } from "@/data/dashboardMockData";

const statusStyles = {
  active: "border-white/24 text-white",
  rotated: "border-silver/16 text-mist/62",
  revoked: "border-silver/12 text-mist/46"
};

export function ApiKeyPanel() {
  const panel = dashboardMockData.apiKeyPanel;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="kimi-section-label">API Key Panel</p>
          <h2 className="mt-4 font-display text-4xl text-white">Safe key lifecycle preview.</h2>
        </div>
        <p className="max-w-xl text-sm leading-6 text-mist/54">
          Manual operator approval remains required. This panel shows safe key previews only; it does not issue keys,
          reveal full values, or enable self-serve access.
        </p>
      </div>

      <div className="mt-7 grid gap-3 sm:grid-cols-3">
        {Object.entries(panel.safeKeyStatusCounts).map(([status, count]) => (
          <div className="border border-white/[0.08] bg-white/[0.018] p-4" key={status}>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/38">{status}</p>
            <p className="mt-2 font-display text-4xl text-white">{count}</p>
          </div>
        ))}
      </div>

      <div className="mt-7 space-y-3">
        {panel.records.map((record) => (
          <article className="grid gap-4 border border-white/[0.08] bg-white/[0.012] p-4 lg:grid-cols-[1fr_1fr_auto]" key={record.keyId}>
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">Key ID</p>
              <p className="mt-2 break-words text-sm text-mist/76">{record.keyId}</p>
            </div>
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">Preview</p>
              <p className="mt-2 font-mono text-sm text-white">{record.safeKeyPreview}</p>
            </div>
            <div className={`h-fit border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] ${statusStyles[record.status]}`}>
              {record.status}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
