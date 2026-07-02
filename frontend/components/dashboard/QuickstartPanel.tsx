const envQuickstart = `PRMR_API_BASE_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<YOUR_PRMR_KEY>
PRMR_CLIENT_ID=<CLIENT_ID>
PRMR_VAULT_ID=<VAULT_ID>
PRMR_NAMESPACE=default`;

export function QuickstartPanel() {
  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">Quickstart</p>
      <div className="mt-4 grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <h2 className="font-display text-4xl text-white">From copy-once key to server-side use.</h2>
          <ol className="mt-6 space-y-3 text-sm leading-6 text-mist/58">
            <li>1. Create and copy the key once.</li>
            <li>2. Put it in your server&apos;s local <code className="font-mono text-mist/82">.env</code> file.</li>
            <li>3. Send scoped client, vault, and namespace values with API requests.</li>
            <li>4. Return here to inspect usage, logs, reports, and memory health.</li>
          </ol>
          <p className="mt-6 border-l border-white/24 pl-4 text-sm leading-6 text-white">
            Do not expose PRMR API keys in frontend or browser code. Use them server-side only.
          </p>
        </div>
        <pre className="overflow-x-auto border border-white/[0.09] bg-black/25 p-5 font-mono text-xs leading-7 text-mist/76">
          <code>{envQuickstart}</code>
        </pre>
      </div>
    </section>
  );
}
