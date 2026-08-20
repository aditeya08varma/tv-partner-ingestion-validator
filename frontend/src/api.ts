import type {
  CombinedReport,
  FeedFixture,
  FeedFormat,
  ManifestFixture,
  ManifestReport,
  MetadataReport,
} from "./types";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function listFeedFixtures(): Promise<FeedFixture[]> {
  return asJson(await fetch("/api/mock/feeds"));
}

export async function getFeedFixture(id: string): Promise<FeedFixture> {
  return asJson(await fetch(`/api/mock/feeds/${id}`));
}

export async function listManifestFixtures(): Promise<ManifestFixture[]> {
  return asJson(await fetch("/api/mock/manifests"));
}

export async function validateMetadata(feedFormat: FeedFormat, content: string): Promise<MetadataReport> {
  const form = new FormData();
  form.set("feed_format", feedFormat);
  form.set("content", content);
  return asJson(await fetch("/api/validate/metadata", { method: "POST", body: form }));
}

export async function validateManifest(manifestUrl: string): Promise<ManifestReport> {
  const form = new FormData();
  form.set("manifest_url", manifestUrl);
  return asJson(await fetch("/api/validate/manifest", { method: "POST", body: form }));
}

export async function validateSubmission(params: {
  partnerName: string;
  contentTitle?: string;
  feedFormat?: FeedFormat;
  metadataContent?: string;
  manifestUrl?: string;
}): Promise<CombinedReport> {
  const form = new FormData();
  form.set("partner_name", params.partnerName);
  if (params.contentTitle) form.set("content_title", params.contentTitle);
  if (params.feedFormat) form.set("feed_format", params.feedFormat);
  if (params.metadataContent) form.set("metadata_content", params.metadataContent);
  if (params.manifestUrl) form.set("manifest_url", params.manifestUrl);
  return asJson(await fetch("/api/validate/submission", { method: "POST", body: form }));
}
