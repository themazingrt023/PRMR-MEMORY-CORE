import { HostedSelfServeDashboard } from "@/components/dashboard/HostedSelfServeDashboard";
import { ConsoleShell } from "@/components/console/ConsoleShell";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function DashboardPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[var(--afternum-bg)] text-mist">
      <DataRainBackground className="opacity-10" />
      <ConsoleShell>
        <HostedSelfServeDashboard />
      </ConsoleShell>
    </main>
  );
}
