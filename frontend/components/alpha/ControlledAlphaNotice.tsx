import { AfternumLogo } from "@/components/brand/AfternumLogo";

export function ControlledAlphaNotice() {
  return (
    <section className="panel p-8">
      <AfternumLogo size="mark" />
      <p className="mt-5 font-mono text-sm uppercase tracking-[0.28em] text-silver/64">Controlled Alpha Access</p>
      <h1 className="mt-3 font-display text-4xl text-mist">Request controlled alpha access</h1>
      <p className="mt-4 text-sm leading-7 text-mist/72">
        PRMR Memory Core is plug-in continuity infrastructure for AI systems and organisations. Controlled alpha
        evaluation uses synthetic, anonymised, or explicitly approved datasets to test API keys, client IDs, vaults,
        namespaces, continuity packets, reports, and dashboard visibility.
      </p>
      <p className="mt-4 text-xs leading-5 text-mist/48">
        Pending founder/team review. No live service access is granted by this form. No production access is claimed.
        No bank approval, no compliance approval, no legal approval, no external security certification, and no real-world
        validation is claimed.
      </p>
      <a className="liquid-glass-btn mt-6" href="/book-demo">
        Book a Controlled Demo
      </a>
    </section>
  );
}
