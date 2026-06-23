import { LabFrame } from "@/components/visual/LabFrame";
import { boundaryStatement } from "@/data/evidence";

export function ApiOverview() {
  return (
    <LabFrame className="p-8 md:p-10">
      <p className="font-mono text-sm uppercase tracking-[0.28em] text-silver/64">Developer docs</p>
      <h1 className="mt-4 max-w-4xl font-display text-[clamp(42px,5vw,78px)] leading-[1.05] text-mist">
        Build with continuity, not just storage.
      </h1>
      <p className="mt-6 max-w-3xl text-lg font-extralight leading-9 text-mist/74">
        PRMR Memory Core is plug-in continuity infrastructure. Companies connect PRMR to their AI system or workflow
        using an API key, client ID, vault, and namespace, then send messy event histories into PRMR.
      </p>
      <p className="mt-5 max-w-3xl text-lg font-extralight leading-9 text-mist/70">
        PRMR turns those histories into smaller continuity packets, reconstructed state, public-safe explanations,
        least-harm action boundaries, usage logs, reports, and dashboard visibility.
      </p>
      <p className="mt-5 max-w-3xl font-display text-3xl leading-tight text-white">
        Storage remembers data. PRMR remembers change.
      </p>
      <p className="mt-5 max-w-3xl text-sm leading-7 text-mist/58">
        PRMR gives AI systems a continuity layer outside the model. It can make limited context feel wider by giving
        systems smaller, cleaner continuity packets instead of raw history dumps; it does not increase a model&apos;s
        official context window.
      </p>
      <p className="mt-4 text-xs leading-5 text-mist/55">{boundaryStatement}</p>
    </LabFrame>
  );
}
