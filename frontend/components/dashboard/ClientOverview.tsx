import { dashboardBoundary, dashboardMockData } from "@/data/dashboardMockData";

export function ClientOverview() {
  const overview = dashboardMockData.clientOverview;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6 silver-hover">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="kimi-section-label">Client Dashboard MVP</p>
          <h1 className="mt-5 max-w-4xl font-display text-[clamp(42px,6vw,86px)] leading-[0.98] text-white">
            Local client view for controlled-alpha evidence.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-7 text-mist/62">{dashboardBoundary}</p>
          <p className="mt-4 max-w-3xl text-base leading-7 text-mist/58">
            The dashboard lets clients see safe key previews, vaults, namespaces, usage, blocked requests, public-safe
            reports, and memory health. It is visibility for the local MVP, not hosted customer access.
          </p>
        </div>
        <div className="grid gap-3 font-mono text-xs uppercase tracking-[0.14em] text-mist/58 sm:grid-cols-3 lg:min-w-[420px]">
          <Metric label="Client" value={overview.status} />
          <Metric label="Vaults" value={String(overview.activeVaultCount)} />
          <Metric label="Namespaces" value={String(overview.activeNamespaceCount)} />
        </div>
      </div>

      <div className="mt-10 grid gap-4 text-sm text-mist/62 md:grid-cols-3">
        <Info label="Synthetic client" value={overview.clientId} />
        <Info label="Organisation" value={overview.organisation} />
        <Info label="Public frontend" value={overview.publicModeAccess} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-white/[0.08] bg-white/[0.018] p-4">
      <p className="text-[10px] text-mist/38">{label}</p>
      <p className="mt-2 text-lg text-white">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-white/[0.07] pt-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-mist/36">{label}</p>
      <p className="mt-2 break-words text-mist/72">{value}</p>
    </div>
  );
}
