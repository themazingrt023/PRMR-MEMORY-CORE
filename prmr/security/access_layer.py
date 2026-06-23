import json
import os
import secrets
from datetime import datetime
from uuid import uuid4


API_KEY_FILE = "config/api_keys_v031.json"
LOG_FOLDER = "logs"
REVOKED_LOCAL_DEV_KEY = "prmr_local_dev_key_v031"


DEFAULT_ACCESS_CONFIG = {
    "admin_key": "prmr_local_admin_key_v034",
    "plans": {
        "private_beta": {
            "name": "Private Beta",
            "monthly_run_limit": 1000,
            "vault_limit": 1
        },
        "developer": {
            "name": "Developer",
            "monthly_run_limit": 1000,
            "vault_limit": 1
        },
        "builder": {
            "name": "Builder",
            "monthly_run_limit": 10000,
            "vault_limit": 5
        },
        "startup": {
            "name": "Startup",
            "monthly_run_limit": 100000,
            "vault_limit": 20
        },
        "enterprise_pilot": {
            "name": "Enterprise Pilot",
            "monthly_run_limit": None,
            "vault_limit": None
        }
    },
    "api_keys": [
        {
            "api_key": None,
            "client_id": "local_dev_client",
            "client_name": "Local Development Client",
            "status": "revoked",
            "plan": "private_beta",
            "allowed_vaults": ["default_vault"],
            "created_at": "local_seed",
            "revoked_at": "v0.78.2_secret_cleanup",
            "revoke_reason": "Old local/dev key material is revoked and must not be reused."
        }
    ]
}


