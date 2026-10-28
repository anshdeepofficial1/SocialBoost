const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sb_token");
}
export function setToken(t: string) { localStorage.setItem("sb_token", t); }
export function clearToken() { localStorage.removeItem("sb_token"); }

async function req(path: string, opts: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = { ...(opts.headers as any) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(opts.body instanceof FormData)) headers["Content-Type"] = headers["Content-Type"] || "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  signup: (email: string, password: string, full_name: string) => req("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, full_name }) }),
  login: (email: string, password: string) => req("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req("/auth/me"),
  uploadVideo: (file: File) => { const fd = new FormData(); fd.append("file", file); return req("/videos/upload", { method: "POST", body: fd }); },
  listVideos: () => req("/videos"),
  getVideo: (id: string) => req(`/videos/${id}`),
  deleteVideo: (id: string) => req(`/videos/${id}`, { method: "DELETE" }),
  jobStatus: (id: string) => req(`/analysis/job/${id}`),
  videoAnalysis: (id: string) => req(`/analysis/video/${id}`),
  caption: (caption: string, platform: string) => req("/analysis/caption", { method: "POST", body: JSON.stringify({ caption, platform }) }),
  hook: (hook_text: string, duration: number) => req("/analysis/hook", { method: "POST", body: JSON.stringify({ hook_text, duration }) }),
  predict: (payload: any) => req("/predictions/run", { method: "POST", body: JSON.stringify(payload) }),
  train: () => req("/predictions/train", { method: "POST" }),
  modelStatus: () => req("/predictions/status"),
  modelDetail: () => req("/predictions/model"),
  predictionHistory: (limit = 50) => req(`/predictions?limit=${limit}`),
  drafts: (videoId?: string) => req(`/drafts${videoId ? `?video_id=${encodeURIComponent(videoId)}` : ""}`),
  createDraft: (payload: any) => req("/drafts", { method: "POST", body: JSON.stringify(payload) }),
  updateDraft: (id: string, payload: any) => req(`/drafts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDraft: (id: string) => req(`/drafts/${id}`, { method: "DELETE" }),
  importCsv: (file: File) => { const fd = new FormData(); fd.append("file", file); return req("/datasets/import", { method: "POST", body: fd }); },
  datasetImports: () => req("/datasets/imports"),
  datasetTemplate: async () => {
    const token = getToken();
    const res = await fetch(`${BASE}/datasets/template`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(res.statusText || "Could not download the template");
    return res.blob();
  },
  calendarEvents: () => req("/calendar/events"),
  schedule: (payload: any) => req("/calendar/schedule", { method: "POST", body: JSON.stringify(payload) }),
  updateSchedule: (id: string, payload: any) => req(`/calendar/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  cancelSchedule: (id: string) => req(`/calendar/${id}/cancel`, { method: "POST" }),
  deleteSchedule: (id: string) => req(`/calendar/${id}`, { method: "DELETE" }),
  analyticsSummary: () => req("/analytics/summary"),
  analyticsPosts: (platform?: string) => req(`/analytics/posts${platform ? `?platform=${platform}` : ""}`),
  getPrefs: () => req("/settings/preferences"),
  updatePrefs: (payload: any) => req("/settings/preferences", { method: "PUT", body: JSON.stringify(payload) }),
  health: () => req("/health"),
  integrationsStatus: () => req("/integrations/status"),
  socialAccounts: () => req("/social/accounts"),
  socialSummary: () => req("/social/summary"),
  socialProviders: () => req("/social/providers"),
  connectSocial: (payload: any) => req("/social/accounts", { method: "POST", body: JSON.stringify(payload) }),
  syncSocial: (id: string) => req(`/social/accounts/${id}/sync`, { method: "POST" }),
  disconnectSocial: (id: string) => req(`/social/accounts/${id}`, { method: "DELETE" }),
  oauthStart: (platform: string) => req(`/social/oauth/${platform}/start`),
  youtubeDashboard: (channel: string, limit = 10) => req(`/youtube/dashboard?channel=${encodeURIComponent(channel)}&limit=${limit}`),
  youtubeCompetitors: (limit = 6) => req(`/youtube/competitors?limit=${limit}`),
};