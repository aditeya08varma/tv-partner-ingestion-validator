import type { Issue } from "../types";

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) {
    return <p className="empty-state">No issues found.</p>;
  }
  return (
    <ul className="issue-list">
      {issues.map((issue, i) => (
        <li key={i} className={`issue issue-${issue.severity}`}>
          <span className={`badge badge-${issue.severity}`}>{issue.severity}</span>
          <div className="issue-body">
            <code className="issue-field">{issue.field}</code>
            <p className="issue-message">
              {issue.message}
              {issue.line != null && <span className="issue-line"> (line {issue.line})</span>}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
