from pathlib import Path

path = Path("prmr_onboarding.py")
text = path.read_text(encoding="utf-8")

if '@app.get("/admin/requests-clean"' in text:
    print("Clean admin route already exists ✅")
else:
    text += r'''

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

'''
    path.write_text(text, encoding="utf-8")
    print("Clean admin route added ✅")

print("Restart onboarding server and open /admin/requests-clean")