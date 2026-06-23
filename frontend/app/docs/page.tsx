import { ApiOverview } from "@/components/docs/ApiOverview";
import { DeveloperDocsSections } from "@/components/docs/DeveloperDocsSections";
import { EndpointList } from "@/components/docs/EndpointList";
import { EvidenceBoundaryNotice } from "@/components/docs/EvidenceBoundaryNotice";
import { VersionTimeline } from "@/components/docs/VersionTimeline";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function DocsPage() {
  return (
    <main className="relative overflow-hidden">
      <DataRainBackground className="opacity-14" />
      <Navigation />
      <div className="relative mx-auto grid max-w-[1500px] gap-8 px-6 pb-24 pt-32 lg:grid-cols-[250px_1fr]">
        <aside className="hidden lg:block">
          <nav className="sticky top-28 space-y-3 border-l border-white/10 pl-5 font-mono text-[11px] uppercase tracking-[0.18em] text-mist/44">
            <a className="block transition hover:text-white" href="#overview">Overview</a>
            <a className="block transition hover:text-white" href="#what-prmr-is-not">What PRMR is not</a>
            <a className="block transition hover:text-white" href="#flow">Flow</a>
            <a className="block transition hover:text-white" href="#endpoints">Endpoints</a>
            <a className="block transition hover:text-white" href="#examples">Examples</a>
            <a className="block transition hover:text-white" href="#local-demo">Local demo</a>
            <a className="block transition hover:text-white" href="#safety">Safety</a>
            <a className="block transition hover:text-white" href="#future">Future</a>
          </nav>
        </aside>
        <div id="overview">
          <EvidenceBoundaryNotice />
          <ApiOverview />
          <DeveloperDocsSections />
          <EndpointList />
          <VersionTimeline />
        </div>
      </div>
      <Footer />
    </main>
  );
}
