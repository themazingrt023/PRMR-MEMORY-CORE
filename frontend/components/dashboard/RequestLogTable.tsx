import { dashboardMockData } from "@/data/dashboardMockData";

export function RequestLogTable() {
  const log = dashboardMockData.requestLogSummary;

  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Request Log</p>
      <h2 className="mt-4 font-display text-4xl text-white">Allowed and denied paths.</h2>
      <p className="mt-4 max-w-3xl text-sm leading-6 text-mist/54">{log.blockedReasonPolicy}</p>

      <div className="mt-6 flex flex-wrap gap-2">
        {log.blockedReasons.map((reason) => (
          <span className="border border-white/[0.08] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.13em] text-mist/54" key={reason}>
            {reason}
          </span>
        ))}
      </div>

      <div className="mt-8 overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-left text-sm">
          <thead className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist/38">
            <tr className="border-b border-white/[0.08]">
              <th className="py-3 pr-4 font-normal">Endpoint</th>
              <th className="py-3 pr-4 font-normal">Scope</th>
              <th className="py-3 pr-4 font-normal">Status</th>
              <th className="py-3 pr-4 font-normal">Reason</th>
              <th className="py-3 font-normal">Public-safe message</th>
            </tr>
          </thead>
          <tbody>
            {log.rows.map((row) => (
              <tr className="border-b border-white/[0.055] text-mist/62" key={`${row.endpoint}-${row.reason}-${row.clientId}`}>
                <td className="py-4 pr-4 font-mono text-xs text-mist/72">{row.endpoint}</td>
                <td className="py-4 pr-4">{row.vaultId}/{row.namespace}</td>
                <td className={row.status === "ok" ? "py-4 pr-4 text-white" : "py-4 pr-4 text-mist/46"}>{row.status}</td>
                <td className="py-4 pr-4 font-mono text-xs">{row.reason}</td>
                <td className="py-4">{row.publicSafeMessage}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
