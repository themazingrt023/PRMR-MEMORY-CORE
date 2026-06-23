import { demoScenarios } from "@/data/demoData";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

const flow = [
  "Raw events",
  "PRMR continuity packet",
  "Reconstructed state",
  "Explanation/report",
  "Dashboard visibility",
  "wrong-key/cross-client denial"
];

export function DemoPreviewSection() {
  return (
    <KimiSectionShell id="demo" eyebrow="Local Demo" title="Replay synthetic scenarios through the continuity flow." className="bg-[var(--afternum-bg-section)]">
      <div className="grid gap-20 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-8">
          <p className="text-lg font-extralight leading-9 text-mist/74">
            The V0.53.1 replay pack shows AI agent memory continuity, customer support/user-history continuity, and
            fraud/risk continuity sandbox scenarios moving through the same controlled-alpha flow.
          </p>
          <p className="text-lg font-extralight leading-9 text-mist/68">
            The point is practical: messy histories become smaller continuity packets that a system can retrieve as
            cleaner context before the next action.
          </p>
          <p className="text-sm leading-7 text-mist/50">Synthetic data only. Local controlled-alpha demo only.</p>
          <a className="liquid-glass-btn" href="/demo">
            Open Demo Page
          </a>
        </div>

        <div className="space-y-14">
          <div className="grid gap-0 border-y border-white/[0.08] md:grid-cols-3">
            {demoScenarios.map((scenario) => (
              <article className="silver-hover border-b border-white/[0.06] py-6 md:border-b-0 md:border-r md:px-6 md:first:pl-0 md:last:border-r-0" key={scenario.id}>
                <h3 className="font-display text-2xl leading-tight text-white">{scenario.name}</h3>
                <p className="mt-4 text-sm leading-6 text-mist/58">{scenario.description}</p>
              </article>
            ))}
          </div>

          <div className="border-y border-white/[0.08]">
            {flow.map((step, index) => (
              <div className="silver-hover grid gap-4 border-b border-white/[0.06] py-4 last:border-b-0 md:grid-cols-[56px_1fr]" key={step}>
                <span className="font-mono text-xs text-mist/32">{String(index + 1).padStart(2, "0")}</span>
                <span className="text-sm leading-6 text-mist/70">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </KimiSectionShell>
  );
}
