# PRMR Memory Core V0.65 Environment Boundary

V0.65 defines what can be public, what must stay local, and what belongs to future hosted infrastructure.

## Local-Only

These must not be exposed on a public domain without protection or replacement:

- Local reports under `reports/`
- Private/internal reports
- Alpha review state
- Demo review state
- Review consoles
- Local bridge/demo runner routes if they execute local processes
- File-writing admin routes
- Any route that exposes personal request details
- Any route that writes local JSON files

## Public-Safe

These may be public only if copy remains bounded and no private data is exposed:

- Homepage `/`
- Public demo page `/demo` if synthetic-only and not dependent on unsafe local bridge execution
- Docs page `/docs` if it contains no secrets/private internals
- Contact page `/contact`
- Capability pages `/capabilities/[slug]`
- Alpha request page `/alpha` if the submit action is disabled, protected, or backed by a safe hosted request system
- Book demo page `/book-demo` if the submit action is disabled, protected, or backed by a safe hosted request system
- Public-safe reports only

## Future Hosted

These belong to future hosted infrastructure and are not implemented as production services in V0.65:

- Hosted backend sandbox
- Real client dashboard
- API key management
- Billing
- Authentication
- Database
- Rate limiting
- Deployed logs/monitoring
- Permissioned review dashboard
- Secure report storage

## Public/Private Report Boundary

Public reports may contain aggregate counts, safe statuses, and boundary wording. Public reports must not contain personal request details, API keys, secrets, private/internal report contents, private engine internals, or debug traces.

Private/internal reports may contain local traces for development, but they must stay local unless explicitly sanitized.

## Environment Flags For Future Work

V0.65 documents these future flags without requiring code guards yet:

- `NEXT_PUBLIC_ENABLE_LOCAL_REVIEW=false`
- `LOCAL_REVIEW_ENABLED=false`
- `LOCAL_FILE_WRITES_ENABLED=false`
- `LOCAL_DEMO_BRIDGE_ENABLED=false`

Public deployment should default all local review/file-writing features to disabled unless a secure hosted replacement exists.
