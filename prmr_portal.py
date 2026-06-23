import json
from pathlib import Path

from fastapi.responses import HTMLResponse

from prmr_dashboard import app


APP_PORTAL_VERSION = "0.33"


PLANS = [
    {
        "name": "Private Beta",
        "price": "Invite Only",
        "description": "Manual access for early trusted testers.",
        "features": [
            "1 local API key",
            "1 vault",
            "Default namespace",
            "Limited runs",
            "Public-safe reports"
        ]
    },
    {
        "name": "Developer",
        "price": "£29/mo",
        "description": "For solo builders testing PRMR Memory Core.",
        "features": [
            "1 API key",
            "1 vault",
            "10 namespaces",
            "1,000 runs/month",
            "Basic dashboard"
        ]
    },
    {
        "name": "Builder",
        "price": "£99/mo",
        "description": "For small AI apps, tools, and prototypes.",
        "features": [
            "3 API keys",
            "5 vaults",
            "50 namespaces",
            "10,000 runs/month",
            "Report history"
        ]
    },
    {
        "name": "Startup",
        "price": "£299/mo",
        "description": "For early companies building memory-heavy systems.",
        "features": [
            "10 API keys",
            "20 vaults",
            "250 namespaces",
            "100,000 runs/month",
            "Priority support"
        ]
    },
    {
        "name": "Enterprise Pilot",
        "price": "Custom",
        "description": "For serious AI, research, and company-memory pilots.",
        "features": [
            "Custom vaults",
            "Security review",
            "Dedicated integration",
            "Private deployment options",
            "Benchmarking support"
        ]
    }
]


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_run_logs(limit=100):
    logs_folder = Path("logs")

    if not logs_folder.exists():
        return []

    log_files = list(logs_folder.glob("*.json"))
    log_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    logs = []

    for path in log_files[:limit]:
        try:
            logs.append(read_json_file(path))
        except Exception:
            continue

    return logs


def build_usage_summary(client_id="local_dev_client"):
    logs = get_run_logs(limit=500)

    client_logs = [
        log for log in logs
        if log.get("client_id") == client_id
    ]

    total_runs = len(client_logs)
    verified_runs = 0
    dataset_total = 0
    last_run_time = None

    for log in client_logs:
        summary = log.get("summary", {})

        if summary.get("all_reconstructions_verified") is True:
            verified_runs += 1

        dataset_total += summary.get("dataset_count", 0)

    if client_logs:
        last_run_time = client_logs[0].get("timestamp")

    return {
        "client_id": client_id,
        "plan": "Private Beta / Local Dev",
        "runs_total": total_runs,
        "verified_runs": verified_runs,
        "datasets_processed": dataset_total,
        "last_run_time": last_run_time
    }


