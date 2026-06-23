import json
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from prmr_api import app


APP_DASHBOARD_VERSION = "0.32"


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_recent_run_logs(limit=20):
    logs_folder = Path("logs")

    if not logs_folder.exists():
        return []

    log_files = list(logs_folder.glob("*.json"))
    log_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    runs = []

    for path in log_files[:limit]:
        try:
            log = read_json_file(path)

            runs.append({
                "run_id": log.get("run_id"),
                "timestamp": log.get("timestamp"),
                "client_id": log.get("client_id"),
                "client_name": log.get("client_name"),
                "vault_id": log.get("vault_id"),
                "namespace": log.get("namespace"),
                "public_report_path": log.get("public_report_path"),
                "dataset_count": log.get("summary", {}).get("dataset_count"),
                "all_reconstructions_verified": log.get("summary", {}).get("all_reconstructions_verified")
            })
        except Exception:
            continue

    return runs


def is_safe_public_report_path(path):
    if not path:
        return False

    normalised = path.replace("\\", "/")

    if not normalised.startswith("reports/"):
        return False

    if "private" in normalised.lower():
        return False

    if "internal" in normalised.lower():
        return False

    if not normalised.endswith("_public.json"):
        return False

    return True


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Memory Core Dashboard</title>
        <style>
            :root {
                --bg: #050505;
                --panel: #0e0e0e;
                --panel-2: #151515;
                --border: #5f5f5f;
                --border-soft: #303030;
                --text: #f3f3f3;
                --muted: #b5b5b5;
                --silver: #c0c0c0;
                --silver-2: #8f8f8f;
                --highlight: #e7e7e7;
                --good: #ffffff;
                --shadow: rgba(255,255,255,0.06);
            }

            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                background:
                    radial-gradient(circle at top, #111111 0%, #050505 48%),
                    #050505;
                color: var(--text);
                font-family: Arial, sans-serif;
                padding: 28px;
            }

            .shell {
                max-width: 1200px;
                margin: 0 auto;
            }

            .header {
                background: linear-gradient(135deg, #101010, #060606);
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 26px;
                margin-bottom: 22px;
                box-shadow: 0 10px 30px var(--shadow);
            }

            h1 {
                margin: 0;
                font-size: 34px;
                letter-spacing: 0.5px;
                color: #ffffff;
            }

            .sub {
                color: var(--muted);
                margin-top: 10px;
                font-size: 15px;
            }

            .warning {
                margin-top: 12px;
                color: var(--silver);
                font-size: 13px;
            }

            .grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 14px;
                margin-bottom: 22px;
            }

            .card {
                background: linear-gradient(180deg, var(--panel), var(--panel-2));
                border: 1px solid var(--border-soft);
                border-radius: 16px;
                padding: 18px;
                box-shadow: 0 8px 24px var(--shadow);
            }

            .label {
                color: var(--muted);
                font-size: 13px;
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }

            .value {
                font-size: 20px;
                font-weight: bold;
                color: #ffffff;
            }

            .good {
                color: var(--good);
            }

            .section {
                background: linear-gradient(180deg, var(--panel), var(--panel-2));
                border: 1px solid var(--border-soft);
                border-radius: 18px;
                padding: 18px;
                box-shadow: 0 8px 24px var(--shadow);
                margin-bottom: 22px;
            }

            .section h2 {
                margin-top: 0;
                margin-bottom: 14px;
                color: #ffffff;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                overflow: hidden;
                border-radius: 12px;
                border: 1px solid var(--border-soft);
            }

            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #262626;
                font-size: 14px;
            }

            th {
                background: #1a1a1a;
                color: #ffffff;
            }

            td {
                background: #0d0d0d;
                color: #e9e9e9;
            }

            tr:hover td {
                background: #141414;
            }

            button {
                background: linear-gradient(180deg, #d9d9d9, #a8a8a8);
                color: #050505;
                border: 1px solid #d0d0d0;
                border-radius: 10px;
                padding: 8px 12px;
                cursor: pointer;
                font-weight: bold;
            }

            button:hover {
                filter: brightness(1.06);
            }

            pre {
                white-space: pre-wrap;
                background: #080808;
                border: 1px solid var(--border-soft);
                border-radius: 14px;
                padding: 16px;
                color: #e7e7e7;
                max-height: 460px;
                overflow: auto;
                line-height: 1.45;
            }

            .footer-note {
                color: var(--muted);
                font-size: 12px;
                margin-top: 8px;
            }

            @media (max-width: 1000px) {
                .grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }

            @media (max-width: 640px) {
                .grid {
                    grid-template-columns: 1fr;
                }

                body {
                    padding: 16px;
                }
            }
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="header">
                <h1>PRMR Memory Core Dashboard</h1>
                <div class="sub">Afternum Industries · Local Dashboard Alpha · V0.32</div>
                <div class="warning">
                    Public-safe dashboard only. Private internal reports, compressed packages, rule data, and protected mechanisms are not displayed.
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="label">API Status</div>
                    <div class="value good" id="apiStatus">Checking...</div>
                </div>
                <div class="card">
                    <div class="label">Product</div>
                    <div class="value">PRMR Memory Core</div>
                </div>
                <div class="card">
                    <div class="label">Company</div>
                    <div class="value">Afternum Industries</div>
                </div>
                <div class="card">
                    <div class="label">Dashboard Version</div>
                    <div class="value">0.32</div>
                </div>
            </div>

            <div class="section">
                <h2>Recent Runs</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Client</th>
                            <th>Vault</th>
                            <th>Namespace</th>
                            <th>Datasets</th>
                            <th>Verified</th>
                            <th>Public Report</th>
                        </tr>
                    </thead>
                    <tbody id="runsTable">
                        <tr>
                            <td colspan="7">Loading...</td>
                        </tr>
                    </tbody>
                </table>
                <div class="footer-note">
                    Only public-safe run metadata is shown here.
                </div>
            </div>

            <div class="section">
                <h2>Public Report Preview</h2>
                <pre id="reportPreview">Select a public report.</pre>
            </div>
        </div>

        <script>
            async function loadStatus() {
                try {
                    const response = await fetch("/health");
                    const data = await response.json();
                    document.getElementById("apiStatus").innerText =
                        data.status + " · " + data.version;
                } catch (error) {
                    document.getElementById("apiStatus").innerText = "offline";
                }
            }

            async function loadRuns() {
                try {
                    const response = await fetch("/dashboard/api/runs");
                    const data = await response.json();

                    const table = document.getElementById("runsTable");
                    table.innerHTML = "";

                    if (!data.runs || data.runs.length === 0) {
                        table.innerHTML = "<tr><td colspan='7'>No runs found yet.</td></tr>";
                        return;
                    }

                    for (const run of data.runs) {
                        const row = document.createElement("tr");
                        const verified = run.all_reconstructions_verified ? "True" : "False";

                        row.innerHTML = `
                            <td>${run.run_id || ""}</td>
                            <td>${run.client_id || ""}</td>
                            <td>${run.vault_id || ""}</td>
                            <td>${run.namespace || ""}</td>
                            <td>${run.dataset_count ?? ""}</td>
                            <td>${verified}</td>
                            <td><button onclick="loadPublicReport('${run.run_id}')">View</button></td>
                        `;

                        table.appendChild(row);
                    }
                } catch (error) {
                    const table = document.getElementById("runsTable");
                    table.innerHTML = "<tr><td colspan='7'>Could not load recent runs.</td></tr>";
                }
            }

            async function loadPublicReport(runId) {
                const preview = document.getElementById("reportPreview");

                try {
                    const response = await fetch("/dashboard/api/public-report/" + runId);

                    if (!response.ok) {
                        preview.innerText = "Could not load public report.";
                        return;
                    }

                    const data = await response.json();
                    preview.innerText = JSON.stringify(data, null, 2);
                } catch (error) {
                    preview.innerText = "Could not load public report.";
                }
            }

            loadStatus();
            loadRuns();

            setInterval(loadStatus, 5000);
            setInterval(loadRuns, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/dashboard/api/runs", include_in_schema=False)
def dashboard_runs():
    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "dashboard_version": APP_DASHBOARD_VERSION,
        "runs": get_recent_run_logs()
    }


@app.get("/dashboard/api/public-report/{run_id}", include_in_schema=False)
def dashboard_public_report(run_id: str):
    runs = get_recent_run_logs(limit=100)

    selected_run = None

    for run in runs:
        if run.get("run_id") == run_id:
            selected_run = run
            break

    if selected_run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found."
        )

    public_report_path = selected_run.get("public_report_path")

    if not is_safe_public_report_path(public_report_path):
        raise HTTPException(
            status_code=403,
            detail="This report path is not public-safe."
        )

    if not os.path.exists(public_report_path):
        raise HTTPException(
            status_code=404,
            detail="Public report file not found."
        )

    return read_json_file(public_report_path)