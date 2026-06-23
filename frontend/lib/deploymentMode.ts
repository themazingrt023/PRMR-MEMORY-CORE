import { NextResponse } from "next/server";

export type DeploymentMode = "local" | "public_frontend";

export const PUBLIC_FRONTEND_BOUNDARY =
  "Public frontend mode is presentation-only. It does not provide hosted backend access, production onboarding, billing, live API access, API key issuing, external validation, bank approval, compliance approval, legal approval, external security certification, or real-world validation.";

export function getDeploymentMode(): DeploymentMode {
  const configured = process.env.NEXT_PUBLIC_DEPLOYMENT_MODE;
  if (configured === "local" || configured === "public_frontend") return configured;
  return process.env.NODE_ENV === "production" ? "public_frontend" : "local";
}

export function isPublicFrontendMode() {
  return getDeploymentMode() === "public_frontend";
}

export function isLocalReviewEnabled() {
  return getDeploymentMode() === "local" && process.env.LOCAL_REVIEW_ENABLED === "true";
}

export function isLocalFileWritesEnabled() {
  return getDeploymentMode() === "local" && process.env.LOCAL_FILE_WRITES_ENABLED === "true";
}

export function isLocalDemoBridgeEnabled() {
  return getDeploymentMode() === "local" && process.env.LOCAL_DEMO_BRIDGE_ENABLED === "true";
}

export function isPublicFormCaptureEnabled() {
  return getDeploymentMode() === "public_frontend" && process.env.PUBLIC_FORM_CAPTURE_ENABLED === "true";
}

export function isPublicDemoBridgeEnabled() {
  return getDeploymentMode() === "public_frontend" && process.env.PUBLIC_DEMO_BRIDGE_ENABLED === "true";
}

export function publicModeInfo() {
  return {
    deployment_mode: getDeploymentMode(),
    public_frontend: isPublicFrontendMode(),
    public_form_capture_enabled: isPublicFormCaptureEnabled(),
    public_demo_bridge_enabled: isPublicDemoBridgeEnabled(),
    boundary: PUBLIC_FRONTEND_BOUNDARY
  };
}

export function localOnlyRouteDisabledResponse() {
  return NextResponse.json(
    {
      status: "error",
      error: {
        code: "local_only_route_disabled",
        message: "This local review/admin route is disabled in the current deployment mode."
      },
      ...publicModeInfo()
    },
    { status: 404 }
  );
}

export function demoBridgeDisabledResponse() {
  return NextResponse.json(
    {
      status: "error",
      synthetic_only: true,
      error: {
        code: "demo_bridge_disabled_on_public_frontend",
        message: "The local demo bridge is disabled in public frontend mode."
      },
      ...publicModeInfo()
    },
    { status: 503 }
  );
}

export function formCaptureDisabledResponse(publicFrontend = isPublicFrontendMode()) {
  return NextResponse.json(
    {
      status: "error",
      error: {
        code: publicFrontend ? "request_capture_not_enabled_on_public_frontend" : "local_file_writes_disabled",
        message: publicFrontend
          ? "Request capture is not enabled on this public frontend deployment."
          : "Local request capture is disabled until LOCAL_FILE_WRITES_ENABLED is explicitly set."
      },
      no_live_service_access_granted: true,
      automatic_access_granted: false,
      api_key_issued: false,
      ...publicModeInfo()
    },
    { status: 503 }
  );
}
