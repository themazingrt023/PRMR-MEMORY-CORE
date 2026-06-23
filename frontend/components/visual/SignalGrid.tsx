export function SignalGrid({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div className="border border-silver/14 bg-white/[0.025] p-5" key={item.label}>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-silver/70">{item.label}</p>
          <p className="mt-3 text-sm leading-6 text-mist/72">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
