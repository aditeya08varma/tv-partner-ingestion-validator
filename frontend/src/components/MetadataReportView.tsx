import type { MetadataReport } from "../types";
import { IssueList } from "./IssueList";

export function MetadataReportView({ report }: { report: MetadataReport }) {
  return (
    <div className="report">
      <div className="report-header">
        <span className={`pass-fail ${report.passed ? "pass" : "fail"}`}>
          {report.passed ? "PASS" : "FAIL"}
        </span>
        <span className="report-meta">
          {report.feed_format.toUpperCase()} · {report.items_checked} item(s) checked
        </span>
      </div>
      <h4>Issues</h4>
      <IssueList issues={report.issues} />
    </div>
  );
}
