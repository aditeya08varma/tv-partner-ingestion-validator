export type Severity = "error" | "warning";
export type FeedFormat = "mrss" | "json";

export interface Issue {
  severity: Severity;
  field: string;
  message: string;
  line: number | null;
}

export interface MetadataReport {
  passed: boolean;
  feed_format: FeedFormat;
  items_checked: number;
  issues: Issue[];
}

export interface RenditionInfo {
  resolution_label: string | null;
  width: number | null;
  height: number | null;
  bandwidth: number | null;
  codecs: string | null;
  uri: string;
}

export interface AudioTrackInfo {
  group_id: string;
  name: string;
  language: string | null;
  uri: string | null;
}

export interface SegmentCheck {
  uri: string;
  ok: boolean;
  status_code: number | null;
  error: string | null;
}

export interface ManifestReport {
  passed: boolean;
  manifest_type: "hls" | "dash";
  manifest_url: string;
  renditions: RenditionInfo[];
  audio_tracks: AudioTrackInfo[];
  missing_required_renditions: string[];
  segments_checked: number;
  broken_segments: SegmentCheck[];
  issues: Issue[];
}

export interface CombinedReport {
  partner_name: string;
  content_title: string | null;
  passed: boolean;
  metadata_report: MetadataReport | null;
  manifest_report: ManifestReport | null;
}

export interface FeedFixture {
  id: string;
  label: string;
  sport: string;
  feed_format: FeedFormat;
  expected_valid: boolean;
  content?: string;
}

export interface ManifestFixture {
  id: string;
  label: string;
  sport: string;
  manifest_type: "hls" | "dash";
  expected_valid: boolean;
  manifest_url: string;
}
