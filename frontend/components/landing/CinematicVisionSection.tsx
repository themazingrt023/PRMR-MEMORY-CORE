import { KimiSectionShell } from "@/components/visual/KimiSectionShell";

export function CinematicVisionSection() {
  return (
    <KimiSectionShell id="architecture" eyebrow="Architecture" title="Storage remembers data. PRMR remembers change.">
      <div className="relative">
        <div className="relative mx-auto aspect-[21/9] max-w-[80vw] overflow-hidden border border-white/10 bg-white/[0.025]">
          <video
            aria-label="Abstract continuity architecture visual"
            autoPlay
            className="h-full w-full object-cover opacity-58 grayscale"
            loop
            muted
            playsInline
            src="/videos/cinematic-vision.mp4"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-ink/50 via-transparent to-ink/20" />
        </div>
        <div className="mt-32 grid gap-16 md:grid-cols-2 md:items-center">
          <h3 className="font-display text-[clamp(32px,4vw,64px)] leading-[1.15] text-white">
            Continuity packets preserve change without replaying every raw event.
          </h3>
          <p className="text-lg font-extralight leading-9 text-mist/72">
            Traditional systems can keep records while losing transformation. PRMR keeps a smaller,
            safer continuity layer: current state, active signals, stale signals, review boundaries,
            and public-safe explanation surfaces.
          </p>
        </div>
      </div>
    </KimiSectionShell>
  );
}
