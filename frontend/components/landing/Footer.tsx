import { AfternumMark } from "@/components/brand/AfternumMark";
import { boundaryStatement } from "@/data/evidence";

export function Footer() {
  return (
    <footer id="footer" className="relative border-t border-white/10 bg-[var(--afternum-bg-section)] px-[5vw] py-24 text-sm text-mist/54">
      <div className="mx-auto max-w-[1400px]">
        <div className="grid gap-16 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <AfternumMark size="footer" />
            <h2 className="mt-8 font-display text-[clamp(34px,4.2vw,64px)] leading-tight text-white">
              PRMR Memory Core
            </h2>
            <p className="mt-5 max-w-2xl text-lg font-extralight leading-8 text-mist/66">
              Continuity infrastructure for intelligent systems.
            </p>
          </div>

          <div className="grid gap-10 md:grid-cols-2">
            <div>
              <p className="kimi-section-label mb-5">Product</p>
              <div className="flex flex-col gap-3 font-mono text-xs uppercase tracking-[0.18em]">
                <a href="/demo">Demo</a>
                <a href="/#access">Alpha</a>
                <a href="/docs">Docs</a>
              </div>
            </div>
            <div>
              <p className="kimi-section-label mb-5">Company</p>
              <div className="flex flex-col gap-3 font-mono text-xs uppercase tracking-[0.18em]">
                <a href="/contact">Contact</a>
                <a href="/#evidence">Evidence</a>
                <a href="/#use-cases">Use Cases</a>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-20 border-t border-white/[0.06] pt-6">
          <div className="grid gap-4 md:grid-cols-[0.7fr_1.3fr]">
            <p className="text-xs text-mist/42">Copyright 2026. Local controlled-alpha frontend shell.</p>
            <p className="text-xs leading-5 text-mist/42">{boundaryStatement}</p>
          </div>
          <p className="mt-4 max-w-4xl text-xs leading-5 text-mist/34">
            No hosted service, deployment readiness, banking sign-off, regulatory sign-off, legal sign-off, third-party
            security sign-off, or field validation is asserted by this local shell.
          </p>
          <p className="mt-4 max-w-4xl text-xs leading-5 text-mist/42">
            PRMR Memory Core is not an AI model. It is a continuity infrastructure layer that helps systems preserve useful state over time.
          </p>
        </div>
      </div>
    </footer>
  );
}
