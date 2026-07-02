import { whopOffer } from "@/data/whopOfferData";
import type { WhopCheckoutState } from "@/lib/whopOffer";

export function WhopOfferPanel({ checkout }: { checkout: WhopCheckoutState }) {
  return (
    <section className="border-y border-white/[0.09] py-10">
      <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr]">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist/42">Controlled Alpha Pilot</p>
          <p className="mt-5 font-display text-6xl text-white">{whopOffer.price}</p>
          <p className="mt-4 text-sm leading-7 text-mist/52">One pilot scope. Manual approval and limited usage.</p>
          <a
            className="liquid-glass-btn mt-8 inline-flex"
            href={checkout.url}
            rel={checkout.external ? "noreferrer" : undefined}
            target={checkout.external ? "_blank" : undefined}
          >
            <span>{checkout.label}</span>
          </a>
          <p className="mt-4 max-w-md text-xs leading-6 text-mist/42">
            {checkout.configured
              ? "Hosted checkout is configured. Completing checkout still does not grant automatic PRMR access."
              : "Whop checkout is not connected in this deployment yet. The button uses the manual pilot application path."}
          </p>
        </div>

        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-mist/42">Pilot includes</p>
          <div className="mt-5 grid gap-x-8 md:grid-cols-2">
            {whopOffer.includes.map((item, index) => (
              <div className="grid grid-cols-[34px_1fr] border-t border-white/[0.07] py-4" key={item}>
                <span className="font-mono text-[10px] text-mist/30">{String(index + 1).padStart(2, "0")}</span>
                <p className="text-sm leading-6 text-mist/66">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

