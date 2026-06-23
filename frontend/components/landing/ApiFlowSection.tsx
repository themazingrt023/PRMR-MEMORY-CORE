import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

const flows = [
  ["Create client", "client_id", "A company or local alpha evaluator gets a scoped synthetic client record."],
  ["Issue API key", "api_key", "Operator-approved keys authenticate requests; browsers never receive raw key material."],
  ["Create vault and namespace", "vault_id / namespace", "Projects, users, teams, or workflows stay separated by scope."],
  ["Send events", "/v1/events/ingest", "Your app sends chats, logs, decisions, tickets, notes, agent actions, or approved timelines to PRMR."],
  ["Generate continuity packet", "/v1/continuity/packet", "PRMR compresses what changed into scoped continuity state."],
  ["Retrieve reconstructed state", "/v1/memory/reconstruct", "Your system asks what matters now without replaying every raw event."],
  ["View usage and reports", "/dashboard", "Clients can review usage, blocked requests, report previews, and memory health in the local MVP dashboard."]
];

export function ApiFlowSection() {
  return (
    <KimiSectionShell id="api" eyebrow="API Flow" title="Add continuity to your system through a focused API layer." className="bg-[var(--afternum-bg-section)]">
      <div className="grid gap-20 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="space-y-7">
          <p className="text-lg font-extralight leading-9 text-mist/76">
            PRMR Memory Core does not replace your database, vector store, or AI model. It sits beside them as a
            continuity infrastructure layer, helping systems preserve what changed, what matters now, what became
            stale, and what should be reviewed next.
          </p>
          <p className="text-lg font-extralight leading-9 text-mist/68">
            Applications send events into PRMR through scoped credentials. PRMR turns those events into continuity
            packets, reconstructable state, public-safe explanations, least-harm action boundaries, usage logs, and
            report outputs.
          </p>
          <p className="text-sm leading-7 text-mist/48">
            Current implementation evidence is local controlled-alpha and API-shaped. It is not a hosted service.
          </p>
        </div>

        <div className="border-y border-white/[0.08]">
          {flows.map(([label, endpoint, body], index) => (
            <article className="silver-hover grid gap-4 border-b border-white/[0.06] py-6 last:border-b-0 md:grid-cols-[54px_1fr_230px]" key={endpoint}>
              <span className="font-mono text-xs text-mist/36">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3 className="font-display text-2xl leading-tight text-white">{label}</h3>
                <p className="mt-2 text-sm leading-6 text-mist/58">{body}</p>
              </div>
              <code className="font-mono text-xs leading-6 text-mist/52 md:text-right">{endpoint}</code>
            </article>
          ))}
        </div>
      </div>
    </KimiSectionShell>
  );
}
