# PRMR Product Readiness Gap Register

| Issue | Severity | Evidence | Risk | Fix or Recommendation | Effort | Dependencies | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Namespace-wide packet mixing for scoped events | Critical | Previous packet generation used all events in client/vault/namespace | Multi-user products could receive blended memory | Implemented entity-scoped packet selection and no-global guard | Medium | Existing event normalization | `python examples/run_product_readiness_sprint.py` | Fixed |
| Missing application product object | Critical | Clients had key/vault/namespace but no application list | External teams could not model environments/apps | Implemented application model, routes, dashboard data, key association | Medium | Self-serve account scope | Product readiness runner | Fixed |
| Packet provenance too thin for engineering debugging | Critical | V0.99 fields existed but contribution reasons were limited | Developers could not explain packet changes | Added safe provenance and score factor breakdowns | Medium | V0.99 deterministic packet | Product readiness runner | Fixed |
| Duplicate event behavior not explicit | High | Duplicate idempotency keys were appended | Replays could distort continuity | Duplicate event IDs are ignored and counted | Small | Event IDs/idempotency keys | Product readiness runner | Fixed |
| Blob event storage limits query/index scaling | High | Events stored as JSON array per namespace | Large histories may require costly scans | Add relational event table migration and indexes before broad external alpha | Large | Postgres migration/deploy window | Migration dry run and hosted smoke | Recommended |
| Rate limiting and abuse controls are incomplete | High | Plan quota exists, but no IP/token bucket limiter | Brute force or abusive traffic could stress hosted API | Add per-key/IP rate limiter and suspicious request audit | Medium | Hosted runtime state or Redis/Postgres counters | Rate-limit tests | Remaining |
| Operational metrics are basic | Medium | Liveness/readiness exist, dashboard logs exist | Latency/error analysis limited | Add structured metrics export, p95/p99, query timing | Medium | Logging/metrics backend | Load test reports | Remaining |
| Production security review absent | High | Local audits pass, no external review | Unknown hosted hardening gaps | Independent review before strong security claims | External | Security partner | Report from reviewer | Remaining |
| External engineering validation absent | High | Product readiness flow is local synthetic evidence | Unknown DX friction | Run first external integration with non-sensitive data | Medium | Approved tester | Evidence record | Remaining |