@app.get("/portal", response_class=HTMLResponse, include_in_schema=False)
def portal_home():
    example_payload = {
        "datasets": [
            {
                "name": "client_memory_demo",
                "description": "Small client-facing continuity test dataset.",
                "rows": [
                    {
                        "event_id": 1,
                        "system": "Client AI Assistant",
                        "memory_state": "origin",
                        "priority": 1,
                        "status": "draft"
                    },
                    {
                        "event_id": 2,
                        "system": "Client AI Assistant",
                        "memory_state": "expanded",
                        "priority": 2,
                        "status": "review"
                    },
                    {
                        "event_id": 3,
                        "system": "Client AI Assistant",
                        "memory_state": "verified",
                        "priority": 3,
                        "status": "approved"
                    }
                ]
            }
        ]
    }

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Memory Core Portal</title>
        <style>
            :root {{
                --bg: #050505;
                --panel: #0e0e0e;
                --panel2: #151515;
                --border: #3a3a3a;
                --silver: #c0c0c0;
                --muted: #a8a8a8;
                --text: #f4f4f4;
                --white: #ffffff;
            }}

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: radial-gradient(circle at top, #151515 0%, #050505 50%);
                color: var(--text);
                font-family: Arial, sans-serif;
                padding: 28px;
            }}

            .shell {{
                max-width: 1240px;
                margin: 0 auto;
            }}

            .hero {{
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 28px;
                background: linear-gradient(135deg, #101010, #060606);
                margin-bottom: 20px;
            }}

            h1 {{
                margin: 0;
                font-size: 36px;
                color: var(--white);
            }}

            .sub {{
                color: var(--muted);
                margin-top: 10px;
            }}

            .tag {{
                display: inline-block;
                margin-top: 14px;
                border: 1px solid var(--silver);
                color: var(--silver);
                padding: 7px 10px;
                border-radius: 999px;
                font-size: 13px;
            }}

            .grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 14px;
                margin-bottom: 20px;
            }}

            .two {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 18px;
                margin-bottom: 20px;
            }}

            .card, .section {{
                border: 1px solid var(--border);
                border-radius: 18px;
                background: linear-gradient(180deg, var(--panel), var(--panel2));
                padding: 18px;
            }}

            .label {{
                color: var(--muted);
                text-transform: uppercase;
                letter-spacing: 0.8px;
                font-size: 12px;
                margin-bottom: 8px;
            }}

            .value {{
                font-size: 18px;
                font-weight: bold;
                color: var(--white);
                word-break: break-word;
            }}

            textarea {{
                width: 100%;
                height: 330px;
                background: #070707;
                color: #f2f2f2;
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 14px;
                font-family: Consolas, monospace;
                font-size: 13px;
                resize: vertical;
            }}

            pre {{
                background: #070707;
                color: #f2f2f2;
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 14px;
                min-height: 330px;
                max-height: 520px;
                overflow: auto;
                white-space: pre-wrap;
                font-family: Consolas, monospace;
                font-size: 13px;
            }}

            button {{
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                border: 1px solid #e2e2e2;
                border-radius: 12px;
                padding: 11px 16px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 12px;
            }}

            button:hover {{
                filter: brightness(1.06);
            }}

            .plans {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 12px;
            }}

            .plan h3 {{
                margin-top: 0;
                color: #ffffff;
            }}

            .price {{
                font-size: 22px;
                font-weight: bold;
                margin-bottom: 8px;
                color: var(--silver);
            }}

            ul {{
                padding-left: 18px;
                color: #dfdfdf;
            }}

            li {{
                margin-bottom: 6px;
            }}

            .notice {{
                color: var(--muted);
                font-size: 13px;
                margin-top: 10px;
            }}

            .danger {{
                color: #d8d8d8;
                font-size: 13px;
                border-top: 1px solid var(--border);
                margin-top: 14px;
                padding-top: 12px;
            }}

            @media (max-width: 1100px) {{
                .grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}

                .two {{
                    grid-template-columns: 1fr;
                }}

                .plans {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="shell">
            <div class="hero">
                <h1>PRMR Memory Core Portal</h1>
                <div class="sub">Afternum Industries · Client Portal Alpha · V0.33</div>
                <div class="tag">Continuity infrastructure for intelligent systems</div>
                <div class="danger">
                    Local/private alpha. Public-safe output only. Private internal reports, compressed packages, rule data, and protected mechanisms are not displayed.
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="label">Current Plan</div>
                    <div class="value" id="plan">Loading...</div>
                </div>

                <div class="card">
                    <div class="label">API Key</div>
                    <div class="value">prmr_local_dev_key_v031</div>
                </div>

                <div class="card">
                    <div class="label">Vault</div>
                    <div class="value">default_vault</div>
                </div>

                <div class="card">
                    <div class="label">Namespace</div>
                    <div class="value">default</div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="label">Runs Total</div>
                    <div class="value" id="runsTotal">Loading...</div>
                </div>

                <div class="card">
                    <div class="label">Verified Runs</div>
                    <div class="value" id="verifiedRuns">Loading...</div>
                </div>

                <div class="card">
                    <div class="label">Datasets Processed</div>
                    <div class="value" id="datasetsProcessed">Loading...</div>
                </div>

                <div class="card">
                    <div class="label">Last Run</div>
                    <div class="value" id="lastRun">Loading...</div>
                </div>
            </div>

            <div class="two">
                <div class="section">
                    <h2>Run PRMR</h2>
                    <div class="notice">Paste JSON payload. This demo sends data through the local PRMR API using the local dev key.</div>
                    <textarea id="jsonInput">{json.dumps(example_payload, indent=4)}</textarea>
                    <button onclick="runPRMR()">Run PRMR Memory Core</button>
                </div>

                <div class="section">
                    <h2>Public-Safe Result</h2>
                    <pre id="resultBox">Run PRMR to see public-safe output.</pre>
                </div>
            </div>

            <div class="section">
                <h2>Plans</h2>
                <div class="plans" id="plansBox"></div>
                <div class="notice">
                    Pricing is planning-stage only. Real billing should come after deployment, legal/security review, real dataset benchmarks, and pilot validation.
                </div>
            </div>
        </div>

        <script>
            async function loadUsage() {{
                const response = await fetch("/portal/api/usage");
                const data = await response.json();

                document.getElementById("plan").innerText = data.plan;
                document.getElementById("runsTotal").innerText = data.runs_total;
                document.getElementById("verifiedRuns").innerText = data.verified_runs;
                document.getElementById("datasetsProcessed").innerText = data.datasets_processed;
                document.getElementById("lastRun").innerText = data.last_run_time || "None yet";
            }}

            async function loadPlans() {{
                const response = await fetch("/portal/api/plans");
                const data = await response.json();

                const box = document.getElementById("plansBox");
                box.innerHTML = "";

                for (const plan of data.plans) {{
                    const card = document.createElement("div");
                    card.className = "card plan";

                    let features = "";

                    for (const feature of plan.features) {{
                        features += `<li>${{feature}}</li>`;
                    }}

                    card.innerHTML = `
                        <h3>${{plan.name}}</h3>
                        <div class="price">${{plan.price}}</div>
                        <div class="notice">${{plan.description}}</div>
                        <ul>${{features}}</ul>
                    `;

                    box.appendChild(card);
                }}
            }}

            async function runPRMR() {{
                const resultBox = document.getElementById("resultBox");

                let payload;

                try {{
                    payload = JSON.parse(document.getElementById("jsonInput").value);
                }} catch (error) {{
                    resultBox.innerText = "Invalid JSON: " + error.message;
                    return;
                }}

                resultBox.innerText = "Running PRMR Memory Core...";

                try {{
                    const response = await fetch("/run", {{
                        method: "POST",
                        headers: {{
                            "Content-Type": "application/json",
                            "X-PRMR-API-Key": "prmr_local_dev_key_v031",
                            "X-PRMR-Vault-ID": "default_vault",
                            "X-PRMR-Namespace": "default"
                        }},
                        body: JSON.stringify(payload)
                    }});

                    const data = await response.json();

                    if (!response.ok) {{
                        resultBox.innerText = JSON.stringify(data, null, 2);
                        return;
                    }}

                    const safeOutput = {{
                        api_version: data.api_version,
                        company: data.company,
                        product: data.product,
                        public_safe: data.public_safe,
                        client_id: data.client_id,
                        vault_id: data.vault_id,
                        namespace: data.namespace,
                        run_id: data.run_id,
                        all_reconstructions_verified: data.all_reconstructions_verified,
                        public_report_path: data.public_report_path,
                        public_report: data.public_report
                    }};

                    resultBox.innerText = JSON.stringify(safeOutput, null, 2);
                    loadUsage();

                }} catch (error) {{
                    resultBox.innerText = "Request failed: " + error.message;
                }}
            }}

            loadUsage();
            loadPlans();

            setInterval(loadUsage, 5000);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/portal/api/usage", include_in_schema=False)
def portal_usage():
    return build_usage_summary()


@app.get("/portal/api/plans", include_in_schema=False)
def portal_plans():
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "portal_version": APP_PORTAL_VERSION,
        "plans": PLANS
    }