export const whopOffer = {
  name: "PRMR Controlled Alpha Pilot",
  eyebrow: "Whop access funnel",
  headline: "Give your system memory that evolves.",
  description:
    "A founder-reviewed pilot for teams that want to test PRMR Memory Core as the continuity layer beneath an AI product, agent, workflow, or platform.",
  price: "From £250",
  commercialLine: "You build the app. PRMR preserves the memory layer underneath.",
  coreLine: "Storage remembers data. Retrieval finds data. PRMR preserves continuity.",
  includes: [
    "15-minute onboarding call",
    "limited controlled-alpha API access",
    "one manually issued, copy-once test key",
    "scoped client ID, vault ID, and namespace",
    "synthetic or explicitly approved non-sensitive data only",
    "usage limits and scoped request logs",
    "continuity output and public-safe report",
    "integration recommendation and feedback call",
    "manual revoke path"
  ],
  boundaries: [
    "Manual approval is required after payment or waitlist intent.",
    "Payment does not automatically issue an API key or unlock the dashboard.",
    "This is not a self-serve production API.",
    "Sensitive data is not accepted without explicit approval.",
    "No production, compliance, legal, banking, or external security certification is claimed."
  ]
} as const;

export const whopFunnelStages = [
  {
    number: "01",
    title: "Review the pilot",
    detail: "Confirm the scope, price, data boundary, usage limits, and what the controlled alpha does not provide."
  },
  {
    number: "02",
    title: "Continue through Whop",
    detail: "Use the configured hosted checkout or waitlist link. If it is not connected yet, submit the manual pilot request."
  },
  {
    number: "03",
    title: "Founder review",
    detail: "Afternum reviews product fit, permitted data, technical readiness, and available pilot capacity."
  },
  {
    number: "04",
    title: "Manual onboarding",
    detail: "An approved client receives a scoped client, vault, namespace, dashboard path, and a copy-once API key."
  },
  {
    number: "05",
    title: "Use and monitor",
    detail: "Use PRMR server-side, then review usage, request logs, public-safe reports, and memory health in the dashboard."
  }
] as const;

