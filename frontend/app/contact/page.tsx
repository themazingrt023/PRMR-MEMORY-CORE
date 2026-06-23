import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";
import { LabFrame } from "@/components/visual/LabFrame";
import { boundaryStatement } from "@/data/evidence";

export default function ContactPage() {
  return (
    <main className="relative overflow-hidden">
      <Navigation />
      <div className="mx-auto max-w-3xl px-6 pb-24 pt-32">
        <LabFrame className="p-8">
          <p className="font-mono text-sm uppercase tracking-[0.28em] text-silver/68">Afternum Industries</p>
          <h1 className="mt-3 font-display text-4xl text-mist">Contact</h1>
          <p className="mt-4 text-sm leading-6 text-mist/75">
            Use this placeholder route for controlled-alpha inquiries, demo review, and technical evaluation
            conversations. This shell does not submit data to an external service.
          </p>
          <div className="mt-6 border border-silver/18 p-4 text-sm text-mist/70">
            {boundaryStatement}
          </div>
        </LabFrame>
      </div>
      <Footer />
    </main>
  );
}
