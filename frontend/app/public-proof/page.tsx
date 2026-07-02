import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { LabFrame } from "@/components/visual/LabFrame";
import { commercialBoundary, proofHighlights } from "@/data/commercialAlphaCopy";

const evidenceLadder = [
  ["Internal reconstruction", "V0.36-V0.50 checks exercise reconstruction, continuity preservation, and truth-gauntlet hygiene."],
  ["Local alpha API", "V0.52-V0.53 checks cover sandbox endpoints, key rotation, revocation, report boundaries, and local demo flow."],
  ["Hosted smoke", "V0.78-V0.79 checks prove hosted health, auth blocking, and full controlled protected route smoke with synthetic test credentials."],
  ["Client readiness", "V0.80-V0.86 checks cover manual onboarding, scoped dashboard access, storage boundary, multi-client isolation, client docs, and first-alpha readiness."]
];

const statusRows = [
  ["Frontend", "https://prmr-memory-core.vercel.app"],
  ["Backend", "https://prmr-memory-core-api.onrender.com"],
  ["Protected hosted smoke", "V0.79 PASS_FULL_CONTROLLED_HOSTED_SMOKE"],
  ["Multi-client isolation", "V0.84 PASS"],
  ["Public/private hygiene", "Checked across public reports and docs"]
];

export default function PublicProofPage() {
  return (
    <main className="relative overflow-hidden">
      <Navigation />
      <KimiSectionShell
        id="public-proof"
        eyebrow="Public-safe Evidence"
        title="Public-safe evidence for the controlled alpha pathway."
      >
        <div className="grid gap-14 lg:grid-cols-[0.78fr_1.22fr]">
          <div className="space-y-6">
            <p className="text-lg font-extralight leading-9 text-mist/74">
              This page summarizes what can be shown publicly without exposing protected engine internals, API keys,
              dashboard tokens, private reports, or real client data.
            </p>
            <p className="text-sm leading-7 text-mist/50">{commercialBoundary}</p>
          </div>

          <div className="border-y border-white/[0.08]">
            {evidenceLadder.map(([label, detail], index) => (
              <article className="grid gap-5 border-b border-white/[0.06] py-6 last:border-b-0 md:grid-cols-[54px_1fr]" key={label}>
                <span className="font-mono text-xs text-mist/34">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h2 className="font-display text-3xl text-white">{label}</h2>
                  <p className="mt-3 text-sm leading-7 text-mist/62">{detail}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="mt-20 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {proofHighlights.map((item) => (
            <LabFrame className="p-6" key={item.label}>
              <h3 className="font-display text-2xl text-silver">{item.label}</h3>
              <p className="mt-4 text-sm leading-7 text-mist/64">{item.detail}</p>
            </LabFrame>
          ))}
        </div>

        <div className="mt-20 grid gap-4 border-y border-white/[0.08] py-6">
          {statusRows.map(([label, value]) => (
            <div className="grid gap-3 py-3 md:grid-cols-[260px_1fr]" key={label}>
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-silver/50">{label}</p>
              <p className="text-sm leading-6 text-mist/68">{value}</p>
            </div>
          ))}
        </div>
      </KimiSectionShell>
      <Footer />
    </main>
  );
}
