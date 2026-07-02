import { Navigation } from "@/components/landing/Navigation";
import { SignupForm } from "@/components/self-serve/SignupForm";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function SignupPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-15" />
      <Navigation />
      <section className="relative mx-auto max-w-5xl px-6 pb-24 pt-36">
        <p className="kimi-section-label">Start building</p>
        <h1 className="mt-5 max-w-4xl font-display text-[clamp(48px,8vw,100px)] leading-[0.95] text-white">
          Create your PRMR workspace.
        </h1>
        <p className="mt-7 max-w-3xl text-base leading-7 text-mist/62">
          Sign up, activate a Free scope, create a copy-once API key, and use PRMR from your server. Activation calls
          the hosted backend through a server-side proxy. If durable Postgres storage is not verified, the request stops
          honestly instead of creating a browser-only account.
        </p>
        <SignupForm />
      </section>
    </main>
  );
}
