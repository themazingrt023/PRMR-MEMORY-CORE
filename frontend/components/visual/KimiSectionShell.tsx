import type { ReactNode } from "react";
import { SilverDivider } from "@/components/visual/SilverDivider";

export function KimiSectionShell({
  id,
  eyebrow,
  title,
  children,
  className = ""
}: {
  id: string;
  eyebrow: string;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`relative bg-[var(--afternum-bg-section)] px-[5vw] py-[150px] ${className}`}>
      <div className="mx-auto max-w-[1400px]">
        <p className="kimi-section-label">{eyebrow}</p>
        <SilverDivider className="mt-6" />
        {title ? (
          <h2 className="mt-20 max-w-5xl font-display text-[clamp(32px,4vw,64px)] leading-[1.15] text-white">
            {title}
          </h2>
        ) : null}
        <div className="mt-16">{children}</div>
      </div>
    </section>
  );
}
