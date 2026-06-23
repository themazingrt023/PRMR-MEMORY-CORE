export type DashboardKeyRecord = {
  keyId: string;
  clientId: string;
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
  "This dashboard is a local controlled-alpha dashboard MVP. It uses synthetic/dev-only data and does not provide hosted customer authentication, billing, live API access, or production guarantees.";

export const dashboardMockData = {
  sourceVersions: ["0.69", "0.70", "0.71"],
  clientOverview: {
    clientId: "client_v071_synthetic_alpha",
    organisation: "Synthetic V0.71 Alpha Client",
    status: "active",
    activeVaultCount: 1,
    activeNamespaceCount: 2,
    syntheticOnly: true,
    localModeAccess: "enabled_for_mvp_review",
    publicModeAccess: "blocked_or_placeholder"
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
        keyId: "key_v070_6d47df6582",
        clientId: "client_v070_synthetic_alpha",
        safeKeyPreview: "prmr_alpha_dev_...16e1",
        status: "active",
        vaultId: "vault_v070_alpha",
        namespace: "default",
        lastUsedAt: "2026-06-22T21:12:14.953551+00:00",
        operatorNote: "Display uses preview only. Full key values are not present in dashboard data."
      },
      {
        keyId: "key_v070_557d44d5e1",
        clientId: "client_v070_synthetic_alpha",
        safeKeyPreview: "prmr_alpha_dev_...6373",
        status: "rotated",
        vaultId: "vault_v070_alpha",
        namespace: "default",
        lastUsedAt: "2026-06-22T21:12:14.953551+00:00",
        operatorNote: "Display uses preview only. Full key values are not present in dashboard data."
      },
      {
        keyId: "key_v070_f2e84c8c58",
        clientId: "client_v070_synthetic_alpha",
        safeKeyPreview: "prmr_alpha_dev_...8097",
        status: "revoked",
        vaultId: "vault_v070_alpha",
        namespace: "default",
        lastUsedAt: "2026-06-22T21:12:14.953551+00:00",
        operatorNote: "Display uses preview only. Full key values are not present in dashboard data."
      }
    ] satisfies DashboardKeyRecord[]
  },
  vaultNamespacePanel: {
    crossClientBoundary: "Dashboard data is scoped to synthetic owner records; cross-client access remains denied by V0.71 evidence.",
    namespaces: [
      {
        namespaceId: "client_v071_synthetic_alpha::vault_v071_alpha::default",
        vaultId: "vault_v071_alpha",
        namespace: "default",
        status: "active",
        eventCount: 1,
        packetCount: 1,
        publicReportCount: 1
      },
      {
        namespaceId: "client_v071_synthetic_alpha::vault_v071_alpha::limit_test",
        vaultId: "vault_v071_alpha",
        namespace: "limit_test",
        status: "active",
        eventCount: 0,
        packetCount: 0,
        publicReportCount: 0
      }
    ] satisfies DashboardNamespace[]
  },
  usageOverview: {
    allowedRequestCount: 11,
    blockedRequestCount: 8,
    totalRequestCount: 19,
    byVault: {
      vault_v071_alpha: 18,
      vault_v071_other: 1
    },
    priorMilestoneComparison: {
      v069Total: 8,
      v070Total: 8,
      v071Total: 19
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
        clientId: "client_v071_synthetic_alpha",
        endpoint: "POST /v1/events/ingest",
        vaultId: "vault_v071_alpha",
        namespace: "default",
        status: "ok",
        reason: "allowed",
        publicSafeMessage: "Request completed for scoped controlled-alpha client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_v071_synthetic_alpha",
        endpoint: "POST /v1/continuity/packet",
        vaultId: "vault_v071_alpha",
        namespace: "default",
        status: "ok",
        reason: "allowed",
        publicSafeMessage: "Request completed for scoped controlled-alpha client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_v071_other",
        endpoint: "POST /v1/events/ingest",
        vaultId: "vault_v071_alpha",
        namespace: "default",
        status: "blocked",
        reason: "key_client_mismatch",
        publicSafeMessage: "The access key is not valid for this client."
      },
      {
        timestamp: "2026-06-22T21:33:17.773267+00:00",
        clientId: "client_v071_synthetic_alpha",
        endpoint: "POST /v1/continuity/packet",
        vaultId: "vault_v071_other",
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
        reportId: "report_8a55546259e8",
        packetId: "packet_9ad7385f0a69",
        clientId: "client_v071_synthetic_alpha",
        vaultId: "vault_v071_alpha",
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
