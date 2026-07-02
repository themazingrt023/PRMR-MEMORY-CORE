import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { LabFrame } from "@/components/visual/LabFrame";
import { infrastructureLeverage } from "@/data/commercialAlphaCopy";

export function InfrastructureLeverageSection() {
  return (
    <KimiSectionShell id="leverage" eyebrow="Infrastructure" title={infrastructureLeverage.title}>
      <div className="grid gap-16 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-8">
          <p className="font-display text-[clamp(36px,4.6vw,74px)] leading-[0.98] text-white">
            {infrastructureLeverage.mainLine}
          </p>
          {infrastructureLeverage.paragraphs.map((paragraph) => (
            <p className="text-lg font-extralight leading-9 text-mist/72" key={paragraph}>
              {paragraph}
            </p>
          ))}
        </div>

        <LabFrame className="p-8">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-silver/52">Layer Underneath</p>
          <div className="mt-7 space-y-5">
            {infrastructureLeverage.closingLines.map((line) => (
              <p className="font-display text-[clamp(34px,4vw,58px)] leading-tight text-white" key={line}>
                {line}
              </p>
            ))}
          </div>
          <div className="mt-10 border-t border-white/[0.08] pt-7">
            {infrastructureLeverage.optionalLines.map((line) => (
              <p className="mt-3 text-sm leading-7 text-mist/58 first:mt-0" key={line}>
                {line}
              </p>
            ))}
          </div>
        </LabFrame>
      </div>
    </KimiSectionShell>
  );
}
