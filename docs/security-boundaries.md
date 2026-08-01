# Security Boundaries

Runtime output, health, readiness, logs, diagnostics, manifests, and reports must not include database URLs, passwords, provider credentials, API keys, authentication tokens, lease tokens, source content, event signals, evidence text, entity labels, or raw job payloads.

SQL remains parameterised for values. Paths are normalised, root destinations and implicit overwrite are refused where applicable, and temporary artifacts are cleaned after failure. PostgreSQL destructive tests require a dedicated URL, explicit permission, and the verified guard table. This is an internal review, not external penetration testing or security certification.
