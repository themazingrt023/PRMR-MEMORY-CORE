const nav = [
  "Overview",
  "Playground",
  "API Keys",
  "Applications",
  "Events",
  "Continuity Packets",
  "Request Logs",
  "Usage",
  "Billing",
  "Team",
  "Settings"
];

export default function ConsoleOverview() {
  return (
    <main className="console">
      <aside className="sidebar">
        <div className="brand">
          <span className="mark">A</span>
          <span>PRMR Console</span>
        </div>
        <nav className="nav" aria-label="Console">
          {nav.map((item) => (
            <a href={item === "Documentation" ? "https://afternumindustries.co.uk/docs" : `#${item.toLowerCase().replaceAll(" ", "-")}`} key={item} data-active={item === "Overview"}>
              {item}
            </a>
          ))}
          <a href="https://afternumindustries.co.uk/docs" target="_blank" rel="noreferrer">Documentation ↗</a>
        </nav>
      </aside>
      <section className="main">
        <header className="topbar">
          <div className="selectors">
            <select aria-label="Organisation">
              <option>Afternum Workspace</option>
            </select>
            <select aria-label="Application">
              <option>My First Application</option>
            </select>
            <select aria-label="Environment">
              <option>Sandbox</option>
              <option>Production</option>
            </select>
          </div>
          <div className="status"><span className="dot" /> API reachable</div>
        </header>
        <div className="content">
          <p className="eyebrow">Overview</p>
          <h1>Developer console</h1>
          <section className="grid">
            <Card label="Current application" value="My First Application" />
            <Card label="Environment" value="Sandbox" />
            <Card label="Requests used" value="0" />
            <Card label="Requests remaining" value="100" />
            <Card label="Latest event" value="No events yet" />
            <Card label="Latest packet" value="No packet yet" />
            <Card label="Recent errors" value="None" />
            <Card label="Billing" value="Free / billing not live" />
            <article className="card wide">
              <p className="eyebrow">First-run progress</p>
              <p>Activate account, copy one server-side key, send one event, generate one continuity packet.</p>
            </article>
            <article className="card wide">
              <p className="eyebrow">Quickstart</p>
              <p>Use `Authorization: Bearer &lt;PRMR_API_KEY&gt;`, then call `/v1/events/ingest` and `/v1/continuity/packet`.</p>
            </article>
          </section>
        </div>
      </section>
    </main>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <article className="card">
      <p className="eyebrow">{label}</p>
      <strong>{value}</strong>
    </article>
  );
}
