import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { LabFrame } from "@/components/visual/LabFrame";
import { commercialBoundary, commercialCtas, pilotOffer } from "@/data/commercialAlphaCopy";

export default function PilotPage() {
  return (
    <main className="relative overflow-hidden">
      <Navigation />
      <KimiSectionShell id="pilot" eyebrow="Controlled Alpha API Pilot" title={pilotOffer.title}>
        <div className="grid gap-16 lg:grid-cols-[0.82fr_1.18fr]">
          <div className="space-y-7">
            <p className="text-lg font-extralight leading-9 text-mist/74">{pilotOffer.description}</p>
            <p className="font-display text-3xl leading-tight text-white">{pilotOffer.pricing}</p>
            <p className="text-sm leading-7 text-mist/54">{pilotOffer.paymentBoundary}</p>
            <p className="text-sm leading-7 text-mist/48">{commercialBoundary}</p>
            <div className="flex flex-col gap-4 sm:flex-row">
              <a className="liquid-glass-btn" href="/whop">
                <span>View Whop Pilot Offer</span>
              </a>
              <a className="liquid-glass-btn" href="/book-demo">
                <span>{commercialCtas.bookDemo}</span>
              </a>
              <a className="liquid-glass-btn" href="/public-proof">
                <span>View Evidence</span>
              </a>
            </div>
          </div>

          <LabFrame className="p-8">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/52">Pilot Includes</p>
            <div className="mt-7 border-y border-white/[0.08]">
              {pilotOffer.includes.map((item, index) => (
                <div className="grid gap-4 border-b border-white/[0.06] py-4 last:border-b-0 md:grid-cols-[44px_1fr]" key={item}>
                  <span className="font-mono text-xs text-mist/34">{String(index + 1).padStart(2, "0")}</span>
                  <p className="text-sm leading-6 text-mist/68">{item}</p>
                </div>
              ))}
            </div>
          </LabFrame>
        </div>
      </KimiSectionShell>
      <Footer />
    </main>
  );
}
