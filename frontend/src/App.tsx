import { useEffect, useState } from "react";
import {
  getFeedFixture,
  listFeedFixtures,
  listManifestFixtures,
  validateManifest,
  validateMetadata,
  validateSubmission,
} from "./api";
import { MetadataReportView } from "./components/MetadataReportView";
import { ManifestReportView } from "./components/ManifestReportView";
import type {
  FeedFixture,
  FeedFormat,
  ManifestFixture,
  ManifestReport,
  MetadataReport,
} from "./types";

export default function App() {
  const [feedFixtures, setFeedFixtures] = useState<FeedFixture[]>([]);
  const [manifestFixtures, setManifestFixtures] = useState<ManifestFixture[]>([]);

  const [partnerName, setPartnerName] = useState("Apex Sports Network");
  const [contentTitle, setContentTitle] = useState("F1: Monaco Grand Prix Replay");
  const [feedFormat, setFeedFormat] = useState<FeedFormat>("mrss");
  const [metadataContent, setMetadataContent] = useState("");
  const [manifestUrl, setManifestUrl] = useState("");

  const [metadataReport, setMetadataReport] = useState<MetadataReport | null>(null);
  const [manifestReport, setManifestReport] = useState<ManifestReport | null>(null);
  const [combinedPassed, setCombinedPassed] = useState<boolean | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFeedFixtures().then(setFeedFixtures).catch((e) => setError(String(e)));
    listManifestFixtures().then(setManifestFixtures).catch((e) => setError(String(e)));
  }, []);

  async function loadFeedFixture(id: string) {
    if (!id) return;
    setError(null);
    const fixture = await getFeedFixture(id);
    setFeedFormat(fixture.feed_format);
    setMetadataContent(fixture.content ?? "");
  }

  async function loadManifestFixture(id: string) {
    if (!id) return;
    setError(null);
    const fixture = manifestFixtures.find((m) => m.id === id);
    if (fixture) setManifestUrl(fixture.manifest_url);
  }

  async function runMetadataValidation() {
    setError(null);
    setLoading("metadata");
    try {
      setMetadataReport(await validateMetadata(feedFormat, metadataContent));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  }

  async function runManifestValidation() {
    setError(null);
    setLoading("manifest");
    try {
      setManifestReport(await validateManifest(manifestUrl));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  }

  async function runFullSubmission() {
    setError(null);
    setLoading("submission");
    try {
      const report = await validateSubmission({
        partnerName,
        contentTitle,
        feedFormat: metadataContent ? feedFormat : undefined,
        metadataContent: metadataContent || undefined,
        manifestUrl: manifestUrl || undefined,
      });
      setMetadataReport(report.metadata_report);
      setManifestReport(report.manifest_report);
      setCombinedPassed(report.passed);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Media Partner Ingestion Validator</h1>
        <p>Self-service pre-flight checks for schedule metadata and HLS/DASH media manifests.</p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="panel">
        <h2>Partner Submission</h2>
        <div className="field-row">
          <label>
            Partner name
            <input value={partnerName} onChange={(e) => setPartnerName(e.target.value)} />
          </label>
          <label>
            Content title
            <input value={contentTitle} onChange={(e) => setContentTitle(e.target.value)} />
          </label>
        </div>
      </section>

      <div className="columns">
        <section className="panel">
          <h2>1. Metadata Feed (MRSS / JSON)</h2>
          <div className="field-row">
            <label>
              Load sample
              <select defaultValue="" onChange={(e) => loadFeedFixture(e.target.value)}>
                <option value="" disabled>
                  Choose a fixture…
                </option>
                {feedFixtures.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Format
              <select value={feedFormat} onChange={(e) => setFeedFormat(e.target.value as FeedFormat)}>
                <option value="mrss">MRSS (XML)</option>
                <option value="json">JSON</option>
              </select>
            </label>
          </div>
          <textarea
            rows={14}
            spellCheck={false}
            placeholder="Paste MRSS XML or JSON feed content here…"
            value={metadataContent}
            onChange={(e) => setMetadataContent(e.target.value)}
          />
          <button disabled={!metadataContent || loading !== null} onClick={runMetadataValidation}>
            {loading === "metadata" ? "Validating…" : "Validate Metadata"}
          </button>
          {metadataReport && <MetadataReportView report={metadataReport} />}
        </section>

        <section className="panel">
          <h2>2. Media Manifest (HLS / DASH)</h2>
          <div className="field-row">
            <label>
              Load sample
              <select defaultValue="" onChange={(e) => loadManifestFixture(e.target.value)}>
                <option value="" disabled>
                  Choose a fixture…
                </option>
                {manifestFixtures.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="full-width">
            Manifest URL
            <input
              placeholder="https://…/master.m3u8 or …/manifest.mpd"
              value={manifestUrl}
              onChange={(e) => setManifestUrl(e.target.value)}
            />
          </label>
          <button disabled={!manifestUrl || loading !== null} onClick={runManifestValidation}>
            {loading === "manifest" ? "Validating…" : "Validate Manifest"}
          </button>
          {manifestReport && <ManifestReportView report={manifestReport} />}
        </section>
      </div>

      <section className="panel submission-panel">
        <h2>3. Full Submission Report</h2>
        <p>Runs both checks together and produces a single go/no-go decision, as Ops would see it.</p>
        <button
          className="primary"
          disabled={(!metadataContent && !manifestUrl) || loading !== null}
          onClick={runFullSubmission}
        >
          {loading === "submission" ? "Validating…" : "Run Full Submission"}
        </button>
        {combinedPassed !== null && (
          <div className={`overall-result ${combinedPassed ? "pass" : "fail"}`}>
            {combinedPassed ? "READY FOR GO-LIVE" : "BLOCKED — resolve issues above before go-live"}
          </div>
        )}
      </section>
    </div>
  );
}
