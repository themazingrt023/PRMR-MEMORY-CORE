import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

const packetContents = [
  "current state",
  "what changed",
  "what still matters",
  "active signals",
  "stale signals",
  "what needs review",
  "what should be remembered safely",
  "what should not be blindly repeated",
  "evidence",
  "reconstruction state",
  "public-safe explanation",
  "least-harm action boundary",
  "public/private reports"
];

const pipeline = [
  ["Raw events", "Chats, logs, tickets, case histories, research notes, agent actions, support interactions, risk timelines, and canon changes enter as scoped events."],
  ["PRMR continuity packet", "The useful shape of change is compressed under the correct client, vault, and namespace."],
  ["Reconstructed state", "Current state is rebuilt without replaying every old event into the next system."],
  ["Explanation / report", "Public-safe explanations and report previews can be produced without restricted diagnostics."],
  ["Dashboard visibility", "Clients can see keys, vaults, namespaces, usage, blocked requests, reports, and memory health."],
  ["Review boundary", "Next steps stay proportionate and review-oriented, not final automated decisions."]
];

export function SolutionSection() {
  return (
    <KimiSectionShell id="solution" eyebrow="The Solution" title="PRMR preserves the shape of change." className="bg-[var(--afternum-bg-section)]">
      <div className="grid gap-20 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-8">
          <p className="text-lg font-extralight leading-9 text-mist/76">
            PRMR Memory Core is plug-in continuity infrastructure. Companies connect PRMR to their AI system or
            workflow using an API key, client ID, vault, and namespace.
          </p>
          <p className="text-lg font-extralight leading-9 text-mist/68">
            They send messy event histories into PRMR. PRMR converts those histories into smaller continuity packets
            that preserve {packetContents.join(", ")}.
          </p>
          <p className="text-sm leading-7 text-mist/48">
            PRMR gives AI systems a continuity layer outside the model. The current shell shows this backbone locally
            with synthetic/demo data only.
          </p>
        </div>

        <div className="border-y border-white/[0.08]">
          {pipeline.map(([label, body], index) => (
            <article className="group grid gap-6 border-b border-white/[0.06] py-7 last:border-b-0 md:grid-cols-[72px_1fr]" key={label}>
              <span className="font-mono text-xs text-mist/36">{String(index + 1).padStart(2, "0")}</span>
              <div className="grid gap-3 md:grid-cols-[0.62fr_1fr] md:items-baseline">
                <h3 className="font-display text-3xl leading-tight text-white transition group-hover:text-silver">
                  {label}
                </h3>
                <p className="text-sm leading-6 text-mist/58">{body}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </KimiSectionShell>
  );
}
