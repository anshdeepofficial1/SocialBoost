"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Meter, Empty, PlatformMark } from "@/components/app/ui";

export default function Predictions() {
  const [videos, setVideos] = useState<any[]>([]);
  const [videoId, setVideoId] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["instagram", "youtube"]);
  const [caption, setCaption] = useState("");
  const [title, setTitle] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [duration, setDuration] = useState(30);
  const [res, setRes] = useState<any>(null);
  const [model, setModel] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const loadModel = () => {
    api.modelDetail().then(setModel).catch(() => setModel({ available: false }));
    api.predictionHistory(12).then(setHistory).catch(() => {});
  };

  useEffect(() => {
    api.listVideos().then(setVideos).catch(() => {});
    loadModel();
    const v = new URLSearchParams(window.location.search).get("video");
    if (v) setVideoId(v);
  }, []);

  const run = async () => {
    if (selectedPlatforms.length === 0) {
      setErr("Select Instagram Reels, YouTube Shorts, or both to run a prediction.");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const results = await Promise.all(selectedPlatforms.map(async (selectedPlatform) => {
        const payload: any = {
          platform: selectedPlatform,
          caption,
          // Instagram uses a caption; YouTube Shorts has a distinct title
          // and description, so this field should not leak into Instagram.
          title: selectedPlatform === "youtube" ? title : "",
          hashtags,
          duration_seconds: duration,
        };
        if (videoId) payload.video_id = videoId;
        try {
          return { platform: selectedPlatform, result: await api.predict(payload), error: "" };
        } catch (reason: any) {
          return { platform: selectedPlatform, result: null, error: reason?.message || "Prediction failed." };
        }
      }));
      setRes(results);
      loadModel();
    } catch (e: any) {
      setErr(e.message || "Could not run predictions.");
    } finally {
      setLoading(false);
    }
  };

  const results: any[] = Array.isArray(res) ? res : [];
  const pct = (v: number | null | undefined) =>
    v == null ? "—" : `${(v * 100).toFixed(0)}%`;

  return (
    <>
      <PageHeader
        eyebrow="Predictions · 03"
        title={<>Estimates, not promises.</>}
        description="Predict on Instagram Reels, YouTube Shorts, or both at once. Estimates are trained on synced/imported posts in this workspace and remain unavailable until there is enough real view data."
        actions={<Link href="/app/datasets" className="btn btn-ghost">Import history</Link>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel title="Inputs">
            <div className="space-y-3">
              <div>
                <label className="field-label" htmlFor="video">Video (optional)</label>
                <select id="video" className="field" value={videoId} onChange={(e) => setVideoId(e.target.value)}>
                  <option value="">No video — score the metadata only</option>
                  {videos.map((v) => <option key={v.id} value={v.id}>{v.original_name}</option>)}
                </select>
              </div>
              <div>
                <p className="field-label">Predict for</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {[
                    { id: "instagram", label: "Instagram Reels", detail: "Caption-led" },
                    { id: "youtube", label: "YouTube Shorts", detail: "Title + description" },
                  ].map((option) => (
                    <label key={option.id} className={`flex items-center gap-2.5 border px-3 py-3 cursor-pointer ${selectedPlatforms.includes(option.id) ? "border-[var(--ink)] bg-[var(--paper-2)]" : "border-[var(--hairline)]"}`}>
                      <input
                        type="checkbox"
                        checked={selectedPlatforms.includes(option.id)}
                        onChange={(e) => setSelectedPlatforms((current) => e.target.checked ? [...current, option.id] : current.filter((p) => p !== option.id))}
                      />
                      <PlatformMark platform={option.id} size={24} />
                      <span className="min-w-0">
                        <span className="block text-[12px] font-medium">{option.label}</span>
                        <span className="block mono text-[8px] uppercase tracking-[0.06em] text-[var(--muted)] mt-0.5">{option.detail}</span>
                      </span>
                    </label>
                  ))}
                </div>
                <p className="mono text-[8.5px] text-[var(--muted)] mt-2">Select one platform or both. Each is scored independently against your workspace model.</p>
              </div>
              <div>
                <label className="field-label" htmlFor="duration">Duration (s)</label>
                <input id="duration" type="number" min={0} max={3600} className="field" value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
              </div>
              <div>
                <label className="field-label" htmlFor="caption">Instagram caption / YouTube description</label>
                <textarea id="caption" className="field h-20 resize-y" placeholder="Write the caption you plan to publish…" value={caption} onChange={(e) => setCaption(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor="title">YouTube Shorts title (ignored for Instagram)</label>
                <input id="title" className="field" placeholder="A concise, specific YouTube title" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor="tags">Hashtags</label>
                <input id="tags" className="field" placeholder="#studio #reels" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
              </div>
            </div>
            {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}
            <button className="btn btn-signal mt-5" onClick={run} disabled={loading}>
              {loading ? "Running models…" : selectedPlatforms.length > 1 ? "Predict both platforms" : "Run prediction"}
            </button>
          </Panel>

          <Panel title="Model status" aside={model ? <span className={`tag ${model.available ? "tag-sage" : ""}`}>{model.available ? "trained" : "none"}</span> : undefined}>
            {model?.available ? (
              <>
                <dl>
                  <div className="kv"><dt>Version</dt><dd>{model.version}</dd></div>
                  <div className="kv"><dt>Trained</dt><dd>{model.trained_at ? new Date(model.trained_at).toLocaleDateString() : "—"}</dd></div>
                  <div className="kv"><dt>Samples</dt><dd>{model.n_samples ?? "—"}</dd></div>
                  <div className="kv"><dt>R²</dt><dd>{model.metrics?.r2 != null ? model.metrics.r2.toFixed(3) : "—"}</dd></div>
                  <div className="kv"><dt>MAE</dt><dd>{model.metrics?.mae != null ? Math.round(model.metrics.mae).toLocaleString() : "—"}</dd></div>
                  <div className="kv"><dt>Median views</dt><dd>{model.views_percentiles?.p50 != null ? Math.round(model.views_percentiles.p50).toLocaleString() : "—"}</dd></div>
                </dl>
                {model.top_features?.length > 0 && (
                  <div className="mt-4">
                    <p className="label mb-2">Top factors</p>
                    <ul className="space-y-1.5">
                      {model.top_features.map((f: any) => (
                        <li key={f.factor} className="flex items-center gap-2">
                          <span className="mono text-[9px] text-[var(--muted)] flex-1">{f.factor}</span>
                          <div className="w-20"><Meter value={f.importance * 100} tone="ink" /></div>
                          <span className="mono text-[9px] w-10 text-right">{f.importance.toFixed(3)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p className="text-[12px] leading-relaxed text-[var(--muted)]">
                No trained model yet. Sync your connected Instagram and YouTube accounts or import historical posts. At least 10 posts with real view counts are required; data will be pulled from connected accounts when available.
                Until then, a prediction returns <span className="text-[var(--ink)]">no score</span> and explains why.
              </p>
            )}
            <Link href="/app/datasets" className="btn btn-ghost btn-sm mt-4">Manage models</Link>
          </Panel>
        </div>

        <div className="space-y-4">
          {!res ? (
            <Panel title="Results">
              <Empty title="No prediction yet" body="Choose one or both platforms, enter your content metadata and run the model. Each result will show a range and confidence, or a data-related reason it cannot be scored." />
            </Panel>
          ) : (
            <div className="space-y-4">
              {results.map((entry: any) => {
                const platformName = entry.platform === "instagram" ? "Instagram Reels" : "YouTube Shorts";
                const result = entry.result;
                const scored = result && result.performance_score != null;
                return entry.error ? (
                  <Panel key={entry.platform} title={platformName} aside={<span className="tag tag-signal">error</span>}>
                    <p className="text-[12px] leading-relaxed text-[var(--muted)]">{entry.error}</p>
                  </Panel>
                ) : !scored ? (
                  <Panel key={entry.platform} title={platformName} aside={<span className="tag tag-signal">not scored</span>}>
                    <p className="font-display font-medium text-[18px] leading-snug">Not enough training data yet.</p>
                    <p className="text-[12.5px] text-[var(--muted)] leading-relaxed mt-3">{result?.note || "No model result was returned."}</p>
                    <Link href="/app/datasets" className="btn btn-signal btn-sm mt-5">Sync data & train</Link>
                  </Panel>
                ) : (
                  <div key={entry.platform} className="panel-ink p-6">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="mono text-[9px] uppercase tracking-[0.14em] text-[var(--night-muted)]">{platformName} · Performance score</p>
                        <div className="flex items-end gap-2 mt-4">
                          <span className="font-display font-semibold text-[58px] leading-none tracking-[-0.05em] text-[var(--porcelain)]">{result.performance_score}</span>
                          <span className="mono text-[10px] text-[var(--night-muted)] pb-2">/100</span>
                        </div>
                      </div>
                      <span className="tag tag-dark">{String(result.category).replace(/_/g, " ")}</span>
                    </div>
                    <div className="mt-4"><Meter value={result.performance_score} /></div>
                    <div className="grid grid-cols-3 gap-4 mt-6 pt-5 border-t border-[var(--night-line)]">
                      {[
                        ["Expected views", result.expected_views_low != null ? `${result.expected_views_low.toLocaleString()} – ${result.expected_views_high.toLocaleString()}` : "—"],
                        ["Engagement", pct(result.expected_engagement_rate)],
                        ["Confidence", pct(result.confidence)],
                      ].map(([key, value]) => (
                        <div key={key}>
                          <p className="mono text-[8px] uppercase tracking-[0.1em] text-[var(--night-muted)]">{key}</p>
                          <p className="mono text-[12px] text-[var(--night-soft)] mt-1.5">{value}</p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-4 mono text-[9px] leading-relaxed text-[var(--night-muted)]">{result.note}</p>
                    <div className="mt-4 pt-4 border-t border-[var(--night-line)]">
                      <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--night-muted)] mb-2">Most influential features</p>
                      <div className="flex flex-wrap gap-2">
                        {(result.factors || []).slice(0, 4).map((factor: any) => (
                          <span key={factor.factor} className="tag tag-dark">{factor.factor.replace(/_/g, " ")}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <Panel title={`Recent predictions · ${history.length}`} flush>
            {history.length === 0 ? (
              <div className="p-5"><p className="text-[12px] text-[var(--muted)]">No predictions stored yet. Every run is recorded with its model version.</p></div>
            ) : (
              <ul>
                {history.map((h) => (
                  <li key={h.id} className="flex items-center gap-3 px-5 py-3 border-b border-[var(--hairline)] last:border-b-0">
                    <PlatformMark platform={h.platform} size={20} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] truncate">
                        {h.performance_score == null ? "Not scored — no model" : `${h.performance_score}/100 · ${String(h.category).replace(/_/g, " ")}`}
                      </p>
                      <p className="mono text-[8.5px] text-[var(--muted)] mt-0.5">
                        {new Date(h.created_at).toLocaleString()} · {h.model_version}
                      </p>
                    </div>
                    <span className="mono text-[9px] text-[var(--muted)] shrink-0">{pct(h.confidence)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
