export type DashboardKeyRecord = {
  keyId: string;
  clientId: string;
  label: string;
  safeKeyPreview: string;
  status: "active" | "rotated" | "revoked";
  vaultId: string;
  namespace: string;
  lastUsedAt: string;
  operatorNote: string;
};

export type DashboardNamespace = {
  namespaceId: string;
  vaultId: string;
  namespace: string;
  status: string;
  eventCount: number;
  packetCount: number;
  publicReportCount: number;
};

export type DashboardRequestLogRow = {
  timestamp: string;
  clientId: string;
  endpoint: string;
  vaultId: string;
  namespace: string;
  status: "ok" | "blocked";
  reason: string;
  publicSafeMessage: string;
};

export const dashboardBoundary =
  "V0.92 is a generic self-serve API product MVP using local synthetic frontend data. The functional Python service implements account, plan, scoped key, quota, and protected API behavior. Real email, billing, durable hosted account storage, and production authentication remain separate work.";

export const dashboardMockData = {
  sourceVersions: ["0.70", "0.79", "0.84", "0.88", "0.92"],
  clientOverview: {
    clientId: "client_ss_demo",
    organisation: "Generic API Builder",
    status: "active",
    activeVaultCount: 1,
    activeNamespaceCount: 1,
    syntheticOnly: true,
    localModeAccess: "self_serve_mvp_preview",
    publicModeAccess: "locked_until_hosted_account_auth",
    vaultId: "vault_ss_demo",
    namespace: "default"
  },
  apiKeyPanel: {
    manualOperatorApprovalRequired: true,
    automaticKeyIssuing: false,
    safeKeyStatusCounts: {
      active: 1,
      rotated: 1,
      revoked: 1
    },
    records: [
      {
        keyId: "key_ss_preview_active",
        clientId: "client_ss_demo",
        label: "Example server key",
        safeKeyPreview: "prmr_alpha_local_...4a81",
        status: "active",
        vaultId: "vault_ss_demo",
        namespace: "default",
        lastUsedAt: "Synthetic preview",
        operatorNote: "Display uses a non-functional preview only. Full key values are not stored in dashboard data."
      }
    ] satisfies DashboardKeyRecord[]
  },
  vaultNamespacePanel: {
    crossClientBoundary: "Dashboard data is scoped to this approved synthetic client; V0.84 cross-client isolation remains enforced.",
    namespaces: [
      {
        namespaceId: "client_ss_demo::vault_ss_demo::default",
        vaultId: "vault_ss_demo",
        namespace: "default",
        status: "active",
        eventCount: 1,
        packetCount: 1,
        publicReportCount: 1
      }
    ] satisfies DashboardNamespace[]
  },
  usageOverview: {
    allowedRequestCount: 11,
    blockedRequestCount: 8,
    totalRequestCount: 19,
    byVault: {
      vault_ss_demo: 18,
      blocked_out_of_scope: 1
    },
    priorMilestoneComparison: {
      v080Onboarding: 8,
      v084Isolation: 16,
      v092Dashboard: 19
    }
  },
  requestLogSummary: {
    blockedReasonPolicy:
      "Blocked requests are logged as denied attempts, but failed authentication does not create successful work artifacts.",
    blockedReasons: [
      "missing_key",
      "invalid_key",
      "key_client_mismatch",
      "vault_denied",
      "namespace_denied",
      "rotated_key",
      "revoked_key",
      "usage_limit_exceeded"
    ],
    rows: [
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_ss_demo",
        endpoint: "POST /v1/events/ingest",
        vaultId: "vault_ss_demo",
        namespace: "default",
        status: "ok",
        reason: "allowed",
        publicSafeMessage: "Request completed for scoped controlled-alpha client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_ss_demo",
        endpoint: "POST /v1/continuity/packet",
        vaultId: "vault_ss_demo",
        namespace: "default",
        status: "ok",
        reason: "allowed",
        publicSafeMessage: "Request completed for scoped controlled-alpha client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_ss_other",
        endpoint: "POST /v1/events/ingest",
        vaultId: "vault_ss_demo",
        namespace: "default",
        status: "blocked",
        reason: "key_client_mismatch",
        publicSafeMessage: "The access key is not valid for this client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_ss_demo",
        endpoint: "POST /v1/continuity/packet",
        vaultId: "vault_ss_other",
        namespace: "default",
        status: "blocked",
        reason: "vault_denied",
        publicSafeMessage: "The requested vault is outside the authorized scope."
      }
    ] satisfies DashboardRequestLogRow[]
  },
  reportsPanel: {
    boundary: "Dashboard previews use public-safe report summaries only.",
    reports: [
      {
        reportId: "report_ss_demo_001",
        packetId: "packet_ss_demo_001",
        clientId: "client_ss_demo",
        vaultId: "vault_ss_demo",
        namespace: "default",
        publicSafe: true,
        eventCount: 1,
        summary: "Public-safe controlled-alpha continuity report generated from synthetic events."
      }
    ]
  },
  memoryHealthPanel: {
    status: "limited_local_mvp",
    eventsReceived: 1,
    packetsGenerated: 1,
    reconstructionAvailable: true,
    explanationAvailable: true,
    leastHarmAvailable: true,
    publicReportAvailable: true,
    blockedRequestCount: 8,
    healthNote: "Healthy enough for local synthetic dashboard review; not evidence of production readiness."
  }
} as const;
