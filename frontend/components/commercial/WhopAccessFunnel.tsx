import { whopFunnelStages, whopOffer } from "@/data/whopOfferData";

export function WhopAccessFunnel() {
  return (
    <>
      <section className="py-24">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist/42">Access sequence</p>
        <h2 className="mt-5 max-w-4xl font-display text-[clamp(42px,6vw,78px)] leading-[1] text-white">
          Payment starts a review. It does not bypass one.
        </h2>
        <div className="mt-14 border-t border-white/[0.09]">
          {whopFunnelStages.map((stage) => (
            <article
              className="grid gap-4 border-b border-white/[0.07] py-7 md:grid-cols-[70px_0.7fr_1.3fr]"
              key={stage.number}
            >
              <span className="font-mono text-xs text-mist/30">{stage.number}</span>
              <h3 className="font-display text-3xl text-white">{stage.title}</h3>
              <p className="max-w-2xl text-sm leading-7 text-mist/58">{stage.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-white/[0.09] py-20">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist/42">Controlled boundary</p>
            <h2 className="mt-5 font-display text-5xl leading-tight text-white">Access remains founder-controlled.</h2>
          </div>
          <div className="space-y-4">
            {whopOffer.boundaries.map((boundary) => (
              <p className="border-l border-white/20 pl-5 text-sm leading-7 text-mist/62" key={boundary}>
                {boundary}
              </p>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

