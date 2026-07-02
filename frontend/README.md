# PRMR Memory Core Frontend

This is the Afternum Industries / PRMR Memory Core frontend. The public site is
deployed, while dashboard key controls remain a local synthetic approved-client
preview until production authentication and hosted dashboard persistence exist.

The PRMR backend is hosted separately and has passed controlled synthetic
protected-route smoke. This frontend does not provide production
authentication, automatic onboarding, completed Whop billing, or permission to
submit sensitive data.

## Run Locally

Install dependencies inside `frontend/`, then run the local dev server:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

To test the connected local demo flow, open `http://localhost:3000/demo`, select a synthetic scenario, and click `Run Local Demo`.

## Routes

- `/`
- `/demo`
- `/alpha`
- `/docs`
- `/contact`
- `/dashboard`
- `/market`
- `/pilot`
- `/public-proof`
- `/whop`
- `/capabilities/event-ingestion`
- `/capabilities/continuity-packets`
- `/capabilities/state-reconstruction`
- `/capabilities/stale-signal-handling`
- `/capabilities/evidence-awareness`
- `/capabilities/public-safe-explanations`
- `/capabilities/least-harm-actions`
- `/capabilities/public-private-reports`

Local proxy routes:

- `GET /api/demo/scenarios`
- `POST /api/demo/run`
- `GET /api/demo/report`
- `GET /api/demo/health`

## Component Architecture

Landing components:

- `Navigation`
- `HeroSection`
- `ProblemSection`
- `SolutionSection`
- `ApiFlowSection`
- `EvidenceSection`
- `UseCasesSection`
- `AlphaAccessSection`
- `Footer`

Demo components:

- `ScenarioSelector`
- `LocalDemoRunner`
- `EventsSummaryCard`
- `ContinuityPacketCard`
- `ReconstructionCard`
- `ExplanationCard`
- `LeastHarmActionCard`
- `ReportPreviewCard`
- `DenialPathCard`

Docs components:

- `ApiOverview`
- `EndpointList`
- `VersionTimeline`
- `EvidenceBoundaryNotice`

Alpha components:

- `RequestAccessForm`
- `ControlledAlphaNotice`

Brand components:

- `AfternumLogo`
- `AfternumMark`

Visual components:

- `DataRainBackground`
- `FragmentedContinuityVisual`
- `KimiSectionShell`
- `LiquidGlassButton`
- `LabFrame`
- `SectionShell`
- `SilverDivider`
- `SignalGrid`

Reusable mock data and public response types live in `frontend/data/`.

Capability detail copy lives in `frontend/data/capabilities.ts`. Public benchmark category copy lives in `frontend/data/benchmarkEvidence.ts`.

Kimi-inspired visual assets copied into the canonical shell live in `frontend/public/visual/`. They are used as atmospheric use-case imagery only and do not replace the Afternum logo or brand hierarchy.

## Logo Usage

The Afternum Industries logo is served from:

- `frontend/public/brand/afternum-logo.png`

The reusable logo component lives at:

- `frontend/components/brand/AfternumLogo.tsx`

Supported sizes:

- `nav`
- `hero`
- `heroFull`
- `footer`
- `mark`

The component uses `next/image`, keeps the image proportional, includes the accessible alt text `Afternum Industries logo`, and has a small text-mark fallback if the browser fails to load the image. The V0.54.3 audit fails if the logo asset is missing from the required public path.

## Visual System

V0.54.9 keeps the approved hero mostly as-is and corrects the remaining navigation, interaction, capability, and evidence issues:

- black, near-black, white, silver, cool grey, and faint blue-white glow
- silver/cool-grey data-rain atmosphere with waterline/ripple treatment
- full-screen cinematic hero with the full Afternum Industries logo asset
- sparse fixed Kimi-style navigation
- homepage header navigation: Problem, Solution, API, Demo, Evidence, Access, Contact
- `/docs` remains available but is no longer in the main header nav
- lower sections use plain black and near-black backgrounds instead of repeated global square/tile grids
- thin silver dividers and restrained borders
- Kimi-like 1400px section width and 150px vertical section rhythm
- Kimi-like problem network visual
- Kimi-like capabilities rows with large serif titles and hover imagery
- capability click-through pages under `/capabilities/[slug]`
- expandable benchmark/evidence rows instead of a default visible full-version ladder
- Kimi-like image-driven use-case cards
- Kimi cinematic architecture/video band
- stronger problem, solution, API, evidence, capabilities, use-case, demo, alpha, and restrained logo-led footer storytelling
- elegant serif headings
- technical sans/mono support text
- subtle grid and signal motifs
- atmospheric use-case imagery from safe generated assets

The Kimi source in `design_sources/kimi_prmr_site/app/` was used as the visual base for layout, spacing, atmosphere, and interaction style. Unsafe claims were not copied. The canonical frontend remains `frontend/`, and the brand hierarchy remains Afternum Industries first, PRMR Memory Core as the first product.

## Logo Usage Rule

The hero/main visual area uses the full Afternum Industries logo:

- `frontend/public/brand/afternum-logo.png`

The mark-only asset is available only for small placements such as nav icon, floating mark, small badge, or loading mark:

- `frontend/public/brand/afternum-mark.png`

## Current Limitations

- Synthetic/demo data only.
- Public dashboard remains locked without controlled authentication.
- Dashboard create/rotate/revoke controls are local synthetic previews.
- Whop checkout URL is configurable but not verified as externally configured.
- Whop webhook/manual-review entrypoint is local and not deployed.
- No completed billing automation.
- No production authentication.
- Hosted backend storage durability is not yet verified.
- Manual approved-client credential issuance only.
- No external validation asserted.
- No banking, regulatory, legal, or third-party security sign-off asserted.

## V0.88-V0.91 Product Path

- V0.88: approved-client dashboard and copy-once key-management MVP.
- V0.89: `/whop` offer and controlled access funnel with a safe manual fallback.
- V0.90: signed Whop-event intake to SQLite-backed manual review; no automatic key issuing.
- V0.91: first local internal server-side consumer using a temporary `.env`.

Configure the public checkout destination with:

```env
NEXT_PUBLIC_WHOP_CHECKOUT_URL=https://whop.com/<YOUR-OFFER-OR-CHECKOUT-PATH>
```

Only an official HTTPS `whop.com` URL is accepted. The page falls back to the
manual alpha request when the variable is absent or invalid.

## Integration Boundary

The V0.55 demo page calls local backend proxy routes, not PRMR core directly from browser code. Browser code must not store or expose credentials. Public demo views fetch public-safe reports only. Restricted traces must stay out of public frontend output.

The local bridge is documented in `docs/frontend_backend_connection_v055.md`. It is local demo wiring only, not a production backend pattern.
