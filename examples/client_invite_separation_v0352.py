from pathlib import Path

path = Path("prmr_onboarding.py")
text = path.read_text(encoding="utf-8")

if '@app.get("/admin/invites"' in text:
    print("V0.35.2 invite separation already exists ✅")
else:
    text += r'''

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
'''
    path.write_text(text, encoding="utf-8")
    print("V0.35.2 client invite separation added ✅")

print("Restart onboarding server and open /admin/invites")