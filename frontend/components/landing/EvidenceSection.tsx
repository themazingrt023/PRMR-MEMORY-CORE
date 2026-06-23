import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { benchmarkEvidence } from "@/data/benchmarkEvidence";
import { boundaryStatement } from "@/data/evidence";

export function EvidenceSection() {
  return (
    <KimiSectionShell id="evidence" eyebrow="Internal Evidence" title="Internal evidence, clearly labelled.">
      <div className="grid gap-20 lg:grid-cols-[0.82fr_1.18fr]">
        <div className="space-y-8">
          <p className="text-lg font-extralight leading-9 text-mist/72">{boundaryStatement}</p>
          <p className="text-sm leading-7 text-mist/50">
            The visible evidence surface now groups benchmark categories into expandable rows. Version details are
            available on reveal so the homepage does not become a long version list.
          </p>
        </div>

        <div className="border-y border-white/[0.08]">
          {benchmarkEvidence.map((item, index) => (
            <details className="benchmark-row silver-hover border-b border-white/[0.06] last:border-b-0" key={item.category}>
              <summary className="grid cursor-pointer list-none gap-4 py-5 md:grid-cols-[56px_1fr_72px]">
                <span className="font-mono text-xs text-mist/32">{String(index + 1).padStart(2, "0")}</span>
                <span className="font-display text-2xl leading-tight text-white">{item.category}</span>
                <span className="font-mono text-xs uppercase tracking-[0.16em] text-silver/62 md:text-right">Reveal</span>
              </summary>
              <div className="grid gap-6 pb-7 pl-0 md:grid-cols-[56px_1fr]">
                <div />
                <div>
                  <div className="space-y-2">
                    {item.versions.map((version) => (
                      <p className="font-mono text-xs leading-6 text-mist/58" key={version}>
                        {version}
                      </p>
                    ))}
                  </div>
                  <p className="mt-5 text-sm leading-7 text-mist/68">{item.meaning}</p>
                  <p className="mt-3 text-xs leading-6 text-mist/42">{item.boundary}</p>
                </div>
              </div>
            </details>
          ))}
        </div>
      </div>
    </KimiSectionShell>
  );
}