def ensure_access_config():
    os.makedirs("config", exist_ok=True)
    os.makedirs(LOG_FOLDER, exist_ok=True)

    if not os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "w", encoding="utf-8") as file:
            json.dump(DEFAULT_ACCESS_CONFIG, file, indent=4)
        return

    # Patch older V0.31 config files safely.
    with open(API_KEY_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    changed = False

    if "admin_key" not in config:
        config["admin_key"] = DEFAULT_ACCESS_CONFIG["admin_key"]
        changed = True

    if "plans" not in config:
        config["plans"] = DEFAULT_ACCESS_CONFIG["plans"]
        changed = True

    if "api_keys" not in config:
        config["api_keys"] = []
        changed = True

    existing_keys = [
        record.get("api_key")
        for record in config.get("api_keys", [])
    ]

    if not any(record.get("client_id") == "local_dev_client" for record in config.get("api_keys", [])):
        config["api_keys"].append(DEFAULT_ACCESS_CONFIG["api_keys"][0])
        changed = True

    for record in config.get("api_keys", []):
        if record.get("api_key") == REVOKED_LOCAL_DEV_KEY or record.get("client_id") == "local_dev_client":
            record["api_key"] = None
            record["status"] = "revoked"
            record["revoked_at"] = record.get("revoked_at") or "v0.78.2_secret_cleanup"
            record["revoke_reason"] = "Old local/dev key material is revoked and must not be reused."
            changed = True

    # Add missing fields to old client records.
    for record in config.get("api_keys", []):
        if "plan" not in record:
            record["plan"] = "private_beta"
            changed = True

        if "created_at" not in record:
            record["created_at"] = "legacy"
            changed = True

    if changed:
        with open(API_KEY_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)


def load_access_config():
    ensure_access_config()

    with open(API_KEY_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_access_config(config):
    os.makedirs("config", exist_ok=True)

    with open(API_KEY_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


def validate_admin_key(admin_key):
    config = load_access_config()

    return admin_key == config.get("admin_key")


def generate_api_key():
    return "prmr_" + secrets.token_urlsafe(32)


def create_client(client_name, plan="private_beta", vault_id=None):
    config = load_access_config()

    if plan not in config.get("plans", {}):
        raise ValueError(f"Unknown plan '{plan}'.")

    safe_name = client_name.strip()

    if not safe_name:
        raise ValueError("client_name cannot be empty.")

    client_id = "client_" + uuid4().hex[:16]

    if vault_id is None or vault_id.strip() == "":
        vault_id = "vault_" + uuid4().hex[:12]

    api_key = generate_api_key()

    record = {
        "api_key": api_key,
        "client_id": client_id,
        "client_name": safe_name,
        "status": "active",
        "plan": plan,
        "allowed_vaults": [vault_id],
        "created_at": datetime.now().isoformat()
    }

    config["api_keys"].append(record)
    save_access_config(config)

    return {
        "client_id": client_id,
        "client_name": safe_name,
        "api_key": api_key,
        "plan": plan,
        "vault_id": vault_id,
        "namespace": "default",
        "status": "active"
    }


def list_clients(public_safe=True):
    config = load_access_config()
    clients = []

    for record in config.get("api_keys", []):
        item = {
            "client_id": record.get("client_id"),
            "client_name": record.get("client_name"),
            "status": record.get("status"),
            "plan": record.get("plan"),
            "allowed_vaults": record.get("allowed_vaults", []),
            "created_at": record.get("created_at")
        }

        if not public_safe:
            item["api_key"] = record.get("api_key")

        clients.append(item)

    return clients


def validate_api_key(api_key):
    config = load_access_config()

    for record in config.get("api_keys", []):
        if record.get("api_key") == api_key and record.get("status") == "active":
            return {
                "valid": True,
                "client_id": record["client_id"],
                "client_name": record["client_name"],
                "plan": record.get("plan", "private_beta"),
                "allowed_vaults": record.get("allowed_vaults", [])
            }

    return {
        "valid": False,
        "reason": "Invalid or inactive API key."
    }


def validate_vault_access(client_record, vault_id):
    allowed_vaults = client_record.get("allowed_vaults", [])

    if vault_id in allowed_vaults:
        return True

    return False


def create_run_id():
    return "run_" + uuid4().hex


def build_access_context(api_key, vault_id, namespace):
    client_record = validate_api_key(api_key)

    if not client_record["valid"]:
        return {
            "allowed": False,
            "reason": client_record["reason"]
        }

    if not validate_vault_access(client_record, vault_id):
        return {
            "allowed": False,
            "reason": f"Client does not have access to vault '{vault_id}'."
        }

    return {
        "allowed": True,
        "client_id": client_record["client_id"],
        "client_name": client_record["client_name"],
        "plan": client_record.get("plan", "private_beta"),
        "vault_id": vault_id,
        "namespace": namespace,
        "run_id": create_run_id(),
        "timestamp": datetime.now().isoformat()
    }


def save_run_log(access_context, public_report_path, private_report_path, summary):
    os.makedirs(LOG_FOLDER, exist_ok=True)

    log_record = {
        "run_id": access_context["run_id"],
        "timestamp": access_context["timestamp"],
        "client_id": access_context["client_id"],
        "client_name": access_context["client_name"],
        "plan": access_context.get("plan", "private_beta"),
        "vault_id": access_context["vault_id"],
        "namespace": access_context["namespace"],
        "public_report_path": public_report_path,
        "private_report_path": private_report_path,
        "summary": summary
    }

    log_path = os.path.join(LOG_FOLDER, f"{access_context['run_id']}.json")

    with open(log_path, "w", encoding="utf-8") as file:
        json.dump(log_record, file, indent=4)

    return log_path

def save_key_audit_log(action, details):
    os.makedirs(LOG_FOLDER, exist_ok=True)

    audit_record = {
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }

    audit_path = os.path.join(
        LOG_FOLDER,
        f"key_audit_{uuid4().hex}.json"
    )

    with open(audit_path, "w", encoding="utf-8") as file:
        json.dump(audit_record, file, indent=4)

    return audit_path


def find_client_by_api_key(api_key):
    config = load_access_config()

    for record in config.get("api_keys", []):
        if record.get("api_key") == api_key:
            return record

    return None


def revoke_api_key(api_key, reason="manual revoke"):
    config = load_access_config()

    for record in config.get("api_keys", []):
        if record.get("api_key") == api_key:
            record["status"] = "revoked"
            record["revoked_at"] = datetime.now().isoformat()
            record["revoke_reason"] = reason

            save_access_config(config)

            audit_path = save_key_audit_log(
                "revoke_api_key",
                {
                    "client_id": record.get("client_id"),
                    "client_name": record.get("client_name"),
                    "reason": reason
                }
            )

            return {
                "revoked": True,
                "client_id": record.get("client_id"),
                "audit_path": audit_path
            }

    return {
        "revoked": False,
        "reason": "API key not found."
    }


def rotate_api_key_for_client(client_id):
    config = load_access_config()

    target_record = None

    for record in config.get("api_keys", []):
        if record.get("client_id") == client_id:
            target_record = record
            break

    if target_record is None:
        return {
            "rotated": False,
            "reason": "Client not found."
        }

    # Revoke all existing active keys for this client.
    for record in config.get("api_keys", []):
        if record.get("client_id") == client_id and record.get("status") == "active":
            record["status"] = "revoked"
            record["revoked_at"] = datetime.now().isoformat()
            record["revoke_reason"] = "rotated"

    new_key = generate_api_key()

    new_record = {
        "api_key": new_key,
        "client_id": target_record.get("client_id"),
        "client_name": target_record.get("client_name"),
        "status": "active",
        "plan": target_record.get("plan", "private_beta"),
        "allowed_vaults": target_record.get("allowed_vaults", []),
        "created_at": datetime.now().isoformat(),
        "rotated_from_client": client_id
    }

    config["api_keys"].append(new_record)
    save_access_config(config)

    audit_path = save_key_audit_log(
        "rotate_api_key",
        {
            "client_id": client_id,
            "client_name": target_record.get("client_name"),
            "new_key_created": True
        }
    )

    return {
        "rotated": True,
        "client_id": client_id,
        "client_name": target_record.get("client_name"),
        "api_key": new_key,
        "allowed_vaults": new_record["allowed_vaults"],
        "plan": new_record["plan"],
        "audit_path": audit_path
    }
