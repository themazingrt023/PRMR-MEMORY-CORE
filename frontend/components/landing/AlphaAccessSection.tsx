import { KimiSectionShell } from "@/components/visual/KimiSectionShell";
import { boundaryStatement } from "@/data/evidence";

const fields = ["Name", "Email", "Organisation", "Use case"];

export function AlphaAccessSection() {
  return (
    <KimiSectionShell id="access" eyebrow="Controlled Alpha" title="Request controlled alpha access.">
      <div className="mx-auto grid max-w-5xl gap-20 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-7">
          <p className="text-lg font-extralight leading-9 text-mist/74">
            This is a local frontend placeholder for controlled-alpha interest. It does not submit to a live service
            yet and does not issue credentials.
          </p>
          <p className="text-sm leading-7 text-mist/50">{boundaryStatement}</p>
          <p className="text-sm leading-7 text-mist/42">
            Use synthetic, anonymised, or explicitly approved data only.
          </p>
        </div>

        <form className="grid gap-0 border-y border-white/[0.09]">
          {fields.map((field) => (
            <label className="grid gap-3 border-b border-white/[0.06] py-5 font-mono text-[11px] uppercase tracking-[0.18em] text-mist/50 last:border-b-0" key={field}>
              {field}
              {field === "Use case" ? (
                <textarea
                  className="min-h-32 resize-none border border-silver/16 bg-transparent px-4 py-3 font-sans text-sm normal-case tracking-normal text-mist outline-none transition focus:border-silver/42"
                  placeholder="Describe the continuity problem you want to test"
                  readOnly
                />
              ) : (
                <input
                  className="border border-silver/16 bg-transparent px-4 py-3 font-sans text-sm normal-case tracking-normal text-mist outline-none transition focus:border-silver/42"
                  placeholder={field === "Email" ? "you@example.com" : field}
                  readOnly
                />
              )}
            </label>
          ))}
          <div className="pt-8">
            <button className="liquid-glass-btn" disabled type="button">
              Apply for Alpha Access
            </button>
            <p className="mt-5 text-xs leading-5 text-mist/40">
              Placeholder only. No backend connection, billing, authentication, or live service access.
            </p>
          </div>
        </form>
      </div>
    </KimiSectionShell>
  );
}
