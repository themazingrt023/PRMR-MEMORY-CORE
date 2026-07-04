# Afternum Industries Official Domain

Official frontend:

```text
https://afternumindustries.co.uk
```

The domain and `www.afternumindustries.co.uk` are attached to the Vercel
project `prmr-memory-core`. The existing
`https://prmr-memory-core.vercel.app` address remains a fallback.

## DNS at the registrar

The registrar currently uses Phase8 nameservers. Add these records there:

```text
A      @      216.198.79.1
A      @      64.29.17.1
CNAME  www    fb287b181c8d967e.vercel-dns-017.com
```

These are the project-specific values returned by Vercel verification on
3 July 2026. Remove the current `85.233.160.22` apex record and the
`fwd3.hosts.co.uk` `www` forwarding record, plus any other conflicting `A`,
`AAAA`, or `CNAME` records for `@` and `www`.
Do not change MX records used for email.

After DNS propagates, verify both domains in Vercel Project Settings >
Domains. Configure a permanent redirect from `www.afternumindustries.co.uk`
to `afternumindustries.co.uk` so the apex domain remains canonical.

## Render CORS

Set the backend environment value to:

```text
PRMR_ALLOWED_ORIGINS=https://afternumindustries.co.uk,https://www.afternumindustries.co.uk,https://prmr-memory-core.vercel.app
```

Keep explicit origins. Do not use wildcard CORS.

## Supabase Auth

Set the production Site URL to:

```text
https://afternumindustries.co.uk
```

Add these exact redirect URLs:

```text
https://afternumindustries.co.uk/auth/callback
https://www.afternumindustries.co.uk/auth/callback
https://prmr-memory-core.vercel.app/auth/callback
http://localhost:3000/auth/callback
```

The Vercel fallback remains during transition. Production signup should begin
and finish on the official domain so PKCE cookies stay on the same host.

## Verification

```powershell
npx vercel domains inspect afternumindustries.co.uk
npx vercel domains inspect www.afternumindustries.co.uk
```

The official domain is live only after DNS is valid, TLS is issued, the site
loads, and the auth callback is accepted on the official host.
