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
            <Panel title="Opening / hook">
              <dl>
                <div className="kv"><dt>Hook window</dt><dd>{hook.hook_window_seconds ?? 3}s</dd></div>
                <div className="kv">
                  <dt>Speech onset</dt>
                  <dd className={hook.speech_onset_seconds == null ? "text-[var(--signal)]" : ""}>
                    {hook.speech_onset_seconds ?? "unavailable"}
                  </dd>
                </div>
                <div className="kv"><dt>On-screen text</dt><dd>{ocrAvailable ? `${hook.ocr_samples?.length ?? 0} samples` : "unavailable"}</dd></div>
              </dl>
              <p className="mt-4 text-[12px] leading-relaxed text-[var(--ink-2)]">
                {hook.opening_text
                  ? `“${hook.opening_text}”`
                  : ocrAvailable
                  ? "No readable on-screen text was found in the sampled frames."
                  : "No on-screen text was extracted. Tesseract is not installed in this build, so the opening copy is reported as unknown."}
              </p>
              {hook.speech_analysis === "unavailable" && hook.speech_note && (
                <p className="mt-3 mono text-[9px] leading-relaxed text-[var(--muted)] border-l border-[var(--signal)] pl-2.5">{hook.speech_note}</p>
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

          <Panel
            title="Reach estimate"
            aside={
              prediction?.model_version && prediction.model_version !== "none"
                ? <span className="tag tag-sage"><span className="dot" />model {prediction.model_version}</span>
                : <span className="tag tag-signal">no model</span>
            }
          >
            {prediction?.performance_score != null ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    ["Score", `${prediction.performance_score}/100`],
                    ["Expected views", `${prediction.expected_views_low?.toLocaleString()} – ${prediction.expected_views_high?.toLocaleString()}`],
                    ["Category", String(prediction.category).replace(/_/g, " ")],
                    ["Confidence", `${Math.round((prediction.confidence || 0) * 100)}%`],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)]">{k}</p>
                      <p className="font-display font-medium text-[18px] mt-1">{v}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-4 mono text-[9px] leading-relaxed text-[var(--muted)]">{prediction.note}</p>
              </>
            ) : (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <p className="text-[12.5px] text-[var(--ink-2)] leading-relaxed max-w-xl">
                    {prediction?.note || "This workspace has no trained model, so reach is not estimated. The analysis above is still measured from the file."}
                  </p>
                </div>
                <Link href="/app/datasets" className="btn btn-ghost btn-sm shrink-0">Train a model</Link>
              </div>
            )}
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
