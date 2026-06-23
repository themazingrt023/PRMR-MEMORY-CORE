import json
import urllib.request
import urllib.error


API_URL = "http://127.0.0.1:8000/run"
INPUT_FILE = "inputs/demo_input_v029.json"


def main():
    print("PRMR V0.34 GENERATED CLIENT KEY TEST")
    print("------------------------------------")

    api_key = input("Paste generated API key here, then press Enter: ").strip()
    vault_id = input("Vault ID [test_client_vault]: ").strip() or "test_client_vault"
    namespace = input("Namespace [default]: ").strip() or "default"

    with open(INPUT_FILE, "rb") as file:
        body = file.read()

    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PRMR-API-Key": api_key,
            "X-PRMR-Vault-ID": vault_id,
            "X-PRMR-Namespace": namespace
        }
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))

        print("\nSUCCESS ✅")
        print("API version:", result.get("api_version"))
        print("Company:", result.get("company"))
        print("Product:", result.get("product"))
        print("Client ID:", result.get("client_id"))
        print("Vault ID:", result.get("vault_id"))
        print("Namespace:", result.get("namespace"))
        print("Run ID:", result.get("run_id"))
        print("All reconstructions verified:", result.get("all_reconstructions_verified"))
        print("Public report path:", result.get("public_report_path"))

        if result.get("all_reconstructions_verified") is True:
            print("\nV0.34 generated client key works ✅")
        else:
            print("\nRequest worked, but reconstruction was not verified ❌")

    except urllib.error.HTTPError as error:
        print("\nHTTP ERROR ❌")
        print("Status code:", error.code)

        try:
            error_body = error.read().decode("utf-8")
            print("Response:", error_body)
        except Exception:
            pass

    except Exception as error:
        print("\nREQUEST FAILED ❌")
        print(error)


if __name__ == "__main__":
    main()