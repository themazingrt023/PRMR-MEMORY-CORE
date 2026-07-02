import { HostedSelfServeDashboard } from "@/components/dashboard/HostedSelfServeDashboard";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function DashboardPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-10" />
      <Navigation />
      <HostedSelfServeDashboard />
      <Footer />
    </main>
  );
}
