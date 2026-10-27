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
    setLoading(true);
    setErr("");
    try {
      const [a, b, c, d] = await Promise.all([
        api.caption(caption, "instagram"),
        api.caption(caption, "youtube"),
        api.predict({ platform: "instagram", caption, title, hashtags: "", duration_seconds: duration }),
        api.predict({ platform: "youtube", caption, title, hashtags: "", duration_seconds: duration }),
      ]);
      setIg({ caption: a, pred: c });
      setYt({ caption: b, pred: d });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const Column = ({ name, platform, data }: { name: string; platform: string; data: any }) => {
    const pred = data?.pred;
    const scored = pred && pred.performance_score != null;
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
              <div className="flex items-baseline justify-between">
                <span className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)]">Caption score</span>
                <span className="font-display font-semibold text-[28px] leading-none">{data.caption.caption_score}<span className="mono text-[10px] text-[var(--muted)]">/100</span></span>
              </div>
              <div className="mt-3"><Meter value={data.caption.caption_score} tone={platform === "instagram" ? "signal" : "cobalt"} /></div>

              {scored ? (
                <dl className="mt-5">
                  <div className="kv"><dt>Performance</dt><dd>{pred.performance_score}/100</dd></div>
                  <div className="kv"><dt>Category</dt><dd>{String(pred.category).replace(/_/g, " ")}</dd></div>
                  <div className="kv"><dt>Expected views</dt><dd>{pred.expected_views_low?.toLocaleString()} – {pred.expected_views_high?.toLocaleString()}</dd></div>
                  <div className="kv"><dt>Confidence</dt><dd>{(pred.confidence * 100).toFixed(0)}%</dd></div>
                </dl>
              ) : (
                <div className="mt-5 border border-dashed border-[var(--hairline-strong)] px-4 py-3">
                  <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)]">No model</p>
                  <p className="text-[11.5px] text-[var(--muted)] leading-relaxed mt-1.5">
                    Reach cannot be estimated until this workspace has a trained model. The caption rules below still apply.
                  </p>
                </div>
              )}
            </div>

            <div className="px-5 py-4 border-t border-[var(--hairline)]">
              <p className="label mb-2">Caption notes</p>
              <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">{data.caption.improved_caption}</p>
              {data.caption.issues?.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {data.caption.issues.map((i: string, n: number) => (
                    <li key={n} className="text-[11px] text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-2.5">{i}</li>
                  ))}
                </ul>
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
        description="The same asset is scored against each platform's caption rules and format expectations. With limited history, no winner is declared."
      />

      <Panel title="Shared asset" className="mb-4">
        <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-3">
          <div>
            <label className="field-label" htmlFor="caption">Caption</label>
            <textarea id="caption" className="field h-[88px] resize-y" placeholder="Write one caption to compare…" value={caption} onChange={(e) => setCaption(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="title">Title</label>
            <input id="title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} />
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
