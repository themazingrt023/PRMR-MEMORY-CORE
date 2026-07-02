# V0.86 First Alpha Evidence Record Template

Use this template after a real external controlled alpha test attempt.

Do not include raw API keys, dashboard tokens, sensitive data, private logs, or unapproved client data.

## Tester Identity

Tester/project identifier:

```text
<TESTER_PSEUDONYM_OR_APPROVED_NAME>
```

Use a pseudonym or approved public name only.

## Date And Time

```text
Date:
Start time:
End time:
Timezone:
```

## Test Scope

```text
Client ID: <CLIENT_ID>
Vault ID: <VAULT_ID>
Namespace: <NAMESPACE>
Dashboard access used: yes/no
API access used: yes/no
```

## Data Safety Confirmation

```text
Synthetic or approved non-sensitive data only: yes/no
Sensitive real client data used: no
If any concern exists, describe and revoke access:
```

## What Was Tested

Endpoints tested:

Check all that apply:

- [ ] `GET /health`
- [ ] `POST /v1/events/ingest`
- [ ] `POST /v1/continuity/packet`
- [ ] `POST /v1/memory/reconstruct`
- [ ] `POST /v1/explain`
- [ ] `POST /v1/actions/least-harm`
- [ ] `GET /v1/reports/{report_id}`
- [ ] `GET /v1/usage`
- [ ] `GET /v1/dashboard/state`
- [ ] Dashboard page or dashboard proxy
- [ ] Client docs and handoff flow

Dashboard tested: yes/no

## Issues Found

```text
Setup issues:
API issues:
Dashboard issues:
Report/log issues:
Security/trust issues:
Data-boundary issues:
Other issues:
```

## Feedback Summary

```text
What made sense:
What was confusing:
Strongest use case:
Weakest or unclear use case:
What would make this pilot-worthy:
Trust/security concerns:
Suggested improvement before next tester:
```

## Access Status

```text
Access revoked: yes/no
Access kept open: yes/no
Reason:
Revocation time, if revoked:
```

## Honest Result Status

Choose one:

- `completed_positive`
- `completed_mixed`
- `completed_needs_work`
- `not_completed`
- `revoked`

Selected status:

```text
<RESULT_STATUS>
```

## Next Actions

```text
Immediate fix needed:
Follow-up needed:
Next tester readiness:
Storage/auth/security gap noted:
```

## Boundary

This record is evidence of one external controlled alpha test attempt only. It is not production readiness, billing, compliance approval, legal approval, bank approval, external security certification, or real-world validation.
