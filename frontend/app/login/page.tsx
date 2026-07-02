import { Navigation } from "@/components/landing/Navigation";
import { LoginForm } from "@/components/self-serve/LoginForm";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function LoginPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-12" />
      <Navigation />
      <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
        <p className="kimi-section-label">Hosted MVP Login</p>
        <h1 className="mt-5 font-display text-[clamp(48px,8vw,96px)] leading-[0.96] text-white">Return to PRMR.</h1>
        <p className="mt-7 max-w-2xl text-base leading-7 text-mist/62">
          Login uses the V0.94 hash-backed session MVP. Your session token stays in an HTTP-only cookie and is not
          exposed to browser JavaScript. This is not production authentication hardening.
        </p>
        <LoginForm />
        <a className="mt-5 text-sm text-white/70 underline" href="/signup">Create a Free workspace</a>
      </section>
    </main>
  );
}
