const OFFICIAL_WHOP_HOSTS = new Set(["whop.com", "www.whop.com"]);

export type WhopCheckoutState = {
  configured: boolean;
  url: string;
  label: "Continue to Whop" | "Request Pilot Access";
  external: boolean;
};

export function getWhopCheckoutState(): WhopCheckoutState {
  const fallback = "/alpha?source=whop-pilot";
  const configured = process.env.NEXT_PUBLIC_WHOP_CHECKOUT_URL?.trim();
  if (!configured) {
    return { configured: false, url: fallback, label: "Request Pilot Access", external: false };
  }

  try {
    const parsed = new URL(configured);
    if (parsed.protocol !== "https:" || !OFFICIAL_WHOP_HOSTS.has(parsed.hostname) || parsed.pathname === "/") {
      return { configured: false, url: fallback, label: "Request Pilot Access", external: false };
    }
    return { configured: true, url: configured, label: "Continue to Whop", external: true };
  } catch {
    return { configured: false, url: fallback, label: "Request Pilot Access", external: false };
  }
}

