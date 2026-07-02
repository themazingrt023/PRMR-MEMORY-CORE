import { Navigation } from "@/components/landing/Navigation";
import { SignupForm } from "@/components/self-serve/SignupForm";

export default function SignupPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
        <p className="kimi-section-label">PRMR API access</p>
        <h1 className="mt-5 max-w-4xl font-display text-[clamp(48px,8vw,100px)] leading-[0.95] text-white">
          Create your PRMR workspace.
        </h1>
        <p className="mt-7 max-w-3xl text-base leading-7 text-mist/62">
          Create your account, verify your email, then start building with your
          PRMR API dashboard.
        </p>
        <SignupForm />
      </section>
    </main>
  );
}
