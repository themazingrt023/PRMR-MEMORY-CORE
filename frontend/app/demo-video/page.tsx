import Link from "next/link";
import { Footer } from "@/components/landing/Footer";
import { Navigation } from "@/components/landing/Navigation";

export default function DemoVideoPage() {
  return (
    <main className="min-h-screen bg-[var(--afternum-bg)] text-mist">
      <Navigation />
      <section className="mx-auto max-w-[1400px] px-[5vw] pb-24 pt-32">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Founder demo video</p>
        <h1 className="mt-5 max-w-4xl font-display text-[clamp(42px,5vw,82px)] leading-[1.05] text-white">
          PRMR Memory Core V0.56
        </h1>
        <p className="mt-6 max-w-3xl text-lg font-extralight leading-9 text-mist/68">
          Local rendered founder demo video. Synthetic/local controlled-alpha evidence only.
        </p>

        <div className="panel mt-12 p-4">
          <video
            className="aspect-video w-full bg-black"
            controls
            poster="/brand/afternum-logo.png"
            preload="metadata"
            src="/video/prmr_founder_demo_v056.mp4"
          >
            <track kind="captions" label="English" srcLang="en" />
          </video>
        </div>

        <div className="mt-8 flex flex-col gap-4 sm:flex-row">
          <a className="liquid-glass-btn" download href="/video/prmr_founder_demo_v056.mp4">
            Download MP4
          </a>
          <Link className="liquid-glass-btn" href="/demo">
            Open Local Demo
          </Link>
        </div>

        <p className="mt-8 max-w-4xl border-l border-white/10 pl-5 text-sm leading-7 text-mist/50">
          Boundary: this video is a local demo recording artifact only. It is not hosted production, not production
          readiness, not bank approval, not compliance approval, not legal approval, not external security
          certification, and not real-world validation.
        </p>
      </section>
      <Footer />
    </main>
  );
}
