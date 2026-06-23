import Image from "next/image";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

const useCases = [
  ["AI assistant and agent memory", "AI systems", "2026", "Preserve cross-session state so agents can continue from cleaner continuity context instead of raw history dumps.", "/visual/usecase-agent.jpg"],
  ["Customer support handovers", "Support ops", "2026", "Carry active follow-up state, prior user updates, and stale notes across teams.", "/visual/usecase-support.jpg"],
  ["SaaS user-history continuity", "Product ops", "2026", "Separate users, projects, and client scopes through vaults and namespaces.", "/visual/usecase-saas.jpg"],
  ["Education learner history", "EdTech", "2026", "Track what changed in learner progress without stuffing every old interaction into the next prompt.", "/visual/usecase-education.jpg"],
  ["Legal and research case continuity", "Research ops", "2026", "Preserve case state, evidence boundaries, decisions, and notes that need review.", "/visual/usecase-legal.jpg"],
  ["Fraud and risk timelines", "Risk ops", "2026", "Review synthetic risk timelines through continuity language without certain-guilt claims.", "/visual/usecase-fraud.jpg"],
  ["Game studio lore and canon", "Creative ops", "2026", "Remember worldbuilding changes, canon updates, and stale plot assumptions across long projects.", "/visual/usecase-knowledge.jpg"],
  ["Enterprise decision logs", "Company ops", "2026", "Give teams compact continuity packets for project management, robotics, operations, and decision handoffs.", "/visual/usecase-custom.jpg"]
];

export function UseCasesSection() {
  return (
    <KimiSectionShell id="use-cases" eyebrow="Use Cases" title="Continuity where context decays.">
      <div className="grid grid-cols-1 border-l border-t border-white/[0.09] sm:grid-cols-2 lg:grid-cols-4">
        {useCases.map(([title, category, year, body, image]) => (
          <article className="silver-hover group border-b border-r border-white/[0.09] p-5 transition duration-500 hover:bg-white/[0.025]" key={title}>
            <div className="relative mb-6 aspect-square overflow-hidden bg-white/[0.02]">
              <Image alt="" className="h-full w-full object-cover opacity-42 grayscale transition duration-700 group-hover:scale-[1.05] group-hover:opacity-80" fill src={image} />
              <div className="absolute inset-0 bg-gradient-to-t from-ink/78 via-transparent to-transparent" />
            </div>
            <h3 className="font-display text-xl leading-tight text-white">{title}</h3>
            <p className="mt-3 min-h-20 text-sm leading-6 text-mist/56">{body}</p>
            <div className="mt-6 flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.14em] text-mist/38">
              <span>{category}</span>
              <span>{year}</span>
            </div>
          </article>
        ))}
      </div>
    </KimiSectionShell>
  );
}
