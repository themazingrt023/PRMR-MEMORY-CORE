import { FragmentedContinuityVisual } from "@/components/visual/FragmentedContinuityVisual";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

const continuityLosses = [
  "what changed",
  "what stayed true",
  "what became stale",
  "what evidence matters",
  "what should happen next",
  "what should stay private",
  "what needs human review"
];

const consequences = [
  "memory bloat",
  "stale context",
  "repeated raw history dumps",
  "weak reasoning",
  "poor handovers",
  "repeated mistakes",
  "noisy decisions",
  "potential human harm"
];

export function ProblemSection() {
  return (
    <KimiSectionShell
      id="problem"
      eyebrow="The Problem"
      title="Modern AI and company systems store information, but they often fail to preserve continuity."
      className="bg-[var(--afternum-bg-section)]"
    >
      <div className="grid gap-20 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="max-w-3xl text-lg font-extralight leading-9 text-mist/76">
            AI apps, SaaS tools, support systems, banks, research tools, education platforms, and companies can store
            huge amounts of information: logs, tickets, documents, chat history, vectors, summaries, case notes,
            transactions, and user events.
          </p>
          <p className="mt-8 max-w-2xl text-lg font-extralight leading-9 text-mist/68">
            Storage alone does not tell a system what changed, what still matters, or what should be reviewed before
            the next action. That is the continuity gap PRMR Memory Core is built for.
          </p>
          <p className="mt-8 max-w-2xl text-lg font-extralight leading-9 text-mist/68">
            PRMR can make limited context feel wider by giving systems smaller, cleaner continuity packets instead of
            raw history dumps. It does not literally increase a model&apos;s official context window.
          </p>
        </div>

        <div className="space-y-10">
          <FragmentedContinuityVisual />
          <div className="grid gap-10 md:grid-cols-2">
            <div>
              <p className="kimi-section-label mb-5">Continuity Lost</p>
              <div className="space-y-3 border-l border-white/10 pl-5">
                {continuityLosses.map((item) => (
                  <p className="text-sm leading-6 text-mist/64" key={item}>
                    {item}
                  </p>
                ))}
              </div>
            </div>
            <div>
              <p className="kimi-section-label mb-5">Consequences</p>
              <div className="space-y-3 border-l border-white/10 pl-5">
                {consequences.map((item) => (
                  <p className="text-sm leading-6 text-mist/64" key={item}>
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </KimiSectionShell>
  );
}
