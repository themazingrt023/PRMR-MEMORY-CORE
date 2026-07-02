import { Navigation } from "@/components/landing/Navigation";
import { VerifyEmailPanel } from "@/components/self-serve/VerifyEmailPanel";

export default function VerifyEmailPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
        <p className="kimi-section-label">Email confirmation</p>
        <h1 className="mt-5 font-display text-[clamp(48px,8vw,96px)] leading-[0.96] text-white">
          Check your email.
        </h1>
        <p className="mt-7 max-w-2xl text-base leading-7 text-mist/62">
          Use the confirmation link we sent to finish setting up your PRMR
          account. Your workspace will stay locked until your email is verified.
        </p>
        <VerifyEmailPanel />
      </section>
    </main>
  );
}
