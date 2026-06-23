# V0.66 Public Frontend Mode

Public frontend mode is for a public-facing PRMR Memory Core shell only. It is not hosted API access, not production onboarding, not billing, not API key issuing, not external validation, and not certification.

Set:

```bash
NEXT_PUBLIC_DEPLOYMENT_MODE=public_frontend
LOCAL_REVIEW_ENABLED=false
LOCAL_FILE_WRITES_ENABLED=false
LOCAL_DEMO_BRIDGE_ENABLED=false
PUBLIC_FORM_CAPTURE_ENABLED=false
PUBLIC_DEMO_BRIDGE_ENABLED=false
```

## What Remains Available

The public site can display:

- landing page copy
- synthetic demo explanations
- synthetic continuity packet previews
- public-safe docs
- alpha/demo request pages with safe disabled request capture
- contact and capability pages
- boundary statements

## What Is Disabled

Public frontend mode blocks:

- local alpha review console
- local demo review console
- local review APIs
- local JSON request capture
- local demo bridge execution
- local report bridge APIs

## Public Responses

Disabled local-only APIs return safe JSON with stable codes:

- `local_only_route_disabled`
- `demo_bridge_disabled_on_public_frontend`
- `request_capture_not_enabled_on_public_frontend`

These responses must not include private request details, private reports, local personal file paths, credentials, or debug traces.

## Local Development Escape Hatch

To use local review tools during development, keep the app local and explicitly set:

```bash
NEXT_PUBLIC_DEPLOYMENT_MODE=local
LOCAL_REVIEW_ENABLED=true
LOCAL_FILE_WRITES_ENABLED=true
LOCAL_DEMO_BRIDGE_ENABLED=true
```

Do not use those local enablement flags on a public domain.
