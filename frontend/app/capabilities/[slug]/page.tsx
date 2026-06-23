import Link from "next/link";
import { notFound } from "next/navigation";
import { AfternumMark } from "@/components/brand/AfternumMark";
import { capabilities, getCapability } from "@/data/capabilities";
import { boundaryStatement } from "@/data/evidence";

export function generateStaticParams() {
  return capabilities.map((capability) => ({ slug: capability.slug }));
}

export default async function CapabilityDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const capability = getCapability(slug);
  if (!capability) notFound();

  const index = capabilities.findIndex((item) => item.slug === slug);
  const previous = capabilities[index - 1] || null;
  const next = capabilities[index + 1] || null;

  return (
    <main className="min-h-screen bg-[var(--afternum-bg)] text-mist">
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-white/[0.06] bg-[var(--afternum-bg)] backdrop-blur-md">
        <nav className="mx-auto flex h-20 max-w-[1400px] items-center justify-between px-[5vw]">
          <Link className="flex items-center gap-3" href="/#capabilities" aria-label="Back to PRMR capabilities">
            <AfternumMark size="nav" />
            <span className="font-mono text-lg uppercase tracking-[-0.03em] text-mist">AFTERNUM</span>
          </Link>
          <Link className="nav-link" href="/#capabilities">
            Back to capabilities
          </Link>
        </nav>
      </header>

      <section className="mx-auto max-w-[920px] px-[5vw] pb-20 pt-44">
        <p className="kimi-section-label">Capability</p>
        <h1 className="mt-8 font-display text-[clamp(46px,6vw,86px)] leading-[1.05] text-white">
          {capability.title}
        </h1>
        <p className="mt-8 max-w-2xl text-lg font-extralight leading-9 text-mist/74">{capability.preview}</p>
      </section>

      <div className="mx-auto max-w-[920px] px-[5vw]">
        <div className="h-px w-full bg-white/[0.08]" />
      </div>

      <article className="mx-auto max-w-[920px] px-[5vw] py-20">
        {capability.deeper.map((paragraph) => (
          <p className="mb-8 text-base font-extralight leading-9 text-mist/72 last:mb-0" key={paragraph}>
            {paragraph}
          </p>
        ))}
        <p className="mt-12 border-l border-white/10 pl-5 text-sm leading-7 text-mist/48">{boundaryStatement}</p>
      </article>

      <nav className="mx-auto grid max-w-[920px] gap-6 px-[5vw] pb-28 md:grid-cols-2">
        {previous ? (
          <Link className="silver-hover border border-white/[0.08] p-5" href={`/capabilities/${previous.slug}`}>
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist/36">Previous</span>
            <p className="mt-3 font-display text-2xl text-white">{previous.title}</p>
          </Link>
        ) : (
          <div />
        )}
        {next ? (
          <Link className="silver-hover border border-white/[0.08] p-5 text-left md:text-right" href={`/capabilities/${next.slug}`}>
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist/36">Next</span>
            <p className="mt-3 font-display text-2xl text-white">{next.title}</p>
          </Link>
        ) : (
          <div />
        )}
      </nav>
    </main>
  );
}
