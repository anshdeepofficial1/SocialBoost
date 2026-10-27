"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Meter, Empty, PlatformMark } from "@/components/app/ui";

export default function Predictions() {
  const [videos, setVideos] = useState<any[]>([]);
  const [videoId, setVideoId] = useState("");
  const [platform, setPlatform] = useState("instagram");
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
    setLoading(true);
    setErr("");
    try {
      const payload: any = {
        platform,
        caption,
        title,
        hashtags,
        duration_seconds: duration,
      };
      // Only send a video_id when one was actually chosen. The backend scopes
      // this id to the workspace and 404s on unknown ids.
      if (videoId) payload.video_id = videoId;
      const r = await api.predict(payload);
      setRes(r);
      loadModel();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const scored = res && res.performance_score != null;
  const pct = (v: number | null | undefined) =>
    v == null ? "—" : `${(v * 100).toFixed(0)}%`;

  return (
    <>
      <PageHeader
        eyebrow="Predictions · 03"
        title={<>Estimates, not promises.</>}
        description="Model output is a range with a confidence value. When no model has been trained on your history, the app says so instead of inventing a number."
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="field-label" htmlFor="platform">Platform</label>
                  <select id="platform" className="field" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                    <option value="instagram">Instagram Reels</option>
                    <option value="youtube">YouTube Shorts</option>
                  </select>
                </div>
                <div>
                  <label className="field-label" htmlFor="duration">Duration (s)</label>
                  <input id="duration" type="number" min={0} max={3600} className="field" value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
                </div>
              </div>
              <div>
                <label className="field-label" htmlFor="caption">Caption</label>
                <textarea id="caption" className="field h-20 resize-y" placeholder="Write the caption you plan to publish…" value={caption} onChange={(e) => setCaption(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor="title">Title</label>
                <input id="title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor="tags">Hashtags</label>
                <input id="tags" className="field" placeholder="#studio #reels" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
              </div>
            </div>
            {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}
            <button className="btn btn-signal mt-5" onClick={run} disabled={loading}>
              {loading ? "Running model…" : "Run prediction"}
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
                No trained model yet. Import at least 10 historical posts, then train from the datasets page.
                Until then, a prediction returns <span className="text-[var(--ink)]">no score</span> and explains why.
              </p>
            )}
            <Link href="/app/datasets" className="btn btn-ghost btn-sm mt-4">Manage models</Link>
          </Panel>
        </div>

        <div className="space-y-4">
          {!res ? (
            <Panel title="Result">
              <Empty title="No prediction yet" body="Fill in the metadata and run the model. The result will show a range, category and confidence — or an explicit reason it cannot." />
            </Panel>
          ) : !scored ? (
            <Panel title="Result" aside={<span className="tag tag-signal">not scored</span>}>
              <p className="font-display font-medium text-[18px] leading-snug">No model is available for this workspace.</p>
              <p className="text-[12.5px] text-[var(--muted)] leading-relaxed mt-3">{res.note}</p>
              <Link href="/app/datasets" className="btn btn-signal btn-sm mt-5">Import & train</Link>
            </Panel>
          ) : (
            <>
              <div className="panel-ink p-6">
                <div className="flex items-start justify-between">
                  <p className="mono text-[9px] uppercase tracking-[0.14em] text-[var(--night-muted)]">Performance score</p>
                  <span className="tag tag-dark">{res.category.replace(/_/g, " ")}</span>
                </div>
                <div className="flex items-end gap-2 mt-4">
                  <span className="font-display font-semibold text-[68px] leading-none tracking-[-0.05em] text-[var(--porcelain)]">{res.performance_score}</span>
                  <span className="mono text-[10px] text-[var(--night-muted)] pb-2">/100</span>
                </div>
                <div className="mt-4"><Meter value={res.performance_score} /></div>
                <div className="grid grid-cols-3 gap-4 mt-6 pt-5 border-t border-[var(--night-line)]">
                  {[
                    ["Expected views", res.expected_views_low != null ? `${res.expected_views_low.toLocaleString()} – ${res.expected_views_high.toLocaleString()}` : "—"],
                    ["Engagement", pct(res.expected_engagement_rate)],
                    ["Confidence", pct(res.confidence)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="mono text-[8px] uppercase tracking-[0.1em] text-[var(--night-muted)]">{k}</p>
                      <p className="mono text-[12px] text-[var(--night-soft)] mt-1.5">{v}</p>
                    </div>
                  ))}
                </div>
              </div>

              <Panel title="Factors" flush>
                <ul>
                  {(res.factors || []).slice(0, 8).map((f: any, i: number) => (
                    <li key={i} className="flex items-center gap-4 px-5 py-3 border-b border-[var(--hairline)] last:border-b-0">
                      <span className="text-[12px] flex-1">{f.factor.replace(/_/g, " ")}</span>
                      <div className="w-24"><Meter value={(f.importance || 0) * 100} tone="ink" /></div>
                      <span className="mono text-[10px] text-[var(--muted)] w-20 text-right">
                        {typeof f.value === "number" ? f.value.toFixed(2) : String(f.value)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="px-5 py-4 mono text-[9px] leading-relaxed text-[var(--muted)]">{res.note}</p>
              </Panel>
            </>
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
