export function AccountPlanSupport() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Panel eyebrow="Billing / Plan" title="Free">
        <p>100 protected API requests per month in the V0.92 service model.</p>
        <p>Payment processing is not connected. Builder upgrades are not charged.</p>
      </Panel>
      <Panel eyebrow="Account + Storage" title="Durable locally">
        <p>Email verification and session state are simulated locally in this frontend walkthrough.</p>
        <p>V0.93 proves SQLite restart persistence for accounts, key hashes, usage, logs, reports, and dashboard state.</p>
        <p>Hosted persistent-disk redeploy survival is not yet verified.</p>
      </Panel>
      <Panel eyebrow="Support" title="Controlled channel">
        <p>Support is handled manually during the controlled-alpha stage.</p>
        <a className="mt-5 inline-block font-mono text-xs uppercase tracking-[0.14em] text-white" href="/contact">
          Contact Afternum
        </a>
      </Panel>
    </div>
  );
}

function Panel({
  eyebrow,
  title,
  children
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-silver/12 bg-[var(--afternum-bg-panel)] p-6">
      <p className="kimi-section-label">{eyebrow}</p>
      <h2 className="mt-4 font-display text-3xl text-white">{title}</h2>
      <div className="mt-5 space-y-3 text-sm leading-6 text-mist/56">{children}</div>
    </section>
  );
}
