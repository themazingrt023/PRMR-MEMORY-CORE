import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { LabFrame } from "@/components/visual/LabFrame";
import { commercialBoundary, commercialHero, marketLandscape, prmrDifference } from "@/data/commercialAlphaCopy";

export default function MarketPage() {
  return (
    <main className="relative overflow-hidden">
      <Navigation />
      <KimiSectionShell id="market" eyebrow="Market Landscape" title={marketLandscape.title}>
        <div className="grid gap-16 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-8">
            {marketLandscape.paragraphs.map((paragraph) => (
              <p className="text-lg font-extralight leading-9 text-mist/74" key={paragraph}>
                {paragraph}
              </p>
            ))}
          </div>
          <div className="border-y border-white/[0.08]">
            {marketLandscape.categories.map((category, index) => (
              <div className="grid gap-5 border-b border-white/[0.06] py-5 last:border-b-0 md:grid-cols-[54px_1fr]" key={category}>
                <span className="font-mono text-xs text-mist/34">{String(index + 1).padStart(2, "0")}</span>
                <p className="font-display text-2xl text-white">{category}</p>
              </div>
            ))}
          </div>
        </div>
      </KimiSectionShell>

      <KimiSectionShell id="different" eyebrow="Why PRMR Is Different" title={prmrDifference.title}>
        <div className="grid gap-14 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-8">
            {prmrDifference.paragraphs.map((paragraph) => (
              <p className="text-lg font-extralight leading-9 text-mist/74" key={paragraph}>
                {paragraph}
              </p>
            ))}
            <p className="text-sm leading-7 text-mist/48">{commercialBoundary}</p>
          </div>
          <LabFrame className="p-8">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/52">The Gap</p>
            <div className="mt-6 space-y-5">
              <p className="font-display text-4xl leading-tight text-white">{commercialHero.gap}</p>
            </div>
            <a className="liquid-glass-btn mt-8" href="/public-proof">
              <span>View Evidence</span>
            </a>
          </LabFrame>
        </div>
      </KimiSectionShell>
      <Footer />
    </main>
  );
}
