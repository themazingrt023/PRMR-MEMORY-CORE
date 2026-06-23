import { ApiKeyPanel } from "@/components/dashboard/ApiKeyPanel";
import { ClientOverview } from "@/components/dashboard/ClientOverview";
import { MemoryHealthPanel } from "@/components/dashboard/MemoryHealthPanel";
import { ReportsPanel } from "@/components/dashboard/ReportsPanel";
import { RequestLogTable } from "@/components/dashboard/RequestLogTable";
import { UsageOverview } from "@/components/dashboard/UsageOverview";
import { VaultNamespacePanel } from "@/components/dashboard/VaultNamespacePanel";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";
import { isPublicFrontendMode, PUBLIC_FRONTEND_BOUNDARY } from "@/lib/deploymentMode";

export default function DashboardPage() {
  if (isPublicFrontendMode()) {
    return <DashboardDisabled />;
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-10" />
      <Navigation />
      <div className="relative mx-auto max-w-[1500px] space-y-6 px-6 pb-24 pt-32">
        <ClientOverview />
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <ApiKeyPanel />
          <VaultNamespacePanel />
        </div>
        <div className="grid gap-6 xl:grid-cols-[0.82fr_1.18fr]">
          <UsageOverview />
          <MemoryHealthPanel />
        </div>
        <RequestLogTable />
        <ReportsPanel />
      </div>
      <Footer />
    </main>
  );
}

function DashboardDisabled() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-10" />
      <Navigation />
      <section className="relative mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-32">
        <p className="kimi-section-label">Dashboard Access</p>
        <h1 className="mt-5 font-display text-[clamp(44px,7vw,92px)] leading-[0.96] text-white">
          Dashboard access is not enabled on the public frontend.
        </h1>
        <p className="mt-6 max-w-3xl text-base leading-7 text-mist/62">
          The V0.72 client dashboard is a local controlled-alpha MVP using synthetic/dev-only evidence. It does not
          provide hosted customer authentication, billing, live API access, self-serve onboarding, or production access.
        </p>
        <div className="mt-10 border border-silver/12 bg-[var(--afternum-bg-panel)] p-5 text-sm leading-6 text-mist/54">
          {PUBLIC_FRONTEND_BOUNDARY}
        </div>
      </section>
    </main>
  );
}
