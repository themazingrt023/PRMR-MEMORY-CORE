"use client";

import Image from "next/image";
import { useState } from "react";

type MarkSize = "nav" | "hero" | "footer" | "mark";

const sizeMap: Record<MarkSize, { width: number; height: number; className: string }> = {
  nav: { width: 46, height: 46, className: "h-12 w-12" },
  hero: { width: 280, height: 280, className: "h-52 w-52 sm:h-64 sm:w-64 lg:h-72 lg:w-72" },
  footer: { width: 104, height: 104, className: "h-24 w-24 sm:h-28 sm:w-28" },
  mark: { width: 30, height: 30, className: "h-8 w-8" }
};

export function AfternumMark({
  size = "mark",
  priority = false,
  className = ""
}: {
  size?: MarkSize;
  priority?: boolean;
  className?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const config = sizeMap[size];

  if (imageFailed) {
    return (
      <span
        aria-label="Afternum Industries mark unavailable"
        className={`inline-flex items-center justify-center rounded-full border border-silver/40 bg-ink text-[10px] font-semibold tracking-[0.18em] text-silver ${config.className} ${className}`}
        role="img"
      >
        A
      </span>
    );
  }

  return (
    <Image
      alt="Afternum Industries mark"
      className={`object-contain drop-shadow-[0_0_46px_rgba(232,238,245,0.34)] ${config.className} ${className}`}
      height={config.height}
      onError={() => setImageFailed(true)}
      priority={priority}
      src="/brand/afternum-mark.png"
      width={config.width}
    />
  );
}
