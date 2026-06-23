import { LocalDemoRunner } from "@/components/demo/LocalDemoRunner";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function DemoPage() {
  return (
    <main className="relative overflow-hidden">
      <DataRainBackground className="opacity-18" />
      <Navigation />
      <LocalDemoRunner />
      <Footer />
    </main>
  );
}
