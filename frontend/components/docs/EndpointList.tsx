import { endpoints } from "@/data/apiDocs";
import { CopyableCode } from "@/components/docs/CopyableCode";

export function EndpointList() {
  return (
    <section id="endpoints" className="panel mt-8 p-8 md:p-10">
      <p className="font-mono text-xs uppercase tracking-[0.24em] text-silver/58">Endpoint reference</p>
      <h2 className="mt-3 font-display text-4xl text-silver">Controlled-alpha API shape</h2>
      <p className="mt-4 max-w-3xl text-sm leading-7 text-mist/62">
        These endpoints come from the V0.52.0 alpha contract. They describe the intended controlled-alpha API shape,
        not a hosted production service.
      </p>
      <div className="mt-8 grid gap-5">
        {endpoints.map((endpoint) => (
          <article className="silver-hover border border-silver/12 p-5" key={`${endpoint.method} ${endpoint.path}`}>
            <div className="flex flex-col gap-3 md:flex-row md:items-baseline md:justify-between">
              <h3 className="font-display text-2xl text-white">
                <span className="font-mono text-sm text-silver/64">{endpoint.method}</span> {endpoint.path}
              </h3>
              <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-mist/36">Public-safe examples</span>
            </div>
            <p className="mt-3 text-sm leading-7 text-mist/66">{endpoint.purpose}</p>
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div>
                <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.2em] text-silver/54">Sample request</p>
                <CopyableCode code={endpoint.request} />
              </div>
              <div>
                <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.2em] text-silver/54">Sample response</p>
                <CopyableCode code={endpoint.response} />
              </div>
            </div>
            <p className="mt-4 border-l border-silver/18 pl-4 text-xs leading-6 text-mist/52">{endpoint.boundary}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
