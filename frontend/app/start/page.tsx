import { Navigation } from "@/components/landing/Navigation";
import { StartFlow } from "@/components/self-serve/StartFlow";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function StartPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-12" />
      <Navigation />
      <section className="relative mx-auto max-w-6xl px-6 pb-24 pt-36">
        <p className="kimi-section-label">Account setup</p>
        <h1 className="mt-5 max-w-4xl font-display text-[clamp(46px,7vw,92px)] leading-[0.96] text-white">
          Verify. Choose. Build.
        </h1>
        <p className="mt-7 max-w-3xl text-base leading-7 text-mist/62">
          V0.92 records verification locally for this MVP walkthrough. No verification email is sent, no payment is
          collected, and no hosted credential is created from this browser.
        </p>
        <StartFlow />
      </section>
    </main>
  );
}
