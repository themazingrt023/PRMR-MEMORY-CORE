import { WhopAccessFunnel } from "@/components/commercial/WhopAccessFunnel";
import { WhopOfferPanel } from "@/components/commercial/WhopOfferPanel";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";
import { whopOffer } from "@/data/whopOfferData";
import { getWhopCheckoutState } from "@/lib/whopOffer";

export default function WhopPilotPage() {
  const checkout = getWhopCheckoutState();

  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-[0.08]" />
      <Navigation />
      <div className="relative mx-auto max-w-[1400px] px-[5vw] pb-24 pt-36">
        <section className="min-h-[560px] py-16">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-mist/42">{whopOffer.eyebrow}</p>
          <h1 className="mt-7 max-w-6xl font-display text-[clamp(60px,9vw,132px)] leading-[0.88] text-white">
            {whopOffer.headline}
          </h1>
          <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_0.8fr] lg:items-end">
            <p className="max-w-3xl text-lg font-extralight leading-9 text-mist/68">{whopOffer.description}</p>
            <div className="space-y-3 text-right">
              <p className="font-display text-3xl text-white">{whopOffer.coreLine}</p>
              <p className="text-sm text-mist/48">{whopOffer.commercialLine}</p>
            </div>
          </div>
        </section>
        <WhopOfferPanel checkout={checkout} />
        <WhopAccessFunnel />
      </div>
      <Footer />
    </main>
  );
}
