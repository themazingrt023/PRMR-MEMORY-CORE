# V0.67 Deployed URL Smoke Test

This smoke test is run only when a deployed staging URL is explicitly provided through:

```env
PRMR_STAGING_DEPLOYMENT_URL=https://example-staging-url
```

or:

```env
STAGING_DEPLOYMENT_URL=https://example-staging-url
```

If neither variable is set, the audit must record:

```json
{
  "deployment_url_available": false,
  "deployed_url_smoke_check": "not_run_no_url"
}
```

## Public Page Checks

For the deployed URL, check:

- `/`
- `/docs`
- `/demo`
- `/alpha`
- `/book-demo`
- `/contact`

Expected: HTTP 200 and public-safe page content. The pages should preserve synthetic/local evidence boundaries and avoid secrets, private request details, local personal paths, hosted API claims, production readiness claims, or certification claims.

## Blocked Route Checks

Check:

- `/alpha/review`
- `/book-demo/review`
- `/api/alpha/review`
- `/api/demo/review`

Expected: 404, safe disabled page, or JSON code `local_only_route_disabled`.

## Disabled Demo Bridge Checks

Check:

- `/api/demo/run`

Expected: JSON code `demo_bridge_disabled_on_public_frontend`.

## Disabled Form Checks

POST synthetic placeholder JSON to:

- `/api/alpha/request`
- `/api/demo/book`

Expected: JSON code `request_capture_not_enabled_on_public_frontend`.

The form endpoints must not write local files, send email, create calendar events, issue API keys, grant live access, or connect billing.

## Reporting

The smoke report should include the deployed URL, checked routes, status codes, disabled-route codes, and whether private/secrets patterns were found. Public reports must not include secrets, personal request data, private reports, or private internals.
