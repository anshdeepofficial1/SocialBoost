"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Panel, PlatformMark, Meter, Empty } from "@/components/app/ui";

export default function PlatformComparison() {
  const [caption, setCaption] = useState("");
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState(30);
  const [ig, setIg] = useState<any>(null);
  const [yt, setYt] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    if (!caption.trim()) {
      setErr("Enter the shared caption/description first. A YouTube title is scored separately.");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const [
        instagramCopy,
        youtubeTitle,
        youtubeDescription,
        instagramPrediction,
        youtubePrediction,
      ] = await Promise.all([
        api.caption(caption, "instagram", "caption"),
        title.trim() ? api.caption(title.trim(), "youtube", "title") : Promise.resolve(null),
        api.caption(caption, "youtube", "description"),
        api.predict({ platform: "instagram", caption, title: "", hashtags: "", duration_seconds: duration }),
        api.predict({ platform: "youtube", caption, title, hashtags: "", duration_seconds: duration }),
      ]);
      setIg({ caption: instagramCopy, pred: instagramPrediction });
      setYt({ title: youtubeTitle, description: youtubeDescription, pred: youtubePrediction });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const Column = ({ name, platform, data }: { name: string; platform: string; data: any }) => {
    const pred = data?.pred;
    const modelScored = pred && pred.performance_score != null;
    const copyResult = platform === "youtube" ? data?.title : data?.caption;
    const copyScore = copyResult
      ? Number(platform === "youtube" ? (copyResult.title_score ?? copyResult.caption_score) : copyResult.caption_score)
      : null;
    const copyIssues = copyResult?.issues || [];
    const description = platform === "youtube" ? data?.description : null;
    return (
      <section className="panel">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--hairline)]">
          <PlatformMark platform={platform} size={30} />
          <div>
            <p className="text-[13.5px] font-medium">{name}</p>
            <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)]">{platform === "instagram" ? "9:16 · up to 90s" : "9:16 · up to 60s"}</p>
          </div>
        </div>
        {!data ? (
          <div className="p-5"><p className="text-[12px] text-[var(--muted)]">Run the comparison to see this column.</p></div>
        ) : (
          <>
            <div className="p-5">
              {copyResult ? (
                <>
                  <div className="flex items-baseline justify-between">
                    <span className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)]">{platform === "youtube" ? "Title score · heuristic" : "Caption score · heuristic"}</span>
                    <span className="font-display font-semibold text-[28px] leading-none">{copyScore}<span className="mono text-[10px] text-[var(--muted)]">/100</span></span>
                  </div>
                  <div className="mt-3"><Meter value={copyScore || 0} tone={platform === "instagram" ? "signal" : "cobalt"} /></div>
                </>
              ) : (
                <div className="border border-dashed border-[var(--hairline-strong)] px-4 py-3">
                  <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)]">Title not scored</p>
                  <p className="text-[11.5px] text-[var(--muted)] leading-relaxed mt-1.5">Enter a YouTube Shorts title above. The description is scored separately below; it is not silently reused as the title.</p>
                </div>
              )}

              {modelScored ? (
                <dl className="mt-5">
                  <div className="kv"><dt>Performance</dt><dd>{pred.performance_score}/100</dd></div>
                  <div className="kv"><dt>Category</dt><dd>{String(pred.category).replace(/_/g, " ")}</dd></div>
                  <div className="kv"><dt>Expected views</dt><dd>{pred.expected_views_low?.toLocaleString()} – {pred.expected_views_high?.toLocaleString()}</dd></div>
                  <div className="kv"><dt>Confidence</dt><dd>{(pred.confidence * 100).toFixed(0)}%</dd></div>
                </dl>
              ) : (
                <div className="mt-5 border border-dashed border-[var(--hairline-strong)] px-4 py-3">
                  <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)]">No trained view model</p>
                  <p className="text-[11.5px] text-[var(--muted)] leading-relaxed mt-1.5">
                    Reach cannot be estimated until this workspace has enough real view-history data. The text checks below are transparent heuristics, not a view prediction.
                  </p>
                </div>
              )}
            </div>

            <div className="px-5 py-4 border-t border-[var(--hairline)]">
              {platform === "instagram" ? (
                <>
                  <p className="label mb-2">Caption notes</p>
                  <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">{copyResult?.improved_caption || "No caption was supplied."}</p>
                  {copyIssues.length > 0 && (
                    <ul className="mt-3 space-y-1.5">
                      {copyIssues.map((issue: string, index: number) => (
                        <li key={index} className="text-[11px] text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-2.5">{issue}</li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <>
                  <p className="label mb-2">YouTube title notes</p>
                  <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">{copyResult?.improved_title || "Add a title to receive title-specific feedback."}</p>
                  {copyIssues.length > 0 && (
                    <ul className="mt-3 space-y-1.5">
                      {copyIssues.map((issue: string, index: number) => (
                        <li key={index} className="text-[11px] text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-2.5">{issue}</li>
                      ))}
                    </ul>
                  )}
                  {copyResult?.alternative_titles?.length > 0 && (
                    <div className="mt-4">
                      <p className="label mb-2">Title angles to test</p>
                      <ul className="space-y-2">
                        {copyResult.alternative_titles.slice(0, 3).map((suggestion: string, index: number) => (
                          <li key={index} className="flex items-start gap-2 border-l border-[var(--hairline-strong)] pl-3">
                            <span className="mono text-[8.5px] text-[var(--muted)]">{String(index + 1).padStart(2, "0")}</span>
                            <span className="text-[11.5px] leading-relaxed">{suggestion}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {description && (
                    <div className="mt-5 pt-4 border-t border-[var(--hairline)]">
                      <div className="flex items-baseline justify-between gap-3">
                        <p className="label">YouTube description score · heuristic</p>
                        <span className="mono text-[11px] shrink-0">{description.caption_score}/100</span>
                      </div>
                      <p className="text-[12px] leading-relaxed text-[var(--ink-2)] mt-2">{description.improved_caption}</p>
                      {description.issues?.length > 0 && (
                        <ul className="mt-3 space-y-1.5">
                          {description.issues.map((issue: string, index: number) => (
                            <li key={index} className="text-[11px] text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-2.5">{issue}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </section>
    );
  };

  return (
    <>
      <PageHeader
        eyebrow="Platforms · 04"
        title={<>One edit. Two audiences.</>}
        description="Both platforms are evaluated in one run. Instagram gets caption-specific checks; YouTube Shorts gets a separate title score and description score. View estimates are shown only when a trained model and enough real history are available."
      />

      <Panel title="Shared asset" className="mb-4">
        <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-3">
          <div>
            <label className="field-label" htmlFor="caption">Instagram caption / YouTube description</label>
            <textarea id="caption" className="field h-[88px] resize-y" placeholder="Instagram caption and YouTube description…" value={caption} onChange={(e) => setCaption(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="title">Separate YouTube Shorts title</label>
            <input id="title" className="field" placeholder="Enter the title separately" value={title} onChange={(e) => setTitle(e.target.value)} />
            <label className="field-label mt-3" htmlFor="dur">Duration (s)</label>
            <input id="dur" type="number" min={0} max={3600} className="field" value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
          </div>
          <div className="flex items-end">
            <button className="btn btn-signal btn-block" onClick={run} disabled={loading}>
              {loading ? "Comparing…" : "Compare platforms"}
            </button>
          </div>
        </div>
        {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Column name="Instagram Reels" platform="instagram" data={ig} />
        <Column name="YouTube Shorts" platform="youtube" data={yt} />
      </div>

      <div className="mt-4 panel p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
        <div className="flex items-start gap-3">
          <span className="tag tag-sage mt-0.5"><span className="dot" />No verdict</span>
          <p className="text-[12px] text-[var(--muted)] max-w-2xl leading-relaxed">
            The app reports what each platform rewards. It does not claim one platform will outperform the other without evidence from your account history.
          </p>
        </div>
        <button className="btn btn-ghost btn-sm shrink-0" onClick={run} disabled={loading}>Run again</button>
      </div>
    </>
  );
}
