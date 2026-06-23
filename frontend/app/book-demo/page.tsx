import { BookDemoForm } from "@/components/demo/BookDemoForm";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { DataRainBackground } from "@/components/visual/DataRainBackground";

export default function BookDemoPage() {
  return (
    <main className="relative overflow-hidden">
      <DataRainBackground className="opacity-16" />
      <Navigation />
      <BookDemoForm />
      <Footer />
    </main>
  );
}
