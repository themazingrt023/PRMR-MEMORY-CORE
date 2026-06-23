import type { ReactNode } from "react";
import { SilverDivider } from "@/components/visual/SilverDivider";

export function SectionShell({
  eyebrow,
  title,
  children,
  className = ""
}: {
  eyebrow: string;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`relative mx-auto max-w-[1400px] px-6 py-32 md:py-40 ${className}`}>
      <p className="text-xs uppercase tracking-[0.34em] text-mist/46">{eyebrow}</p>
      <SilverDivider className="mt-6" />
      {title ? <h2 className="mt-14 max-w-5xl font-display text-4xl leading-[1.12] text-mist md:text-6xl">{title}</h2> : null}
      <div className="mt-14">{children}</div>
    </section>
  );
}
