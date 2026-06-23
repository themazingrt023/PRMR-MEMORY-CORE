import Link from "next/link";
import { CopyableCode } from "@/components/docs/CopyableCode";
import { integrationFlow, useCases } from "@/data/apiDocs";

const notList = [
  "not an AI model",
  "not a database replacement",
  "not a vector database replacement",
  "not an official model context-window expansion",
  "not a final decision engine",
  "not production-certified",
  "not bank, compliance, legal, or external security approved"
];

const localDemoFlow = [
  "Browser /demo",
  "Next.js server-side proxy",
  "local Python PRMR bridge",
  "V0.52.1 sandbox / V0.53.1 synthetic fixtures",
  "public-safe JSON",
  "frontend cards"
];

const futureNotes = [
  "hosted backend",
  "client accounts",
  "vaults and namespaces",
  "credential issuing",
  "usage logs",
  "rate limits",
  "dashboard",
  "billing",
  "external security review"
];

const samplePublicReport = `{
  "report_id": "rep_demo_001",
  "public_safe": true,
  "summary": "Continuity packet generated for controlled alpha review.",
  "owner_access": "allowed",
  "boundary": "Synthetic/local controlled-alpha evidence only."
}`;

export function DeveloperDocsSections() {
  return (
    <>
      <section id="what-prmr-is-not" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">What PRMR is not</p>
        <h2 className="mt-3 font-display text-3xl text-white">A continuity layer, not a replacement for your stack.</h2>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {notList.map((item) => (
            <div className="border border-silver/12 p-4 text-sm text-mist/70" key={item}>
              {item}
            </div>
          ))}
        </div>
      </section>

      <section id="flow" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Basic integration flow</p>
        <h2 className="mt-3 font-display text-3xl text-white">From messy history to continuity packet.</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-mist/62">
          Raw events -&gt; PRMR continuity packet -&gt; reconstructed state -&gt; explanation/report -&gt; dashboard
          visibility.
        </p>
        <div className="mt-7 border-y border-white/[0.08]">
          {integrationFlow.map((step, index) => (
            <div className="silver-hover grid gap-4 border-b border-white/[0.06] py-4 last:border-b-0 md:grid-cols-[54px_1fr]" key={step}>
              <span className="font-mono text-xs text-mist/36">{String(index + 1).padStart(2, "0")}</span>
              <span className="text-sm leading-6 text-mist/72">{step}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="examples" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Example use cases</p>
        <h2 className="mt-3 font-display text-3xl text-white">Continuity where context decays.</h2>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {useCases.map((item) => (
            <div className="silver-hover border border-silver/12 p-4 text-sm text-mist/70" key={item}>
              {item}
            </div>
          ))}
        </div>
        <div className="mt-8">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.2em] text-silver/54">Public report preview JSON</p>
          <CopyableCode code={samplePublicReport} />
        </div>
      </section>

      <section id="local-demo" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Local demo integration</p>
        <h2 className="mt-3 font-display text-3xl text-white">V0.55 local demo architecture.</h2>
        <div className="mt-7 grid gap-3">
          {localDemoFlow.map((item, index) => (
            <div className="grid gap-4 border border-silver/12 p-4 md:grid-cols-[54px_1fr]" key={item}>
              <span className="font-mono text-xs text-mist/36">{String(index + 1).padStart(2, "0")}</span>
              <span className="text-sm leading-6 text-mist/72">{item}</span>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm leading-7 text-mist/58">
          This is local-only demo wiring, not production architecture. Browser code calls proxy routes and receives
          public-safe output only.
        </p>
        <div className="mt-7 flex flex-col gap-4 sm:flex-row">
          <Link className="liquid-glass-btn" href="/demo">
            Open Local Demo
          </Link>
          <Link className="liquid-glass-btn" href="/alpha">
            Request Alpha Access
          </Link>
        </div>
      </section>

      <section id="safety" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Safety and boundaries</p>
        <h2 className="mt-3 font-display text-3xl text-white">Keep public surfaces public-safe.</h2>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {[
            "Synthetic/demo data only for current local demo",
            "No real sensitive data unless explicitly approved",
            "No final punitive decisions",
            "Restricted diagnostic reports remain server-side",
            "Browser never receives raw credentials",
            "External validation and production hardening are future milestones"
          ].map((item) => (
            <div className="border border-silver/12 p-4 text-sm leading-6 text-mist/70" key={item}>
              {item}
            </div>
          ))}
        </div>
      </section>

      <section id="future" className="panel mt-8 p-8 md:p-10">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Future hosted API notes</p>
        <h2 className="mt-3 font-display text-3xl text-white">Future work, not current claims.</h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-mist/62">
          A future hosted service would require separate backend work, security hardening, operational policy, and external review.
          These items are future milestones, not V0.72.1 implementation claims.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          {futureNotes.map((item) => (
            <span className="border border-silver/16 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-mist/54" key={item}>
              {item}
            </span>
          ))}
        </div>
      </section>
    </>
  );
}
