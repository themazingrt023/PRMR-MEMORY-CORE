from pathlib import Path

path = Path("prmr_onboarding.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
'''const data = await response.json();
                    resultBox.innerText = JSON.stringify(data, null, 2);''',
'''const data = await response.json();

                    if (data.submitted) {
                        resultBox.innerText =
                            "Access request submitted.\\\\n\\\\n" +
                            "Status: " + data.status + "\\\\n" +
                            "Request ID: " + data.request_id + "\\\\n\\\\n" +
                            "Afternum will review this request before API access is issued.";
                    } else {
                        resultBox.innerText = JSON.stringify(data, null, 2);
                    }'''
)

text = text.replace(
'''"future_access_url_after_approval": f"/access/{request_id}?token={access_token}"''',
'''"note": "Access URL is generated after admin approval."'''
)

text = text.replace(
'''"X-PRMR-API-Key" = "{client["api_key"]}"''',
'''"X-PRMR-API-Key" = "YOUR_API_KEY"'''
)

text = text.replace(
'''<div class="label">API Key</div>
                <div class="value" id="apiKey">{client["api_key"]}</div>
                <button onclick="copyKey()">Copy API Key</button>''',
'''<div class="label">API Key</div>
                <div class="value" id="apiKeyMasked">prmr_••••••••••••••••••••••••••••••••</div>
                <div class="value" id="apiKey" style="display:none;">{client["api_key"]}</div>

                <button onclick="revealKey()">Reveal API Key</button>
                <button onclick="copyKey()">Copy API Key</button>'''
)

text = text.replace(
'''<script>
            function copyKey() {{
                const key = document.getElementById("apiKey").innerText;
                navigator.clipboard.writeText(key);
                alert("API key copied.");
            }}
        </script>''',
'''<script>
            function revealKey() {{
                const hiddenKey = document.getElementById("apiKey").innerText;
                document.getElementById("apiKeyMasked").innerText = hiddenKey;
            }}

            function copyKey() {{
                const key = document.getElementById("apiKey").innerText;
                navigator.clipboard.writeText(key);
                alert("API key copied.");
            }}
        </script>'''
)

path.write_text(text, encoding="utf-8")

print("V0.35.1 onboarding polish patch applied ✅")
print("Now restart the onboarding server on port 8002.")