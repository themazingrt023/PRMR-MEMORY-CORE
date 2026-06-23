import json
import os
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from prmr.security.access_layer import (
    create_client,
    validate_admin_key
)


APP_VERSION = "0.35"
REQUEST_FILE = "data/onboarding_requests_v035.json"


app = FastAPI(
    title="PRMR Memory Core Onboarding",
    description="Professional client onboarding alpha for PRMR Memory Core.",
    version=APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_data_file():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(REQUEST_FILE):
        with open(REQUEST_FILE, "w", encoding="utf-8") as file:
            json.dump({"requests": []}, file, indent=4)


def load_requests():
    ensure_data_file()

    with open(REQUEST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_requests(data):
    os.makedirs("data", exist_ok=True)

    with open(REQUEST_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def find_request(request_id):
    data = load_requests()

    for item in data.get("requests", []):
        if item.get("request_id") == request_id:
            return item

    return None


def mask_key(api_key):
    if not api_key:
        return None

    if len(api_key) <= 12:
        return "••••"

    return api_key[:8] + "••••••••••••••••" + api_key[-6:]


def public_request_view(item):
    approved_client = item.get("approved_client")

    return {
        "request_id": item.get("request_id"),
        "company_name": item.get("company_name"),
        "contact_name": item.get("contact_name"),
        "email": item.get("email"),
        "use_case": item.get("use_case"),
        "requested_plan": item.get("requested_plan"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "approved_at": item.get("approved_at"),
        "client_id": approved_client.get("client_id") if approved_client else None,
        "vault_id": approved_client.get("vault_id") if approved_client else None,
        "namespace": approved_client.get("namespace") if approved_client else None,
        "masked_api_key": mask_key(approved_client.get("api_key")) if approved_client else None
    }


def admin_request_view(item):
    view = public_request_view(item)

    if item.get("status") == "approved" and item.get("access_token"):
        view["access_url"] = f"/access/{item['request_id']}?token={item['access_token']}"
    else:
        view["access_url"] = None

    return view


@app.get("/health")
def health():
    return {
        "status": "ok",
        "company": "Afternum Industries",
        "product": "PRMR Memory Core Onboarding",
        "version": APP_VERSION,
        "mode": "local_onboarding_alpha"
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("""
    <html>
        <head>
            <title>PRMR Onboarding</title>
            <style>
                body {
                    background: #050505;
                    color: #f5f5f5;
                    font-family: Arial, sans-serif;
                    padding: 40px;
                }

                a {
                    color: #ffffff;
                    font-weight: bold;
                }

                .box {
                    max-width: 850px;
                    margin: 0 auto;
                    border: 1px solid #444;
                    border-radius: 20px;
                    background: linear-gradient(180deg, #0e0e0e, #151515);
                    padding: 26px;
                }

                .sub {
                    color: #b8b8b8;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>PRMR Memory Core Onboarding</h1>
                <div class="sub">Afternum Industries · Professional Client Onboarding Alpha · V0.35</div>
                <p><a href="/apply">Request API Access</a></p>
                <p><a href="/admin/requests">Admin Approval Queue</a></p>
            </div>
        </body>
    </html>
    """)


@app.get("/apply", response_class=HTMLResponse)
def apply_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Request PRMR API Access</title>
        <style>
            body {
                background: radial-gradient(circle at top, #151515 0%, #050505 50%);
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }

            .shell {
                max-width: 900px;
                margin: 0 auto;
            }

            .hero, .card {
                border: 1px solid #444;
                border-radius: 20px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 24px;
                margin-bottom: 18px;
            }

            h1 {
                margin: 0;
                font-size: 34px;
            }

            .sub, .notice {
                color: #b8b8b8;
                margin-top: 10px;
            }

            label {
                display: block;
                margin-top: 14px;
                margin-bottom: 6px;
                color: #b8b8b8;
                text-transform: uppercase;
                font-size: 13px;
                letter-spacing: 0.8px;
            }

            input, select, textarea {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #444;
                background: #070707;
                color: #f5f5f5;
            }

            textarea {
                height: 140px;
                resize: vertical;
            }

            button {
                margin-top: 18px;
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
                margin-top: 16px;
            }
        </style>
    </head>

    <body>
        <div class="shell">
            <div class="hero">
                <h1>Request PRMR API Access</h1>
                <div class="sub">Afternum Industries · PRMR Memory Core · Private Beta Access</div>
                <div class="notice">
                    Submit your access request. In this local alpha, Afternum admin approval creates your API key, client ID, vault, and namespace.
                </div>
            </div>

            <div class="card">
                <label>Company Name</label>
                <input id="companyName" value="Example AI Lab">

                <label>Contact Name</label>
                <input id="contactName" value="Demo Founder">

                <label>Email</label>
                <input id="email" value="demo@example.com">

                <label>Requested Plan</label>
                <select id="requestedPlan">
                    <option value="private_beta">Private Beta</option>
                    <option value="developer">Developer</option>
                    <option value="builder">Builder</option>
                    <option value="startup">Startup</option>
                    <option value="enterprise_pilot">Enterprise Pilot</option>
                </select>

                <label>Use Case</label>
                <textarea id="useCase">We want to test PRMR Memory Core for AI memory/context continuity.</textarea>

                <button onclick="submitRequest()">Submit Access Request</button>

                <pre id="resultBox">No request submitted yet.</pre>
            </div>
        </div>

        <script>
            async function submitRequest() {
                const resultBox = document.getElementById("resultBox");

                const payload = {
                    company_name: document.getElementById("companyName").value,
                    contact_name: document.getElementById("contactName").value,
                    email: document.getElementById("email").value,
                    requested_plan: document.getElementById("requestedPlan").value,
                    use_case: document.getElementById("useCase").value
                };

                try {
                    const response = await fetch("/api/apply", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();

                    if (data.submitted) {
                        resultBox.innerText =
                            "Access request submitted.\\n\\n" +
                            "Status: " + data.status + "\\n" +
                            "Request ID: " + data.request_id + "\\n\\n" +
                            "Afternum will review this request before API access is issued.";
                    } else {
                        resultBox.innerText = JSON.stringify(data, null, 2);
                    }

                } catch (error) {
                    resultBox.innerText = "Request failed: " + error.message;
                }
            }
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.post("/api/apply")
def apply(payload: dict):
    required = ["company_name", "contact_name", "email", "requested_plan", "use_case"]

    for field in required:
        if not payload.get(field):
            raise HTTPException(
                status_code=400,
                detail=f"Missing field: {field}"
            )

    data = load_requests()

    request_id = "req_" + uuid4().hex[:16]
    access_token = "access_" + uuid4().hex

    item = {
        "request_id": request_id,
        "access_token": access_token,
        "company_name": payload["company_name"].strip(),
        "contact_name": payload["contact_name"].strip(),
        "email": payload["email"].strip(),
        "requested_plan": payload["requested_plan"],
        "use_case": payload["use_case"].strip(),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "approved_at": None,
        "approved_client": None
    }

    data["requests"].append(item)
    save_requests(data)

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": APP_VERSION,
        "submitted": True,
        "request_id": request_id,
        "status": "pending",
        "message": "Access request submitted. Awaiting Afternum admin approval.",
        "note": "Access URL is generated after admin approval."
    }


@app.get("/admin/requests", response_class=HTMLResponse)
def admin_requests_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Admin Requests</title>
        <style>
            body {
                background: #050505;
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }

            .shell {
                max-width: 1200px;
                margin: 0 auto;
            }

            .hero, .card {
                border: 1px solid #444;
                border-radius: 18px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 22px;
                margin-bottom: 18px;
            }

            .sub, .notice {
                color: #b8b8b8;
                margin-top: 8px;
            }

            input {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #444;
                background: #070707;
                color: #f5f5f5;
                margin-bottom: 12px;
            }

            button {
                padding: 10px 14px;
                border-radius: 10px;
                border: 1px solid #ddd;
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                font-weight: bold;
                cursor: pointer;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }

            th, td {
                border-bottom: 1px solid #333;
                padding: 10px;
                text-align: left;
                vertical-align: top;
                font-size: 13px;
            }

            th {
                background: #1a1a1a;
            }

            td {
                background: #0d0d0d;
            }

            pre {
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 14px;
                white-space: pre-wrap;
                margin-top: 16px;
            }
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="hero">
                <h1>Admin Approval Queue</h1>
                <div class="sub">Afternum Industries · PRMR Memory Core · V0.35</div>
                <div class="notice">Local admin page. Approving a request creates client_id, API key, vault, namespace, and plan.</div>
            </div>

            <div class="card">
                <label>Admin Key</label>
                <input id="adminKey" value="prmr_local_admin_key_v034">
                <button onclick="loadRequests()">Load Requests</button>
                <pre id="outputBox">No action yet.</pre>
            </div>

            <div class="card">
                <h2>Requests</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Request ID</th>
                            <th>Company</th>
                            <th>Contact</th>
                            <th>Email</th>
                            <th>Plan</th>
                            <th>Status</th>
                            <th>Use Case</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="requestsTable">
                        <tr><td colspan="8">Load requests to view.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadRequests(updateOutput = true) {
                const table = document.getElementById("requestsTable");
                const output = document.getElementById("outputBox");

                try {
                    const response = await fetch("/api/admin/requests", {
                        method: "GET",
                        headers: {
                            "X-PRMR-Admin-Key": document.getElementById("adminKey").value
                        }
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        output.innerText = JSON.stringify(data, null, 2);
                        return;
                    }

                    table.innerHTML = "";

                    for (const item of data.requests) {
                        const row = document.createElement("tr");

                        const button = item.status === "pending"
                            ? `<button onclick="approveRequest('${item.request_id}')">Approve</button>`
                            : item.access_url
                                ? `<a href="${item.access_url}" target="_blank">Open Access</a>`
                                : "Approved";

                        row.innerHTML = `
                            <td>${item.request_id}</td>
                            <td>${item.company_name}</td>
                            <td>${item.contact_name}</td>
                            <td>${item.email}</td>
                            <td>${item.requested_plan}</td>
                            <td>${item.status}</td>
                            <td>${item.use_case}</td>
                            <td>${button}</td>
                        `;

                        table.appendChild(row);
                    }

                    if (updateOutput) {
                        output.innerText = "Requests loaded.";
                    }

                } catch (error) {
                    output.innerText = "Request failed: " + error.message;
                }
            }

            async function approveRequest(requestId) {
                const output = document.getElementById("outputBox");

                try {
                    const response = await fetch("/api/admin/approve/" + requestId, {
                        method: "POST",
                        headers: {
                            "X-PRMR-Admin-Key": document.getElementById("adminKey").value
                        }
                    });

                    const data = await response.json();

                    if (data.approved && data.access_url) {
                        output.innerText =
                            "Approved. Client access URL:\n" +
                            data.access_url +
                            "\n\nOpen this link to view the client's API access page.";
                    } else {
                        output.innerText = JSON.stringify(data, null, 2);
                    }

                    await loadRequests(false);

                } catch (error) {
                    output.innerText = "Approval failed: " + error.message;
                }
            }

            loadRequests();
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/api/admin/requests")
def api_admin_requests(x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": APP_VERSION,
        "requests": [
            admin_request_view(item)
            for item in data.get("requests", [])
        ]
    }


@app.post("/api/admin/approve/{request_id}")
def api_admin_approve(request_id: str, x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()

    for item in data.get("requests", []):
        if item.get("request_id") == request_id:
            if item.get("status") == "approved":
                return {
                    "approved": False,
                    "reason": "Request already approved.",
                    "request": public_request_view(item)
                }

            vault_id = "vault_" + item["company_name"].lower().replace(" ", "_").replace("/", "_")[:24]

            client = create_client(
                client_name=item["company_name"],
                plan=item["requested_plan"],
                vault_id=vault_id
            )

            item["status"] = "approved"
            item["approved_at"] = datetime.now().isoformat()
            item["approved_client"] = client

            save_requests(data)

            return {
                "company": "Afternum Industries",
                "product": "PRMR Memory Core",
                "version": APP_VERSION,
                "approved": True,
                "request_id": request_id,
                "client_id": client["client_id"],
                "vault_id": client["vault_id"],
                "namespace": client["namespace"],
                "plan": client["plan"],
                "access_url": f"/access/{request_id}?token={item['access_token']}",
                "important": "API key is available on the client access page. Treat it as sensitive."
            }

    raise HTTPException(status_code=404, detail="Request not found.")


@app.get("/access/{request_id}", response_class=HTMLResponse)
def access_page(request_id: str, token: str):
    item = find_request(request_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Request not found.")

    if token != item.get("access_token"):
        raise HTTPException(status_code=403, detail="Invalid access token.")

    if item.get("status") != "approved" or item.get("approved_client") is None:
        return HTMLResponse("""
        <html>
            <body style="background:#050505;color:#f5f5f5;font-family:Arial;padding:40px;">
                <h1>Access Pending</h1>
                <p>Your PRMR Memory Core access request is still pending Afternum approval.</p>
            </body>
        </html>
        """)

    client = item["approved_client"]

    quickstart = f'''$body = Get-Content "inputs/demo_input_v029.json" -Raw

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/run" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{{
    "X-PRMR-API-Key" = "YOUR_API_KEY"
    "X-PRMR-Vault-ID" = "{client["vault_id"]}"
    "X-PRMR-Namespace" = "{client["namespace"]}"
  }} `
  -Body $body
'''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Your PRMR API Access</title>
        <style>
            body {{
                background: radial-gradient(circle at top, #151515 0%, #050505 50%);
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }}

            .shell {{
                max-width: 950px;
                margin: 0 auto;
            }}

            .hero, .card {{
                border: 1px solid #444;
                border-radius: 20px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 24px;
                margin-bottom: 18px;
            }}

            .label {{
                color: #b8b8b8;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                font-size: 13px;
                margin-bottom: 6px;
            }}

            .value {{
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 12px;
                word-break: break-all;
                margin-bottom: 14px;
            }}

            pre {{
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 14px;
                white-space: pre-wrap;
                overflow: auto;
            }}

            button {{
                padding: 10px 14px;
                border-radius: 10px;
                border: 1px solid #ddd;
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                font-weight: bold;
                cursor: pointer;
                margin-bottom: 12px;
            }}

            .notice {{
                color: #b8b8b8;
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="hero">
                <h1>Your PRMR API Access</h1>
                <div class="notice">Afternum Industries · PRMR Memory Core · Private Beta Access</div>
            </div>

            <div class="card">
                <div class="label">Client ID</div>
                <div class="value">{client["client_id"]}</div>

                <div class="label">Plan</div>
                <div class="value">{client["plan"]}</div>

                <div class="label">Vault ID</div>
                <div class="value">{client["vault_id"]}</div>

                <div class="label">Namespace</div>
                <div class="value">{client["namespace"]}</div>

                <div class="label">API Key</div>
                <div class="value" id="apiKeyMasked">prmr_••••••••••••••••••••••••••••••••</div>
                <div class="value" id="apiKey" style="display:none;">{client["api_key"]}</div>

                <button onclick="revealKey()">Reveal API Key</button>
                <button onclick="copyKey()">Copy API Key</button>

                <div class="notice">
                    Keep this key private. In a real hosted product, API keys should be shown once, masked afterward, and rotatable.
                </div>
            </div>

            <div class="card">
                <h2>Quickstart</h2>
                <pre>{quickstart}</pre>
            </div>
        </div>

        <script>
            function revealKey() {{
                const hiddenKey = document.getElementById("apiKey").innerText;
                document.getElementById("apiKeyMasked").innerText = hiddenKey;
            }}

            function copyKey() {{
                const key = document.getElementById("apiKey").innerText;
                navigator.clipboard.writeText(key);
                alert("API key copied.");
            }}
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)

@app.get("/api/admin/requests-clean")
def api_admin_requests_clean(x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()
    requests = []

    for item in data.get("requests", []):
        approved_client = item.get("approved_client")
        access_url = None

        if item.get("status") == "approved" and item.get("access_token"):
            access_url = f"/access/{item['request_id']}?token={item['access_token']}"

        requests.append({
            "request_id": item.get("request_id"),
            "company_name": item.get("company_name"),
            "contact_name": item.get("contact_name"),
            "email": item.get("email"),
            "requested_plan": item.get("requested_plan"),
            "use_case": item.get("use_case"),
            "status": item.get("status"),
            "created_at": item.get("created_at"),
            "approved_at": item.get("approved_at"),
            "client_id": approved_client.get("client_id") if approved_client else None,
            "vault_id": approved_client.get("vault_id") if approved_client else None,
            "namespace": approved_client.get("namespace") if approved_client else None,
            "access_url": access_url
        })

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": APP_VERSION,
        "requests": requests
    }


@app.post("/api/admin/approve-clean/{request_id}")
def api_admin_approve_clean(request_id: str, x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()

    for item in data.get("requests", []):
        if item.get("request_id") == request_id:
            access_url = f"/access/{request_id}?token={item['access_token']}"

            if item.get("status") == "approved":
                return {
                    "approved": False,
                    "reason": "Request already approved.",
                    "request_id": request_id,
                    "access_url": access_url
                }

            safe_company = "".join(
                character if character.isalnum() else "_"
                for character in item["company_name"].lower()
            ).strip("_")[:24]

            vault_id = "vault_" + safe_company

            client = create_client(
                client_name=item["company_name"],
                plan=item["requested_plan"],
                vault_id=vault_id
            )

            item["status"] = "approved"
            item["approved_at"] = datetime.now().isoformat()
            item["approved_client"] = client

            save_requests(data)

            return {
                "company": "Afternum Industries",
                "product": "PRMR Memory Core",
                "version": APP_VERSION,
                "approved": True,
                "request_id": request_id,
                "client_id": client["client_id"],
                "vault_id": client["vault_id"],
                "namespace": client["namespace"],
                "plan": client["plan"],
                "access_url": access_url,
                "important": "Client access URL created. API key is only shown on the access page."
            }

    raise HTTPException(status_code=404, detail="Request not found.")


@app.get("/admin/requests-clean", response_class=HTMLResponse)
def admin_requests_clean_page():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Clean Admin Requests</title>
        <style>
            body {
                background: #050505;
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }

            .shell {
                max-width: 1200px;
                margin: 0 auto;
            }

            .hero, .card {
                border: 1px solid #444;
                border-radius: 18px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 22px;
                margin-bottom: 18px;
            }

            input {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #444;
                background: #070707;
                color: #f5f5f5;
                margin-bottom: 12px;
            }

            button, a.button-link {
                padding: 10px 14px;
                border-radius: 10px;
                border: 1px solid #ddd;
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                font-weight: bold;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }

            th, td {
                border-bottom: 1px solid #333;
                padding: 10px;
                text-align: left;
                vertical-align: top;
                font-size: 13px;
            }

            th {
                background: #1a1a1a;
            }

            td {
                background: #0d0d0d;
            }

            pre {
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 14px;
                white-space: pre-wrap;
                margin-top: 16px;
            }

            .muted {
                color: #b8b8b8;
            }
        </style>
    </head>

    <body>
        <div class="shell">
            <div class="hero">
                <h1>Clean Admin Approval Queue</h1>
                <p class="muted">Afternum Industries · PRMR Memory Core · V0.35.1</p>
            </div>

            <div class="card">
                <label>Admin Key</label>
                <input id="adminKey" value="prmr_local_admin_key_v034">
                <button onclick="loadRequests()">Load Requests</button>
                <pre id="outputBox">No action yet.</pre>
            </div>

            <div class="card">
                <h2>Requests</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Request ID</th>
                            <th>Company</th>
                            <th>Contact</th>
                            <th>Email</th>
                            <th>Plan</th>
                            <th>Status</th>
                            <th>Use Case</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="requestsTable">
                        <tr><td colspan="8">Click Load Requests.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadRequests() {
                const output = document.getElementById("outputBox");
                const table = document.getElementById("requestsTable");
                const adminKey = document.getElementById("adminKey").value;

                output.innerText = "Loading requests...";

                try {
                    const response = await fetch("/api/admin/requests-clean", {
                        method: "GET",
                        headers: {
                            "X-PRMR-Admin-Key": adminKey
                        }
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        output.innerText = JSON.stringify(data, null, 2);
                        return;
                    }

                    table.innerHTML = "";

                    for (const item of data.requests) {
                        const row = document.createElement("tr");

                        let action = "";

                        if (item.status === "pending") {
                            action = `<button onclick="approveRequest('${item.request_id}')">Approve</button>`;
                        } else if (item.access_url) {
                            action = `<a class="button-link" href="${item.access_url}" target="_blank">Open Access</a>`;
                        } else {
                            action = "Approved";
                        }

                        row.innerHTML = `
                            <td>${item.request_id}</td>
                            <td>${item.company_name}</td>
                            <td>${item.contact_name}</td>
                            <td>${item.email}</td>
                            <td>${item.requested_plan}</td>
                            <td>${item.status}</td>
                            <td>${item.use_case}</td>
                            <td>${action}</td>
                        `;

                        table.appendChild(row);
                    }

                    output.innerText = "Loaded " + data.requests.length + " request(s).";

                } catch (error) {
                    output.innerText = "Load failed: " + error.message;
                }
            }

            async function approveRequest(requestId) {
                const output = document.getElementById("outputBox");
                const adminKey = document.getElementById("adminKey").value;

                output.innerText = "Approving request...";

                try {
                    const response = await fetch("/api/admin/approve-clean/" + requestId, {
                        method: "POST",
                        headers: {
                            "X-PRMR-Admin-Key": adminKey
                        }
                    });

                    const data = await response.json();

                    if (data.access_url) {
                        output.innerText =
                            "Approval complete.\\n\\n" +
                            "Access URL:\\n" +
                            data.access_url;
                    } else {
                        output.innerText = JSON.stringify(data, null, 2);
                    }

                    await loadRequests();

                } catch (error) {
                    output.innerText = "Approval failed: " + error.message;
                }
            }

            loadRequests();
        </script>
    </body>
    </html>
    """)



@app.get("/api/admin/invites")
def api_admin_invites(x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()
    invite_rows = []

    for item in data.get("requests", []):
        approved_client = item.get("approved_client")
        access_url = None
        key_status = None

        if item.get("status") == "approved" and item.get("access_token"):
            access_url = f"/access/{item['request_id']}?token={item['access_token']}"

        if approved_client:
            key_status = approved_client.get("status", "active")

        invite_rows.append({
            "request_id": item.get("request_id"),
            "company_name": item.get("company_name"),
            "contact_name": item.get("contact_name"),
            "email": item.get("email"),
            "requested_plan": item.get("requested_plan"),
            "use_case": item.get("use_case"),
            "status": item.get("status"),
            "client_id": approved_client.get("client_id") if approved_client else None,
            "vault_id": approved_client.get("vault_id") if approved_client else None,
            "namespace": approved_client.get("namespace") if approved_client else None,
            "key_status": key_status,
            "invite_link": access_url
        })

    return {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.35.2",
        "admin_note": "Admin can approve clients and copy invite links, but API keys are only displayed on the client access page.",
        "requests": invite_rows
    }


@app.post("/api/admin/approve-invite/{request_id}")
def api_admin_approve_invite(request_id: str, x_prmr_admin_key: str = Header(default=None)):
    if not x_prmr_admin_key or not validate_admin_key(x_prmr_admin_key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    data = load_requests()

    for item in data.get("requests", []):
        if item.get("request_id") == request_id:
            invite_link = f"/access/{request_id}?token={item['access_token']}"

            if item.get("status") == "approved" and item.get("approved_client"):
                client = item["approved_client"]

                return {
                    "company": "Afternum Industries",
                    "product": "PRMR Memory Core",
                    "version": "0.35.2",
                    "approved": False,
                    "reason": "Request already approved.",
                    "request_id": request_id,
                    "client_id": client.get("client_id"),
                    "vault_id": client.get("vault_id"),
                    "namespace": client.get("namespace"),
                    "invite_link": invite_link,
                    "admin_note": "Send this invite link privately to the approved client. API key is not shown in admin response."
                }

            safe_company = "".join(
                character if character.isalnum() else "_"
                for character in item["company_name"].lower()
            ).strip("_")[:24]

            vault_id = "vault_" + safe_company

            client = create_client(
                client_name=item["company_name"],
                plan=item["requested_plan"],
                vault_id=vault_id
            )

            item["status"] = "approved"
            item["approved_at"] = datetime.now().isoformat()
            item["approved_client"] = client

            save_requests(data)

            return {
                "company": "Afternum Industries",
                "product": "PRMR Memory Core",
                "version": "0.35.2",
                "approved": True,
                "request_id": request_id,
                "client_id": client["client_id"],
                "vault_id": client["vault_id"],
                "namespace": client["namespace"],
                "plan": client["plan"],
                "invite_link": invite_link,
                "admin_note": "Copy this invite link and send it privately to the approved client. API key is only shown on the client access page."
            }

    raise HTTPException(status_code=404, detail="Request not found.")


@app.get("/admin/invites", response_class=HTMLResponse)
def admin_invites_page():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PRMR Client Invites</title>
        <style>
            body {
                background: #050505;
                color: #f5f5f5;
                font-family: Arial, sans-serif;
                padding: 32px;
            }

            .shell {
                max-width: 1250px;
                margin: 0 auto;
            }

            .hero, .card {
                border: 1px solid #444;
                border-radius: 18px;
                background: linear-gradient(180deg, #0e0e0e, #151515);
                padding: 22px;
                margin-bottom: 18px;
            }

            .muted {
                color: #b8b8b8;
            }

            input {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                border: 1px solid #444;
                background: #070707;
                color: #f5f5f5;
                margin-bottom: 12px;
            }

            button {
                padding: 10px 14px;
                border-radius: 10px;
                border: 1px solid #ddd;
                background: linear-gradient(180deg, #ffffff, #b8b8b8);
                color: #050505;
                font-weight: bold;
                cursor: pointer;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }

            th, td {
                border-bottom: 1px solid #333;
                padding: 10px;
                text-align: left;
                vertical-align: top;
                font-size: 13px;
            }

            th {
                background: #1a1a1a;
            }

            td {
                background: #0d0d0d;
            }

            pre {
                background: #070707;
                border: 1px solid #444;
                border-radius: 12px;
                padding: 14px;
                white-space: pre-wrap;
                margin-top: 16px;
            }

            .pill {
                display: inline-block;
                padding: 4px 8px;
                border: 1px solid #555;
                border-radius: 999px;
                color: #d8d8d8;
                font-size: 12px;
            }
        </style>
    </head>

    <body>
        <div class="shell">
            <div class="hero">
                <h1>Client Invite Manager</h1>
                <p class="muted">Afternum Industries · PRMR Memory Core · V0.35.2</p>
                <p class="muted">
                    Admin approves access and copies a private invite link. API keys are not shown in this admin page.
                </p>
            </div>

            <div class="card">
                <label>Admin Key</label>
                <input id="adminKey" value="prmr_local_admin_key_v034">
                <button onclick="loadInvites()">Load Invites</button>
                <pre id="outputBox">No action yet.</pre>
            </div>

            <div class="card">
                <h2>Requests / Invites</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Request ID</th>
                            <th>Company</th>
                            <th>Contact</th>
                            <th>Plan</th>
                            <th>Status</th>
                            <th>Client</th>
                            <th>Vault</th>
                            <th>Key Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="invitesTable">
                        <tr><td colspan="9">Click Load Invites.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadInvites() {
                const output = document.getElementById("outputBox");
                const table = document.getElementById("invitesTable");
                const adminKey = document.getElementById("adminKey").value;

                output.innerText = "Loading invites...";

                try {
                    const response = await fetch("/api/admin/invites", {
                        method: "GET",
                        headers: {
                            "X-PRMR-Admin-Key": adminKey
                        }
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        output.innerText = JSON.stringify(data, null, 2);
                        return;
                    }

                    table.innerHTML = "";

                    for (const item of data.requests) {
                        const row = document.createElement("tr");

                        let action = "";

                        if (item.status === "pending") {
                            action = `<button onclick="approveInvite('${item.request_id}')">Approve + Create Invite</button>`;
                        } else if (item.invite_link) {
                            action = `<button onclick="copyInvite('${item.invite_link}')">Copy Invite Link</button>`;
                        } else {
                            action = "Approved";
                        }

                        row.innerHTML = `
                            <td>${item.request_id}</td>
                            <td>${item.company_name}</td>
                            <td>${item.contact_name}<br><span class="muted">${item.email}</span></td>
                            <td>${item.requested_plan}</td>
                            <td><span class="pill">${item.status}</span></td>
                            <td>${item.client_id || "Not created yet"}</td>
                            <td>${item.vault_id || "Not created yet"}</td>
                            <td>${item.key_status || "No key yet"}</td>
                            <td>${action}</td>
                        `;

                        table.appendChild(row);
                    }

                    output.innerText =
                        "Loaded " + data.requests.length + " request(s).\\n\\n" +
                        "Admin note: invite links are for delivery to clients. API keys stay on the client access page.";

                } catch (error) {
                    output.innerText = "Load failed: " + error.message;
                }
            }

            async function approveInvite(requestId) {
                const output = document.getElementById("outputBox");
                const adminKey = document.getElementById("adminKey").value;

                output.innerText = "Approving request and creating invite...";

                try {
                    const response = await fetch("/api/admin/approve-invite/" + requestId, {
                        method: "POST",
                        headers: {
                            "X-PRMR-Admin-Key": adminKey
                        }
                    });

                    const data = await response.json();

                    if (data.invite_link) {
                        output.innerText =
                            "Invite created.\\n\\n" +
                            "Client ID: " + data.client_id + "\\n" +
                            "Vault ID: " + data.vault_id + "\\n" +
                            "Namespace: " + data.namespace + "\\n\\n" +
                            "Private invite link:\\n" +
                            data.invite_link + "\\n\\n" +
                            "Send this invite link privately to the approved client. API key is not shown here.";
                    } else {
                        output.innerText = JSON.stringify(data, null, 2);
                    }

                    await loadInvites();

                } catch (error) {
                    output.innerText = "Approval failed: " + error.message;
                }
            }

            function copyInvite(inviteLink) {
                const fullLink = window.location.origin + inviteLink;
                navigator.clipboard.writeText(fullLink);
                document.getElementById("outputBox").innerText =
                    "Client invite link copied.\\n\\n" +
                    fullLink + "\\n\\n" +
                    "Send this privately to the approved client.";
            }

            loadInvites();
        </script>
    </body>
    </html>
    """)
