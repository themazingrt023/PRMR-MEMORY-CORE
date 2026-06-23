"use client";

import Image from "next/image";
import { useState } from "react";

type LogoSize = "nav" | "hero" | "heroFull" | "footer" | "mark";

const sizeMap: Record<LogoSize, { width: number; height: number; className: string }> = {
  nav: { width: 34, height: 34, className: "h-9 w-9" },
  hero: { width: 180, height: 180, className: "h-32 w-32 sm:h-40 sm:w-40 lg:h-48 lg:w-48" },
  heroFull: { width: 360, height: 360, className: "h-56 w-56 sm:h-64 sm:w-64 lg:h-72 lg:w-72" },
  footer: { width: 84, height: 84, className: "h-20 w-20" },
  mark: { width: 26, height: 26, className: "h-7 w-7" }
};

export function AfternumLogo({
  size = "mark",
  priority = false,
  className = ""
}: {
  size?: LogoSize;
  priority?: boolean;
  className?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const config = sizeMap[size];

  if (imageFailed) {
    return (
      <span
        aria-label="Afternum Industries logo unavailable"
        className={`inline-flex items-center justify-center rounded-full border border-silver/40 bg-ink text-[10px] font-semibold tracking-[0.18em] text-silver ${config.className} ${className}`}
        role="img"
      >
        AI
      </span>
    );
  }

  return (
    <Image
      alt="Afternum Industries logo"
      className={`object-contain drop-shadow-[0_0_34px_rgba(232,238,245,0.24)] ${config.className} ${className}`}
      height={config.height}
      onError={() => setImageFailed(true)}
      priority={priority}
      src="/brand/afternum-logo.png"
      width={config.width}
    />
  );
}
