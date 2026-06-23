import { AfternumLogo } from "@/components/brand/AfternumLogo";
import { DataRainBackground } from "@/components/visual/DataRainBackground";
import { LiquidGlassButton } from "@/components/visual/LiquidGlassButton";
import { boundaryStatement } from "@/data/evidence";
import { coreConcept, outsideModelLine, productUtilityLine, supportLine } from "@/data/productCopy";

export function HeroSection() {
  return (
    <section id="hero" className="hero-shell relative h-screen w-full overflow-hidden">
      <DataRainBackground className="opacity-70" />
      <div className="absolute inset-0 z-[1] bg-[radial-gradient(circle_at_50%_16%,rgba(232,238,245,0.12),transparent_30%),linear-gradient(180deg,rgba(9,9,9,0.16),rgba(9,9,9,0.54)_76%,#090909)]" />
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-[5vw] pb-[8vh] pt-[17vh] text-center">
        <AfternumLogo className="mb-6" priority size="heroFull" />
        <h1 className="metal-text font-display text-[clamp(44px,6.8vw,108px)] leading-[0.96] text-mist">
          Continuity infrastructure for AI systems and organisations.
        </h1>
        <p className="mt-7 font-display text-[clamp(22px,2.6vw,38px)] leading-[1.22] text-white">
          Building systems that remember what matters.
        </p>
        <p className="mt-6 max-w-[720px] text-[clamp(14px,1.3vw,18px)] font-extralight leading-8 text-white/78">
          {supportLine}
        </p>
        <p className="mt-4 max-w-[760px] text-sm font-extralight leading-7 text-white/58">
          {productUtilityLine}
        </p>
        <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.16em] text-white/50">
          {outsideModelLine}
        </p>
        <p className="mt-6 font-display text-2xl text-silver/88">{coreConcept}</p>
        <div className="pointer-events-auto mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <LiquidGlassButton href="/demo">
            View Local Demo
          </LiquidGlassButton>
          <LiquidGlassButton href="/book-demo">
            Book a Demo
          </LiquidGlassButton>
          <LiquidGlassButton href="/alpha">
            Request Alpha Access
          </LiquidGlassButton>
        </div>
        <p className="mt-8 max-w-[650px] text-[11px] font-extralight leading-5 text-white/42">
          {boundaryStatement}
        </p>
      </div>
    </section>
  );
}
