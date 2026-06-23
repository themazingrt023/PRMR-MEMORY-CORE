import type { ReactNode } from "react";

export function LabFrame({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`panel relative overflow-hidden rounded-none ${className}`}>
      <div className="pointer-events-none absolute left-0 top-0 h-8 w-8 border-l border-t border-silver/45" />
      <div className="pointer-events-none absolute right-0 top-0 h-8 w-8 border-r border-t border-silver/28" />
      <div className="pointer-events-none absolute bottom-0 left-0 h-8 w-8 border-b border-l border-silver/22" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-8 w-8 border-b border-r border-silver/45" />
      {children}
    </div>
  );
}
