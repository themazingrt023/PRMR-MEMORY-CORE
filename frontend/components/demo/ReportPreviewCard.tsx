import { LabFrame } from "@/components/visual/LabFrame";
import type { ReportPreview } from "@/data/demoData";
import type { ConnectedReportPreview } from "@/data/demoConnection";

export function ReportPreviewCard({ report }: { report: ReportPreview | ConnectedReportPreview }) {
  const normalized = normalizeReport(report);

  return (
    <LabFrame className="p-6">
      <h2 className="font-display text-2xl text-silver">Report preview</h2>
      <p className="mt-3 text-sm text-mist/74">Report: {normalized.reportId}</p>
      <p className="mt-2 text-sm text-mist/74">Public-safe: {String(normalized.publicSafe)}</p>
      <p className="mt-2 text-sm text-mist/74">Owner path: {normalized.ownerAccess}</p>
      <p className="mt-2 text-sm leading-6 text-mist/62">{normalized.summary}</p>
    </LabFrame>
  );
}

function normalizeReport(report: ReportPreview | ConnectedReportPreview) {
  if ("report_id" in report) {
    return {
      reportId: report.report_id,
      publicSafe: report.public_safe,
      ownerAccess: report.owner_access,
      summary: report.public_summary
    };
  }

  return {
    reportId: report.reportId,
    publicSafe: report.publicSafe,
    ownerAccess: report.ownerAccess,
    summary: report.denialPath
  };
}
