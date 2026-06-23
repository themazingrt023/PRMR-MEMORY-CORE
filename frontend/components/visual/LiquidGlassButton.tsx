import type { ReactNode } from "react";

export function LiquidGlassButton({
  children,
  href,
  className = ""
}: {
  children: ReactNode;
  href: string;
  className?: string;
}) {
  return (
    <a className={`liquid-glass-btn ${className}`} href={href}>
      <span>{children}</span>
    </a>
  );
}
