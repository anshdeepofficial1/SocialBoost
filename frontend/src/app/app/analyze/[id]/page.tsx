"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Meter, StatusTag, Empty, PlatformMark } from "@/components/app/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function AnalysisReport() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;
  const [data, setData] = useState<any>(null);
  const [video, setVideo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.videoAnalysis(id).catch((e) => { setErr(e.message); return null; }),
      api.getVideo(id).catch(() => null),
    ]).then(([a, v]) => { setData(a); setVideo(v); }).finally(() => setLoading(false));
  }, [id]);

  const remove = async () => {
    if (!id || !confirm("Delete this video and its analysis? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await api.deleteVideo(id);
      router.push("/app/library");
    } catch (e: any) {
      setErr(e.message);
      setDeleting(false);
    }
  };

  if (loading) return <p className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Loading report…</p>;
  if (err) return <div className="panel p-6"><p className="text-[12px] text-[var(--red)]">{err}</p><Link href="/app/analyze" className="btn btn-ghost btn-sm mt-4 inline-flex">Back to analyze</Link></div>;
  if (!data) return <Empty title="No report" body="This video has no analysis yet." action={<Link href="/app/analyze" className="btn btn-signal btn-sm">Analyze a video</Link>} />;

  const r = data.result || {};
  const tech = r.technical || {};
  const hook = r.hook || {};
  const meta = r.metadata_analysis || {};
  const recs = r.recommendations || [];
  const prediction = meta.prediction || null;
  const platformPredictions = meta.predictions_by_platform || { instagram: prediction };
  const predictionPlatforms = [{ id: "instagram", label: "Instagram Reels" }, { id: "youtube", label: "YouTube Shorts" }];
  const ocrAvailable = hook.ocr_available === true;

  return (
    <>
      <div className="flex items-center gap-2 mono text-[9px] uppercase tracking-[0.12em] text-[var(--muted)] mb-4">
        <Link href="/app" className="hover:text-[var(--ink)]">Studio</Link>
        <span>/</span>
        <Link href="/app/library" className="hover:text-[var(--ink)]">Library</Link>
        <span>/</span>
        <span className="text-[var(--ink)]">Report</span>
      </div>

      <PageHeader
        eyebrow={`Analysis report · ${id.slice(0, 8)}`}
        title={video?.original_name || `Video ${id.slice(0, 8)}`}
        description={<>Status <StatusTag status={data.status} /> — results are extracted from the file and labelled by confidence.</>}
        actions={<>
          <Link href={`/app/predictions?video=${id}`} className="btn btn-signal">Run prediction</Link>
          <Link href="/app/library" className="btn btn-ghost">Library</Link>
          <button className="btn btn-ghost" onClick={remove} disabled={deleting}>{deleting ? "Deleting…" : "Delete"}</button>
        </>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 items-start">
        <div className="space-y-4 lg:sticky lg:top-6">
          <div className="panel overflow-hidden">
            <div className="bg-[var(--night)] aspect-[9/16] max-h-[420px] flex items-center justify-center">
              {video?.filename ? (
                <video
                  src={`${API_BASE}/uploads/${video.filename}`}
                  className="w-full h-full object-contain"
                  controls
                  playsInline
                  preload="metadata"
                />
              ) : (
                <div className="text-center px-6">
                  <span className="mono text-[9px] tracking-[0.16em] text-[var(--night-muted)]">PREVIEW UNAVAILABLE</span>
                </div>
              )}
            </div>
            <dl className="p-4">
              <div className="kv"><dt>Duration</dt><dd>{tech.duration_seconds?.toFixed(2) ?? "—"}s</dd></div>
              <div className="kv"><dt>Resolution</dt><dd>{tech.width && tech.height ? `${tech.width}×${tech.height}` : "—"}</dd></div>
              <div className="kv"><dt>Aspect</dt><dd>{tech.aspect_ratio || "—"}</dd></div>
              <div className="kv"><dt>Frame rate</dt><dd>{tech.fps?.toFixed(2) ?? "—"} fps</dd></div>
              <div className="kv"><dt>File size</dt><dd>{video?.size_bytes ? `${(video.size_bytes / 1024 / 1024).toFixed(2)} MB` : "—"}</dd></div>
            </dl>
          </div>

          <Panel title="Hook score" aside={<span className="tag">heuristic</span>}>
            <div className="flex items-baseline gap-2">
              <span className="font-display font-semibold text-[46px] leading-none tracking-[-0.04em]">{hook.hook_score ?? "—"}</span>
              <span className="mono text-[10px] text-[var(--muted)]">/100</span>
            </div>
            <div className="mt-3"><Meter value={hook.hook_score ?? 0} /></div>
            <p className="mt-3 text-[11.5px] text-[var(--muted)] leading-relaxed">{hook.notes || "No hook notes recorded."}</p>
            {hook.score_basis?.length > 0 && (
              <ul className="mt-3 space-y-1">
                {hook.score_basis.map((b: string, i: number) => (
                  <li key={i} className="mono text-[9px] leading-relaxed text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-2.5">{b}</li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Technical signal" aside={<span className="tag tag-sage"><span className="dot" />measured</span>}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {[
                ["Avg brightness", tech.avg_brightness != null ? tech.avg_brightness.toFixed(1) : "—", "/ 255"],
                ["Avg contrast", tech.avg_contrast != null ? tech.avg_contrast.toFixed(1) : "—", "std dev"],
                ["Scene changes", tech.scene_changes_sampled ?? "—", "sampled"],
                ["Frame samples", tech.frame_samples ?? "—", "analyzed"],
                ["Black frames", tech.black_frames ?? 0, "detected"],
                ["Aspect fit", meta.aspect_ratio_ok ? "Pass" : "Review", "9:16 preferred"],
              ].map(([k, v, h]) => (
                <div key={k as string}>
                  <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)]">{k}</p>
                  <p className="font-display font-medium text-[20px] mt-1">{v}</p>
                  <p className="mono text-[8.5px] text-[var(--muted)]">{h}</p>
                </div>
              ))}
            </div>
          </Panel>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Panel title="Opening · speech + screen text">
              <dl>
                <div className="kv"><dt>Hook window</dt><dd>{hook.hook_window_seconds ?? 3}s</dd></div>
                <div className="kv"><dt>Speech status</dt><dd>{String(hook.speech_analysis || "not recorded").replace(/_/g, " ")}</dd></div>
                <div className="kv"><dt>First speech</dt><dd>{hook.speech_onset_seconds == null ? "Not detected" : `${Number(hook.speech_onset_seconds).toFixed(2)}s`}</dd></div>
                <div className="kv"><dt>Detected language</dt><dd>{hook.speech_language ? `${hook.speech_language}${hook.speech_language_probability != null ? ` · ${Math.round(hook.speech_language_probability * 100)}%` : ""}` : "Unknown"}</dd></div>
                <div className="kv"><dt>OCR engine</dt><dd>{hook.ocr_engine || (ocrAvailable ? "Available" : "Unavailable")}</dd></div>
                <div className="kv"><dt>Screen-text samples</dt><dd>{hook.ocr_segments?.length ?? hook.ocr_samples?.length ?? 0}</dd></div>
              </dl>
              <div className="mt-4">
                <p className="label mb-2">Opening text</p>
                <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">{hook.opening_text || "No readable overlay text was found in the sampled opening frames."}</p>
              </div>
              <div className="mt-4 border-t border-[var(--hairline)] pt-4">
                <p className="label mb-2">Speech transcript</p>
                {hook.speech_transcript ? (
                  <>
                    <p className="text-[12px] leading-relaxed text-[var(--ink-2)] whitespace-pre-wrap">{hook.speech_transcript}</p>
                    {hook.speech_transcript_truncated && <p className="mono text-[8.5px] text-[var(--signal)] mt-2">Transcript limited to the opening audio window; the full video was not transcribed.</p>}
                  </>
                ) : <p className="text-[11px] leading-relaxed text-[var(--muted)]">{hook.speech_note || "No transcript was returned for this file."}</p>}
              </div>
              {(hook.ocr_segments?.length > 0 || hook.speech_segments?.length > 0) && (
                <div className="mt-4 border-t border-[var(--hairline)] pt-4">
                  <p className="label mb-2">Timed evidence</p>
                  {hook.ocr_segments?.length > 0 && (
                    <ul className="space-y-2">
                      {hook.ocr_segments.slice(0, 8).map((line: any, index: number) => {
                        const alignment = (hook.screen_text_alignment || []).find((item: any) => item.text === line.text && item.time_seconds === line.time_seconds);
                        return (
                          <li key={`ocr-${index}`} className="border-l border-[var(--hairline-strong)] pl-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="mono text-[8.5px] text-[var(--muted)]">{Number(line.time_seconds || 0).toFixed(2)}s</span>
                              {line.confidence != null && <span className="tag">{Math.round(Number(line.confidence) * 100)}% OCR confidence</span>}
                              {alignment?.spoken_match === true && <span className="tag tag-sage">Matches speech</span>}
                              {alignment?.spoken_match === false && alignment?.nearby_speech && <span className="tag tag-signal">Words differ</span>}
                            </div>
                            <p className="text-[11.5px] leading-relaxed mt-1">{line.text}</p>
                            {alignment?.nearby_speech && <p className="text-[10px] text-[var(--muted)] mt-1">Nearby speech: {alignment.nearby_speech}</p>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {hook.speech_segments?.length > 0 && (
                    <ul className="space-y-1.5 mt-3">
                      {hook.speech_segments.slice(0, 10).map((segment: any, index: number) => (
                        <li key={`speech-${index}`} className="flex items-start gap-3 text-[10.5px]">
                          <span className="mono text-[8.5px] text-[var(--muted)] shrink-0">{Number(segment.start).toFixed(2)}–{Number(segment.end).toFixed(2)}s</span>
                          <span className="leading-relaxed">{segment.text}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </Panel>

            <Panel title="Format & metadata">
              <div className="space-y-2.5">
                {[
                  ["Aspect ratio", meta.aspect_ratio_ok],
                  ["Duration", meta.duration_ok],
                  ["Resolution", meta.resolution_ok],
                ].map(([k, ok]) => (
                  <div key={k as string} className="flex items-center justify-between">
                    <span className="text-[12px]">{k}</span>
                    <span className={`mono text-[9px] uppercase tracking-[0.1em] ${ok ? "text-[var(--sage-ink)]" : "text-[var(--signal)]"}`}>
                      {ok ? "pass" : "review"}
                    </span>
                  </div>
                ))}
              </div>
              {meta.issues?.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {meta.issues.map((i: string, n: number) => (
                    <li key={n} className="text-[11.5px] leading-relaxed text-[var(--muted)] border-l border-[var(--signal)] pl-3">{i}</li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel title="Platform-specific reach estimates" aside={<span className="tag">Workspace ML · Random Forest</span>}>
            <p className="text-[11.5px] leading-relaxed text-[var(--muted)] mb-4">The same analysed clip is scored separately for Instagram Reels and YouTube Shorts. These ranges are estimates from your workspace's real view history, not guarantees.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {predictionPlatforms.map((platform) => {
                const result = platformPredictions[platform.id];
                const scored = result?.performance_score != null;
                return (
                  <section key={platform.id} className="border border-[var(--hairline)] p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformMark platform={platform.id} size={24} />
                      <h3 className="text-[13px] font-semibold">{platform.label}</h3>
                    </div>
                    {scored ? (
                      <>
                        <div className="flex items-baseline gap-2">
                          <span className="font-display text-[34px] font-semibold">{result.performance_score}</span>
                          <span className="mono text-[9px] text-[var(--muted)]">/100 · {Math.round((result.confidence || 0) * 100)}% confidence</span>
                        </div>
                        <div className="mt-3"><Meter value={result.performance_score} tone={platform.id === "instagram" ? "signal" : "cobalt"} /></div>
                        <dl className="mt-3">
                          <div className="kv"><dt>Expected views</dt><dd>{result.expected_views_low == null ? "—" : `${Number(result.expected_views_low).toLocaleString()}–${Number(result.expected_views_high).toLocaleString()}`}</dd></div>
                          <div className="kv"><dt>Category</dt><dd>{String(result.category || "unknown").replace(/_/g, " ")}</dd></div>
                          <div className="kv"><dt>Model version</dt><dd>{result.model_version || "unknown"}</dd></div>
                        </dl>
                        <p className="mono text-[8.5px] text-[var(--muted)] mt-3 leading-relaxed">{result.note}</p>
                      </>
                    ) : (
                      <div>
                        <p className="text-[12px] font-medium">No score yet</p>
                        <p className="text-[11px] text-[var(--muted)] mt-2 leading-relaxed">{result?.note || "No trained model result was returned for this platform."}</p>
                        <Link href="/app/datasets" className="btn btn-ghost btn-sm mt-3">Sync account data & train</Link>
                      </div>
                    )}
                  </section>
                );
              })}
            </div>
          </Panel>

          <Panel title={`Recommendations · ${recs.length}`} flush>
            {recs.length === 0 ? (
              <div className="p-5"><p className="text-[12px] text-[var(--muted)]">No recommendations were generated.</p></div>
            ) : (
              <ul>
                {recs.map((rec: any, i: number) => (
                  <li key={i} className="flex gap-4 px-5 py-4 border-b border-[var(--hairline)] last:border-b-0">
                    <span className="mono text-[9px] text-[var(--signal)] pt-0.5">{String(i + 1).padStart(2, "0")}</span>
                    <div className="flex-1">
                      <p className="text-[13px] font-medium">{rec.problem}</p>
                      <p className="text-[12px] text-[var(--muted)] mt-1 leading-relaxed">{rec.fix}</p>
                      {rec.evidence && <p className="mono text-[8.5px] text-[var(--muted)] mt-2">{rec.evidence}</p>}
                    </div>
                    <span className="tag shrink-0">{rec.area || "general"}</span>
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
