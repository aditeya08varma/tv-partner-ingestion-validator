import type { ManifestReport } from "../types";
import { IssueList } from "./IssueList";

export function ManifestReportView({ report }: { report: ManifestReport }) {
  return (
    <div className="report">
      <div className="report-header">
        <span className={`pass-fail ${report.passed ? "pass" : "fail"}`}>
          {report.passed ? "PASS" : "FAIL"}
        </span>
        <span className="report-meta">
          {report.manifest_type.toUpperCase()} · {report.segments_checked} segments probed ·{" "}
          {report.broken_segments.length} broken
        </span>
      </div>

      <h4>Renditions</h4>
      {report.renditions.length === 0 ? (
        <p className="empty-state">No renditions found.</p>
      ) : (
        <table className="rendition-table">
          <thead>
            <tr>
              <th>Resolution</th>
              <th>Bandwidth</th>
              <th>Codecs</th>
            </tr>
          </thead>
          <tbody>
            {report.renditions.map((r, i) => (
              <tr key={i}>
                <td>{r.resolution_label ?? "unknown"}</td>
                <td>{r.bandwidth ? `${Math.round(r.bandwidth / 1000)} kbps` : "—"}</td>
                <td>{r.codecs ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {report.missing_required_renditions.length > 0 && (
        <p className="warn-line">
          Missing required renditions: {report.missing_required_renditions.join(", ")}
        </p>
      )}

      <h4>Audio Tracks</h4>
      {report.audio_tracks.length === 0 ? (
        <p className="empty-state">No audio tracks found.</p>
      ) : (
        <ul className="audio-list">
          {report.audio_tracks.map((a, i) => (
            <li key={i}>
              {a.name} {a.language ? `(${a.language})` : ""} — group {a.group_id}
            </li>
          ))}
        </ul>
      )}

      <h4>Issues</h4>
      <IssueList issues={report.issues} />
    </div>
  );
}
