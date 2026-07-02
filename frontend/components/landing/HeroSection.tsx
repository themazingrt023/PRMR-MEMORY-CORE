import { AfternumLogo } from "@/components/brand/AfternumLogo";
import { DataRainBackground } from "@/components/visual/DataRainBackground";
import { LiquidGlassButton } from "@/components/visual/LiquidGlassButton";
import { commercialCtas, commercialHero } from "@/data/commercialAlphaCopy";
import { boundaryStatement } from "@/data/evidence";

export function HeroSection() {
  return (
    <section id="hero" className="hero-shell relative h-screen w-full overflow-hidden">
      <DataRainBackground className="opacity-70" />
      <div className="absolute inset-0 z-[1] bg-[radial-gradient(circle_at_50%_16%,rgba(232,238,245,0.12),transparent_30%),linear-gradient(180deg,rgba(9,9,9,0.16),rgba(9,9,9,0.54)_76%,#090909)]" />
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-[5vw] pb-[8vh] pt-[17vh] text-center">
        <AfternumLogo className="mb-6" priority size="heroFull" />
        <h1 className="metal-text font-display text-[clamp(44px,6.8vw,108px)] leading-[0.96] text-mist">
          {commercialHero.primary}
        </h1>
        <p className="mt-7 font-display text-[clamp(22px,2.6vw,38px)] leading-[1.22] text-white">
          {commercialHero.subheadline}
        </p>
        <p className="mt-6 max-w-[720px] text-[clamp(14px,1.3vw,18px)] font-extralight leading-8 text-white/78">
          {commercialHero.support}
        </p>
        <p className="mt-6 max-w-[860px] font-display text-2xl leading-snug text-silver/88">{commercialHero.gap}</p>
        <div className="pointer-events-auto mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <LiquidGlassButton href="/signup">
            Get API Key
          </LiquidGlassButton>
          <LiquidGlassButton href="/docs">
            Start Building
          </LiquidGlassButton>
          <LiquidGlassButton href="/pilot">
            {commercialCtas.viewPilot}
          </LiquidGlassButton>
        </div>
        <p className="mt-8 max-w-[650px] text-[11px] font-extralight leading-5 text-white/42">
          {boundaryStatement}
        </p>
      </div>
    </section>
  );
}
