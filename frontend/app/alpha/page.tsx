import { ControlledAlphaNotice } from "@/components/alpha/ControlledAlphaNotice";
import { RequestAccessForm } from "@/components/alpha/RequestAccessForm";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function AlphaPage() {
  return (
    <main className="relative overflow-hidden">
      <DataRainBackground className="opacity-16" />
      <Navigation />
      <div className="relative mx-auto max-w-5xl px-6 pb-24 pt-32">
        <ControlledAlphaNotice />
        <RequestAccessForm />
      </div>
      <Footer />
    </main>
  );
}
