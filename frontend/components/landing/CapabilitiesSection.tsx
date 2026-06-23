import Image from "next/image";
import Link from "next/link";
import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { capabilities } from "@/data/capabilities";

export function CapabilitiesSection() {
  return (
    <KimiSectionShell id="capabilities" eyebrow="Capabilities">
      <div className="flex flex-col gap-24">
        {capabilities.map((capability, index) => (
          <Link
            aria-label={`Open capability detail for ${capability.title}`}
            className="silver-hover group grid cursor-pointer gap-10 border-y border-transparent py-2 md:grid-cols-[0.62fr_0.38fr]"
            href={`/capabilities/${capability.slug}`}
            key={capability.slug}
          >
            <div>
              <span className="font-mono text-xs text-mist/30">{String(index + 1).padStart(2, "0")}</span>
              <h2 className="mt-5 font-display text-[clamp(42px,5.5vw,86px)] leading-[1.04] text-white transition duration-500 group-hover:text-silver group-hover:drop-shadow-[0_0_22px_rgba(232,238,245,0.18)]">
                {capability.title}
              </h2>
            </div>
            <div className="relative min-h-36 overflow-hidden md:min-h-52">
              <p className="max-w-sm text-base font-extralight leading-8 text-mist/70 transition duration-300 group-hover:opacity-0">
                {capability.preview}
              </p>
              <div className="absolute inset-0 opacity-0 transition duration-500 group-hover:opacity-100">
                <Image alt="" className="h-full w-full object-cover opacity-70 grayscale transition duration-700 group-hover:scale-[1.03]" fill src={capability.image} />
                <div className="absolute inset-0 bg-gradient-to-t from-ink/70 via-transparent to-transparent" />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </KimiSectionShell>
  );
}
