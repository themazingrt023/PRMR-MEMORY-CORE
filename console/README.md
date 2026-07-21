# PRMR Developer Console

Truth label: separated console deployment root. This is not a production auth hardening claim, billing launch, compliance approval, legal approval, or external security certification.

Target domain:

```text
app.prmr.afternumindustries.co.uk
```

This root is intentionally separate from the marketing site. It should share the same Supabase project and PRMR backend, but it must not show marketing navigation such as Problem, Solution, Market, Pilot, Demo, or Start Building inside authenticated console screens.

Required environment variables for deployment:

```text
NEXT_PUBLIC_SUPABASE_URL=<supabase-project-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<supabase-anon-key>
PRMR_HOSTED_API_URL=https://prmr-memory-core-api.onrender.com
```

Future production hardening remains separate work.
