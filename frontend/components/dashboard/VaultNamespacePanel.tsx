import { dashboardMockData } from "@/data/dashboardMockData";

export function VaultNamespacePanel() {
  const panel = dashboardMockData.vaultNamespacePanel;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Vaults and Namespaces</p>
      <h2 className="mt-4 font-display text-4xl text-white">Scoped synthetic storage view.</h2>
      <p className="mt-4 max-w-3xl text-sm leading-6 text-mist/54">{panel.crossClientBoundary}</p>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        {panel.namespaces.map((namespace) => (
          <article className="border border-white/[0.08] bg-white/[0.018] p-5" key={namespace.namespaceId}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">{namespace.vaultId}</p>
                <h3 className="mt-2 font-display text-3xl text-white">{namespace.namespace}</h3>
              </div>
              <span className="border border-white/14 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-mist/58">
                {namespace.status}
              </span>
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3 font-mono text-xs uppercase tracking-[0.12em] text-mist/50">
              <SmallStat label="Events" value={namespace.eventCount} />
              <SmallStat label="Packets" value={namespace.packetCount} />
              <SmallStat label="Reports" value={namespace.publicReportCount} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SmallStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-mist/34">{label}</p>
      <p className="mt-2 text-lg text-white">{value}</p>
    </div>
  );
}
