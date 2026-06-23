import { AlphaAccessSection } from "@/components/landing/AlphaAccessSection";
import { ApiFlowSection } from "@/components/landing/ApiFlowSection";
import { CapabilitiesSection } from "@/components/landing/CapabilitiesSection";
import { CinematicVisionSection } from "@/components/landing/CinematicVisionSection";
import { DemoPreviewSection } from "@/components/landing/DemoPreviewSection";
import { EvidenceSection } from "@/components/landing/EvidenceSection";
import { Footer } from "@/components/landing/Footer";
import { HeroSection } from "@/components/landing/HeroSection";
import { Navigation } from "@/components/landing/Navigation";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { SolutionSection } from "@/components/landing/SolutionSection";
import { UseCasesSection } from "@/components/landing/UseCasesSection";

export default function HomePage() {
  return (
    <main>
      <Navigation />
      <HeroSection />
      <ProblemSection />
      <SolutionSection />
      <ApiFlowSection />
      <DemoPreviewSection />
      <EvidenceSection />
      <CapabilitiesSection />
      <CinematicVisionSection />
      <UseCasesSection />
      <AlphaAccessSection />
      <Footer />
    </main>
  );
}
