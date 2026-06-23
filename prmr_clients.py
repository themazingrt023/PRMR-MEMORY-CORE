from fastapi import Header, HTTPException
from fastapi.responses import HTMLResponse

from prmr_portal import app

from prmr.security.access_layer import (
    create_client,
    list_clients,
    validate_admin_key
)


APP_CLIENTS_VERSION = "0.34"


@app.get("/clients", response_class=HTMLResponse, include_in_schema=False)
def clients_home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Client Key Manager</title>
        <style>
            body {
                background: #050505;
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }

            .shell {
                max-width: 1050px;
                margin: 0 auto;
            }

            .hero, .card {
                border: 1px solid #444;
                border-radius: 18px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 22px;
                margin-bottom: 18px;
            }

            h1 {
                margin: 0;
                font-size: 34px;
            }

            .sub {
                color: #b8b8b8;
                margin-top: 8px;
            }

            .grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 18px;
            }

            label {
                display: block;
                color: #b8b8b8;
                font-size: 13px;
                margin-top: 12px;
                margin-bottom: 6px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }

            input, select {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #444;
                background: #070707;
                color: #f5f5f5;
            }

            button {
                margin-top: 16px;
                padding: 12px 16px;
                border-radius: 10px;
                border: 1px solid #ddd;
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                font-weight: bold;
                cursor: pointer;
            }

            pre {
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 14px;
                white-space: pre-wrap;
                min-height: 250px;
                overflow: auto;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 14px;
            }

            th, td {
                border-bottom: 1px solid #333;
                padding: 10px;
                text-align: left;
                font-size: 14px;
            }

            th {
                background: #1a1a1a;
            }

            td {
                background: #0d0d0d;
            }

            .notice {
                color: #b8b8b8;
                font-size: 13px;
                margin-top: 10px;
            }
        </style>
    </head>

    <body>
        <div class="shell">
            <div class="hero">
                <h1>PRMR Client Key Manager</h1>
                <div class="sub">Afternum Industries · API Key Generation Alpha · V0.34</div>
                <div class="notice">
                    Local alpha only. This creates local test clients and API keys. No real billing yet.
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <h2>Create Client API Key</h2>

                    <label>Admin Key</label>
                    <input id="adminKey" value="prmr_local_admin_key_v034">

                    <label>Client Name</label>
                    <input id="clientName" value="Test Client Ltd">

                    <label>Plan</label>
                    <select id="plan">
                        <option value="private_beta">Private Beta</option>
                        <option value="developer">Developer</option>
                        <option value="builder">Builder</option>
                        <option value="startup">Startup</option>
                        <option value="enterprise_pilot">Enterprise Pilot</option>
                    </select>

                    <label>Vault ID</label>
                    <input id="vaultId" value="test_client_vault">

                    <button onclick="createClient()">Create API Key</button>

                    <div class="notice">
                        Copy the generated API key. In a real product this would be shown once.
                    </div>
                </div>

                <div class="card">
                    <h2>Created Key Output</h2>
                    <pre id="createdOutput">No key created yet.</pre>
                </div>
            </div>

            <div class="card">
                <h2>Clients</h2>
                <button onclick="loadClients()">Refresh Clients</button>

                <table>
                    <thead>
                        <tr>
                            <th>Client ID</th>
                            <th>Name</th>
                            <th>Plan</th>
                            <th>Status</th>
                            <th>Vaults</th>
                        </tr>
                    </thead>
                    <tbody id="clientsTable">
                        <tr><td colspan="5">Loading clients...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function createClient() {
                const output = document.getElementById("createdOutput");

                const payload = {
                    client_name: document.getElementById("clientName").value,
                    plan: document.getElementById("plan").value,
                    vault_id: document.getElementById("vaultId").value
                };

                try {
                    const response = await fetch("/clients/api/create", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-PRMR-Admin-Key": document.getElementById("adminKey").value
                        },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();
                    output.innerText = JSON.stringify(data, null, 2);

                    await loadClients();

                } catch (error) {
                    output.innerText = "Request failed: " + error.message;
                }
            }

            async function loadClients() {
                const table = document.getElementById("clientsTable");

                try {
                    const response = await fetch("/clients/api/list", {
                        method: "GET",
                        headers: {
                            "X-PRMR-Admin-Key": document.getElementById("adminKey").value
                        }
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        table.innerHTML = "<tr><td colspan='5'>" + JSON.stringify(data) + "</td></tr>";
                        return;
                    }

                    table.innerHTML = "";

                    for (const client of data.clients) {
                        const row = document.createElement("tr");

                        row.innerHTML = `
                            <td>${client.client_id}</td>
                            <td>${client.client_name}</td>
                            <td>${client.plan}</td>
                            <td>${client.status}</td>
                            <td>${client.allowed_vaults.join(", ")}</td>
                        `;

                        table.appendChild(row);
                    }

                } catch (error) {
                    table.innerHTML = "<tr><td colspan='5'>Could not load clients.</td></tr>";
                }
            }

            loadClients();
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.post("/clients/api/create", include_in_schema=False)
def clients_create(payload: dict, x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    try:
        client = create_client(
            client_name=payload.get("client_name", ""),
            plan=payload.get("plan", "private_beta"),
            vault_id=payload.get("vault_id")
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": APP_CLIENTS_VERSION,
        "created": True,
        "client": client,
        "important": "Store this API key securely. Do not expose it publicly."
    }


@app.get("/clients/api/list", include_in_schema=False)
def clients_list(x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": APP_CLIENTS_VERSION,
        "public_safe": True,
        "clients": list_clients(public_safe=True)
    }


@app.get("/clients-test", response_class=HTMLResponse, include_in_schema=False)
def clients_test():
    return HTMLResponse("<h1>PRMR Clients Route Loaded</h1>")