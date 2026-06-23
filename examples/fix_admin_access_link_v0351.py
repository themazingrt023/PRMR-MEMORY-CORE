from pathlib import Path

path = Path("prmr_onboarding.py")
text = path.read_text(encoding="utf-8")

# Add admin_request_view helper so admin can see approved access URLs.
if "def admin_request_view(item):" not in text:
    helper = '''

def admin_request_view(item):
    view = public_request_view(item)

    if item.get("status") == "approved" and item.get("access_token"):
        view["access_url"] = f"/access/{item['request_id']}?token={item['access_token']}"
    else:
        view["access_url"] = None

    return view
'''
    text = text.replace('\n\n@app.get("/health")', helper + '\n\n@app.get("/health")')

# Make admin API return admin view instead of public-only view.
text = text.replace(
'''public_request_view(item)
            for item in data.get("requests", [])''',
'''admin_request_view(item)
            for item in data.get("requests", [])'''
)

# Let loadRequests preserve approval message when needed.
text = text.replace(
'''async function loadRequests() {''',
'''async function loadRequests(updateOutput = true) {'''
)

text = text.replace(
'''output.innerText = "Requests loaded.";''',
'''if (updateOutput) {
                        output.innerText = "Requests loaded.";
                    }'''
)

# Show Open Access link for approved requests.
text = text.replace(
'''const button = item.status === "pending"
                            ? `<button onclick="approveRequest('${item.request_id}')">Approve</button>`
                            : "Approved";''',
'''const button = item.status === "pending"
                            ? `<button onclick="approveRequest('${item.request_id}')">Approve</button>`
                            : item.access_url
                                ? `<a href="${item.access_url}" target="_blank">Open Access</a>`
                                : "Approved";'''
)

# Keep approval output visible after approval.
text = text.replace(
'''const data = await response.json();
                    output.innerText = JSON.stringify(data, null, 2);

                    await loadRequests();''',
'''const data = await response.json();

                    if (data.approved && data.access_url) {
                        output.innerText =
                            "Approved. Client access URL:\\n" +
                            data.access_url +
                            "\\n\\nOpen this link to view the client's API access page.";
                    } else {
                        output.innerText = JSON.stringify(data, null, 2);
                    }

                    await loadRequests(false);'''
)

path.write_text(text, encoding="utf-8")

print("V0.35.1 admin access link fix applied ✅")
print("Restart onboarding server on port 8002.")