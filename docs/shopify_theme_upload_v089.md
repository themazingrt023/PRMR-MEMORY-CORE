# V0.89 Shopify Theme Upload Guide

This package is a Shopify conversion theme for the Afternum / PRMR Controlled Alpha Pilot.

It is not the main PRMR company site. The company site builds trust; this Shopify theme converts attention into pilot applications or purchases.

## Files

- Theme folder: `shopify_prmr_pilot_theme/`
- Upload ZIP: `afternum-prmr-controlled-alpha-theme.zip`

## Upload Steps

1. Open Shopify Admin.
2. Go to Online Store -> Themes.
3. Choose Add theme / Import theme.
4. Upload `afternum-prmr-controlled-alpha-theme.zip`.
5. Preview the theme before publishing.
   - If the editor opens on `404 page`, use the top page selector and switch to `Home page`.
   - This package also includes a 404 fallback template so the preview does not appear empty.
6. Create a product named `PRMR Controlled Alpha Pilot`.
7. Set the product as a digital/service product with physical shipping disabled.
8. Set price to `£250`, or keep the page copy as `from £250` if the final price is manually agreed.
9. Use manual fulfilment only.
10. Do not enable automatic API key delivery.
11. Link CTA buttons to the product page, an application page, or a booking page.
12. Keep the PRMR company site linked as `Learn more`: `https://prmr-memory-core.vercel.app`.

## Recommended Shopify Product Setup

Product title:

```text
PRMR Controlled Alpha Pilot
```

Product type:

```text
Digital/service product
```

Price:

```text
£250
```

Fulfilment:

```text
Manual fulfilment only
```

Shipping:

```text
Physical shipping disabled
```

Description should state:

- Controlled alpha pilot
- Manual approval only
- 15-minute onboarding call
- Limited sandbox access
- Manually issued test API key
- Synthetic or approved non-sensitive data only
- Usage limits
- Continuity output/report
- Integration recommendation
- Feedback call
- Manual revoke path

## Theme Settings To Configure

In the theme editor, open the PRMR Controlled Alpha Pilot section and configure:

- Primary CTA label: `Request Pilot Access`
- Primary CTA URL: `/products/prmr-controlled-alpha-pilot` or an application page
- Secondary CTA label: `Book Pilot Call`
- Secondary CTA URL: your booking/contact page

## Boundary

This Shopify theme does not claim production launch status, regulated approval, external security sign-off, promised outcomes, self-serve production API access, or automatic key delivery.

Do not paste credentials, private access tokens, protected engine internals, private reports, or sensitive client data into Shopify theme settings or product descriptions.
