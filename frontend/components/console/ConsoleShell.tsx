import Link from "next/link";
import type { ReactNode } from "react";

const consoleNav = [
  ["Home", "/dashboard#home"],
  ["Playground", "/dashboard#playground"],
  ["Events", "/dashboard#events"],
  ["Packets", "/dashboard#packets"],
  ["Actors", "/dashboard#actors"],
  ["API Keys", "/dashboard#api-keys"],
  ["Usage", "/dashboard#usage"],
  ["Logs", "/dashboard#logs"],
  ["How to Use", "/dashboard#how-to-use"],
  ["Settings", "/dashboard#settings"]
];

export function ConsoleShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--afternum-bg)] text-mist lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="border-b border-white/10 bg-[#070707] p-5 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <Link className="flex items-center gap-3" href="/dashboard" aria-label="PRMR Console overview">
          <span className="grid h-9 w-9 place-items-center rounded-full border border-white/20 font-display text-white">A</span>
          <span className="font-mono text-xs uppercase tracking-[0.18em] text-white">Memory Core</span>
        </Link>
        <nav className="mt-8 grid gap-1" aria-label="PRMR developer console">
          {consoleNav.map(([label, href]) => (
            <Link className="border border-transparent px-3 py-3 text-sm text-mist/58 transition hover:border-white/12 hover:bg-white/[0.025] hover:text-white" href={href} key={href}>
              {label}
            </Link>
          ))}
          <a className="border border-transparent px-3 py-3 text-sm text-mist/58 transition hover:border-white/12 hover:bg-white/[0.025] hover:text-white" href="/docs" target="_blank" rel="noreferrer">
            Documentation ↗
          </a>
        </nav>
      </aside>
      <section className="min-w-0">
        <header className="sticky top-0 z-40 flex flex-col gap-3 border-b border-white/10 bg-[#090909]/92 px-6 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            <select className="field-input w-auto min-w-48" aria-label="Application">
              <option>My First Application</option>
            </select>
            <select className="field-input w-auto min-w-36" aria-label="Environment">
              <option>LIVE</option>
            </select>
          </div>
          <div className="flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/48">
            <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-white shadow-[0_0_14px_rgba(255,255,255,0.5)]" /> API status</span>
            <span>Account</span>
          </div>
        </header>
        {children}
      </section>
    </div>
  );
}
