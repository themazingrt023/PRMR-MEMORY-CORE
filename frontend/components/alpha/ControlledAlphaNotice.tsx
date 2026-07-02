import { AfternumLogo } from "@/components/brand/AfternumLogo";
import { commercialBoundary, pilotOffer } from "@/data/commercialAlphaCopy";

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
      <p className="mt-4 text-sm leading-7 text-mist/66">
        Approved teams can request a demo, describe a use case, or discuss a manually approved pilot. {pilotOffer.pricing}
      </p>
      <p className="mt-4 text-xs leading-5 text-mist/48">
        Pending founder/team review. No live service access is granted by this form. {commercialBoundary}
      </p>
      <div className="mt-6 flex flex-col gap-4 sm:flex-row">
        <a className="liquid-glass-btn" href="/book-demo">
          Book a Demo
        </a>
        <a className="liquid-glass-btn" href="/pilot">
          View Pilot Path
        </a>
      </div>
    </section>
  );
}
