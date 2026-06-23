"use client";

import { useState } from "react";

export function CopyableCode({ code, label = "Copy" }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="relative">
      <button
        className="absolute right-3 top-3 border border-silver/18 bg-[var(--afternum-bg-panel)] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-mist/58 transition hover:border-silver/42 hover:text-white"
        onClick={copy}
        type="button"
      >
        {copied ? "Copied" : label}
      </button>
      <pre className="overflow-x-auto border border-silver/14 bg-white/[0.025] p-4 pr-24 text-xs leading-6 text-mist/74">
        <code>{code}</code>
      </pre>
    </div>
  );
}
