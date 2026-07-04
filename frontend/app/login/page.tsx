import Link from "next/link";
import { Navigation } from "@/components/landing/Navigation";
import { LoginForm } from "@/components/self-serve/LoginForm";

type LoginPageProps = {
  searchParams: Promise<{ verified?: string; error?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const initialMessage =
    params.verified === "1"
      ? "Email verified. Sign in to continue."
      : params.error === "auth_callback_failed"
        ? "We could not complete email verification. Please sign in or request a new verification email."
        : "";
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
        <p className="kimi-section-label">PRMR workspace</p>
        <h1 className="mt-5 font-display text-[clamp(48px,8vw,96px)] leading-[0.96] text-white">Return to PRMR.</h1>
        <p className="mt-7 max-w-2xl text-base leading-7 text-mist/62">
          Sign in to continue to your API workspace. PRMR API keys remain
          separate and are never used as dashboard login credentials.
        </p>
        <LoginForm initialMessage={initialMessage} />
        <Link className="mt-5 text-sm text-white/70 underline" href="/signup">Create a Free workspace</Link>
      </section>
    </main>
  );
}
