import { versionTimeline } from "@/data/apiDocs";

export function VersionTimeline() {
  return (
    <section id="evidence" className="panel mt-8 p-8 md:p-10">
      <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Internal/local evidence</p>
      <h2 className="mt-3 font-display text-3xl text-silver">Version timeline</h2>
      <ul className="mt-4 space-y-2 text-sm text-mist/72">
        {versionTimeline.map((item) => (
          <li className="border-l border-silver/24 pl-3" key={item}>
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}
