import { Navigation } from "@/components/landing/Navigation";
import { StartFlow } from "@/components/self-serve/StartFlow";

export default function StartPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="relative mx-auto max-w-6xl px-6 py-32">
        <p className="kimi-section-label">Workspace setup</p>
        <h1 className="mt-5 max-w-4xl font-display text-[clamp(46px,7vw,92px)] leading-[0.96] text-white">
          Choose your starting plan.
        </h1>
        <p className="mt-7 max-w-3xl text-base leading-7 text-mist/62">
          Verify your email to activate your PRMR workspace. Free can activate
          now; Builder remains an unbilled beta; Controlled Pilot is manually approved.
        </p>
        <StartFlow />
      </section>
    </main>
  );
}
