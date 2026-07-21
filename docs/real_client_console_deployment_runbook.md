# Real Client and Console Deployment Runbook

Truth label: deployment runbook. Do not claim deployment completion until each smoke test passes against the real URL.

## Reference Client

1. Deploy `reference-client/` as its own Vercel project.
2. Configure server-side environment variables:

```text
PRMR_API_URL=https://prmr-memory-core-api.onrender.com
PRMR_API_KEY=<copy-once-reference-client-key>
```

3. Do not expose `PRMR_API_KEY` as `NEXT_PUBLIC_*`.
4. Run:

```bash
cd reference-client
npm run hosted:smoke
```

## Console

1. Deploy `console/` as its own Vercel project.
2. Target domain:

```text
app.prmr.afternumindustries.co.uk
```

3. Configure:

```text
NEXT_PUBLIC_SUPABASE_URL=<supabase-project-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<supabase-anon-key>
PRMR_HOSTED_API_URL=https://prmr-memory-core-api.onrender.com
```

4. Add console callback URLs in Supabase before publishing.

## Marketing

Target domain:

```text
prmr.afternumindustries.co.uk
```

The existing Afternum site can remain at `https://afternumindustries.co.uk` during migration.

## Legacy Routes

Keep `https://afternumindustries.co.uk/dashboard` working until the console URL is verified. After verification, redirect it to the console domain.
