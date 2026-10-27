"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import SiteNav from "@/components/SiteNav";
import { Reveal, SplitLines, Counter } from "@/components/motion/Reveal";

/* ---------------------------------------------------------------- visuals */

function Waveform({
  bars = 96,
  height = 74,
  accentFrom = 0.16,
  tone = "light",
  animate = true,
}: {
  bars?: number;
  height?: number;
  accentFrom?: number;
  tone?: "light" | "orange" | "dark";
  animate?: boolean;
}) {
  const vals = Array.from({ length: bars }, (_, i) => {
    const a = Math.abs(Math.sin(i * 0.31)) * 0.6 + Math.abs(Math.cos(i * 0.11)) * 0.4;
    return 0.18 + a * 0.82;
  });
  const dim = tone === "orange" ? "rgba(255,255,255,.42)" : tone === "dark" ? "#3A3A32" : "#CFCEC6";
  const accent = tone === "orange" ? "#FFFFFF" : "var(--signal)";
  return (
    <div className="flex items-center gap-[2px]" style={{ height }} aria-hidden="true">
      {vals.map((v, i) => {
        const inHook = i / bars < accentFrom;
        return (
          <span
            key={i}
            className={animate ? "wave-bar" : ""}
            style={{
              flex: 1,
              height: `${v * 100}%`,
              background: inHook ? accent : dim,
              animationDelay: animate ? `${i * 9}ms` : undefined,
              minWidth: 1,
              borderRadius: 1,
            }}
          />
        );
      })}
    </div>
  );
}

function StudioPreview() {
  const [t, setT] = useState(2.4);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setT((v) => (v >= 4.6 ? 1.2 : +(v + 0.08).toFixed(2))), 90);
    return () => window.clearInterval(id);
  }, []);
  const pct = (t / 6) * 100;

  return (
    <div className="panel overflow-hidden bg-[var(--paper)] shadow-[var(--shadow-lg)]">
      {/* window bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--hairline)] bg-[var(--paper-2)]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--signal)]" />
          <span className="text-[11px] font-semibold tracking-[0.02em] text-[var(--ink-2)]">Signal Studio · Analysis</span>
        </div>
        <span className="label">preview</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[1.3fr_1fr]">
        {/* media */}
        <div className="relative bg-[var(--night)] p-4">
          <div className="duotone relative aspect-[4/5] sm:aspect-[3/4] w-full rounded-[var(--r-sm)]">
            <div className="absolute left-4 top-4 right-4 z-10">
              <span className="mono text-[10px] tracking-[0.14em] text-white/70">no file loaded</span>
            </div>
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <div className="text-center px-6">
                <span className="inline-flex items-center justify-center w-11 h-11 rounded-full border border-white/30 mb-4">
                  <span className="w-0 h-0 border-y-[6px] border-y-transparent border-l-[9px] border-l-white/80 ml-0.5" />
                </span>
                <p className="label mb-1.5" style={{ color: "rgba(255,255,255,.6)" }}>your upload</p>
                <p className="font-display font-bold text-[15px] leading-tight text-white">9:16 · Reel or Short</p>
              </div>
            </div>
            {/* hook bracket */}
            <div className="absolute left-0 top-0 bottom-0 w-[27%] border-r border-dashed border-[var(--signal)] bg-[var(--signal)]/20 z-10" />
            <span className="absolute left-2.5 bottom-3 z-10 mono text-[9px] tracking-[0.14em] text-white">HOOK</span>
            {/* playhead */}
            <div className="absolute top-0 bottom-0 w-px bg-white z-10" style={{ left: `${pct}%` }} />
            <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-black/40 z-10">
              <div className="h-full bg-[var(--signal)] transition-all duration-100" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            {["vertical", "Reel · Short", "up to 90s"].map((x) => (
              <span key={x} className="mono text-[10px] text-white/50">{x}</span>
            ))}
          </div>
        </div>

        {/* findings */}
        <div className="p-5 space-y-4">
          <div>
            <p className="label mb-2">Hook score</p>
            <div className="flex items-baseline gap-1.5">
              <span className="font-display font-bold text-[46px] leading-none tracking-[-0.04em] text-[var(--muted)]">—</span>
              <span className="mono text-[11px] text-[var(--muted)]">/100 · heuristic</span>
            </div>
            <div className="meter mt-3"><span style={{ width: "0%" }} /></div>
          </div>

          <div className="space-y-2 pt-1">
            {[
              ["Speech onset", "unavailable"],
              ["Opening length", "not measured"],
              ["On-screen text", "not scanned"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-[12px]">
                <span className="text-[var(--muted)]">{k}</span>
                <span className="mono flex items-center gap-1.5 text-[var(--muted)]">
                  <span className="dot" style={{ background: "var(--hairline-strong)" }} />
                  {v}
                </span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-[var(--hairline)]">
            <p className="label mb-2">Recommendation</p>
            <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">Score, findings and suggestions appear once a video has been analyzed. Nothing is filled in before then.</p>
          </div>

          <div className="pt-3 border-t border-[var(--hairline)] flex items-center justify-between">
            <span className="tag"><span className="dot" />Awaiting upload</span>
            <span className="mono text-[10px] text-[var(--muted)]">—</span>
          </div>
        </div>
      </div>

      {/* waveform strip */}
      <div className="border-t border-[var(--hairline)] px-5 py-4 bg-[var(--paper-2)]">
        <div className="flex items-center justify-between mb-2.5">
          <span className="label">Audio envelope</span>
          <span className="mono text-[10px] text-[var(--muted)]">illustrative</span>
        </div>
        <Waveform bars={80} height={42} />
      </div>
    </div>
  );
}

function PlatformCard({ platform }: { platform: "instagram" | "youtube" }) {
  const ig = platform === "instagram";
  const tone = ig ? "var(--signal)" : "var(--cobalt)";
  return (
    <div className="panel panel-hover p-6 h-full">
      <div className="flex items-center justify-between">
        <span
          className="inline-flex items-center justify-center w-9 h-9 rounded-[10px] text-white font-display font-bold text-[13px]"
          style={{ background: tone }}
        >
          {ig ? "IG" : "YT"}
        </span>
        <span className="label">{ig ? "Reels" : "Shorts"}</span>
      </div>
      <div className="mt-5 aspect-[9/16] max-h-[220px] w-full rounded-[var(--r-sm)] overflow-hidden relative" style={{ background: `linear-gradient(160deg, ${tone}22, var(--paper-2))` }}>
        <div className="absolute inset-0 hairgrid opacity-60" />
        <div className="absolute inset-x-0 bottom-0 p-3">
          <div className="h-1.5 w-2/3 rounded-full bg-[var(--hairline-strong)] mb-2" />
          <div className="h-1.5 w-1/2 rounded-full bg-[var(--hairline)]" />
        </div>
      </div>
      <dl className="mt-4">
        <div className="kv"><dt>Format</dt><dd className="text-[var(--sage-ink)]">9:16 ✓</dd></div>
        <div className="kv"><dt>Duration cap</dt><dd>{ig ? "90s" : "60s"}</dd></div>
        <div className="kv"><dt>Placement</dt><dd>{ig ? "Reels tab" : "Shorts feed"}</dd></div>
        <div className="kv"><dt>Your evidence</dt><dd>no history yet</dd></div>
      </dl>
    </div>
  );
}

function PredictionChart() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 300);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="relative">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-[200px]" aria-hidden="true">
        {[20, 40, 60, 80].map((y) => (
          <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="rgba(255,255,255,.10)" strokeWidth="0.3" />
        ))}
        <line
          x1="0"
          y1="100"
          x2="100"
          y2="100"
          stroke="var(--night-line)"
          strokeWidth="1"
          strokeDasharray="2 3"
          vectorEffect="non-scaling-stroke"
          style={{ opacity: mounted ? 1 : 0, transition: "opacity .6s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 pointer-events-none">
        <p className="label mb-2">No model trained</p>
        <p className="text-[12.5px] leading-relaxed max-w-[280px]" style={{ color: "var(--night-muted)" }}>
          A predicted range appears here once your imported history trains a model. Until then the app shows a clearly labelled illustrative estimate.
        </p>
      </div>
      <div className="flex justify-between mt-2">
        {["W1", "W2", "W3", "W4", "W5", "W6"].map((w) => (
          <span key={w} className="mono text-[10px]" style={{ color: "var(--night-muted)" }}>{w}</span>
        ))}
      </div>
    </div>
  );
}

function CalendarSketch() {
  const days = Array.from({ length: 35 }, (_, i) => i);
  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="label">Month view</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]"><span className="dot" style={{ background: "var(--signal)" }} />Reels</span>
          <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]"><span className="dot" style={{ background: "var(--cobalt)" }} />Shorts</span>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-[4px]">
        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
          <span key={i} className="text-[10px] font-semibold text-[var(--muted)] text-center pb-1">{d}</span>
        ))}
        {days.map((d) => (
          <div key={d} className={`aspect-square rounded-[6px] p-1.5 relative ${inMonth(d) ? "bg-[var(--paper-2)]" : "bg-transparent"}`}>
            <span className="mono text-[9px] text-[var(--muted)]">{d + 1}</span>
          </div>
        ))}
      </div>
      <p className="mt-4 pt-4 border-t border-[var(--hairline)] text-[12px] leading-relaxed text-[var(--muted)] text-center">
        No releases scheduled. Drafts, sandbox jobs and published posts appear here.
      </p>
    </div>
  );
}
function inMonth(d: number) {
  return d % 7 !== 0 && d % 7 !== 6;
}

/* ------------------------------------------------------------------- page */

export default function Landing() {
  return (
    <main className="bg-[var(--canvas)] text-[var(--ink)] overflow-x-hidden">
      <SiteNav />

      {/* ============================== HERO ============================== */}
      <section className="relative pt-32 md:pt-40 pb-16 md:pb-24">
        <div className="absolute inset-0 -z-10 hairgrid opacity-40 [mask-image:linear-gradient(to_bottom,black,transparent_75%)]" />
        <div className="wrap">
          <div className="flex items-center justify-between gap-6 mb-10 md:mb-14">
            <span className="eyebrow">SocialBoost AI · Signal Studio</span>
            <span className="label hidden sm:inline-flex">Instagram + YouTube intelligence</span>
          </div>

          <div className="grid grid-cols-12 gap-8 items-end">
            <div className="col-span-12 lg:col-span-8">
              <h1 className="display-1">
                <SplitLines lines={["Make every", "second count."]} delay={80} stagger={110} />
              </h1>
            </div>
            <div className="col-span-12 lg:col-span-4 lg:pb-3">
              <Reveal delay={220}>
                <p className="lede max-w-md">
                  Know what to improve before you publish. Analyze your hooks, understand performance potential, and plan your Instagram and YouTube releases from one intelligent studio.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <Link href="/signup" className="btn btn-signal btn-lg">Analyze your first video</Link>
                  <Link href="/how-it-works" className="btn btn-ghost btn-lg">See the workflow</Link>
                </div>
                <p className="mt-5 mono text-[10px] tracking-[0.08em] text-[var(--muted)]">
                  NO CREDENTIALS REQUIRED · SANDBOX SCHEDULING
                </p>
              </Reveal>
            </div>
          </div>

          {/* preview + marginalia */}
          <div className="mt-14 md:mt-20 grid grid-cols-12 gap-6 md:gap-8 items-start">
            <div className="col-span-12 lg:col-span-8">
              <Reveal delay={120}><StudioPreview /></Reveal>
            </div>
            <aside className="col-span-12 lg:col-span-4">
              <Reveal delay={200}>
                <div className="panel p-6">
                  <p className="label mb-5">What you get</p>
                  <ol className="space-y-0">
                    {[
                      ["01", "Hook analysis", "Opening seconds, speech onset, on-screen text."],
                      ["02", "Technical signal", "Duration, aspect, brightness, scene rhythm."],
                      ["03", "Prediction range", "Estimates with uncertainty — never guarantees."],
                      ["04", "Platform fit", "Reels vs Shorts, side by side."],
                    ].map(([n, t, d]) => (
                      <li key={n} className="py-4 border-t border-[var(--hairline)] first:border-t-0 first:pt-0 flex gap-4">
                        <span className="num pt-0.5">{n}</span>
                        <div>
                          <p className="text-[13.5px] font-semibold">{t}</p>
                          <p className="text-[12px] text-[var(--muted)] mt-1 leading-relaxed">{d}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <div className="mt-5 pt-4 border-t border-[var(--hairline)] flex items-center justify-between">
                    <span className="tag tag-sage"><span className="dot" />Runs locally</span>
                    <Link href="/how-it-works" className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--signal)]">How it works →</Link>
                  </div>
                </div>
              </Reveal>
            </aside>
          </div>
        </div>
      </section>

      {/* ============================== METRIC STRIP ============================== */}
      <section className="border-y border-[var(--hairline)] bg-[var(--paper)]">
        <div className="wrap">
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-[var(--hairline)]">
            {[
              ["7", "analysis stages"],
              ["2", "platforms compared"],
              ["10", "posts to train a model"],
              ["0", "fabricated metrics"],
            ].map(([v, l], i) => (
              <Reveal key={l} delay={i * 70}>
                <div className="py-9 px-5 md:px-7">
                  <p className="display-3"><Counter value={Number(v)} /></p>
                  <p className="label mt-3">{l}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ============================== TICKER ============================== */}
      <section className="block-ink py-4 overflow-hidden">
        <div className="marquee-track">
          {[0, 1].map((dup) => (
            <div key={dup} className="flex items-center shrink-0">
              {["HOOK ANALYSIS", "TECHNICAL SIGNAL", "PREDICTION RANGE", "PLATFORM FIT", "PUBLISHING WINDOW", "TRANSCRIPT TIMING", "MODEL EVIDENCE", "SANDBOX PUBLISHING"].map((t) => (
                <span key={t + dup} className="flex items-center gap-8 px-8">
                  <span className="text-[12px] font-semibold tracking-[0.14em] text-[var(--night-body)]">{t}</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
                </span>
              ))}
            </div>
          ))}
        </div>
      </section>

      {/* ============================== PROBLEM ============================== */}
      <section className="section">
        <div className="wrap">
          <div className="grid grid-cols-12 gap-6 md:gap-10">
            <div className="col-span-12 md:col-span-3">
              <Reveal>
                <p className="label">01 — The problem</p>
                <div className="mt-6 hidden md:block">
                  <div className="h-px w-full bg-[var(--hairline)]" />
                  <p className="mt-4 mono text-[11px] leading-[2] text-[var(--muted)]">
                    PUBLISH → HOPE<br />→ REFRESH<br />→ GUESS AGAIN
                  </p>
                </div>
              </Reveal>
            </div>
            <div className="col-span-12 md:col-span-9">
              <Reveal>
                <h2 className="display-2 max-w-3xl">
                  Most creators publish<br />
                  <span className="text-[var(--muted)]">without knowing why</span><br />
                  anything works.
                </h2>
              </Reveal>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 mt-10 md:mt-14">
                <Reveal delay={80}>
                  <p className="lede">
                    A hook that lands, a frame that holds attention, a title that earns the click — these are measurable properties of your content, not luck. The trouble is they arrive after you post.
                  </p>
                </Reveal>
                <Reveal delay={160}>
                  <p className="lede">
                    Signal Studio reads the media before you publish: the opening seconds, the technical signal, the metadata. It shows what is measured, what is estimated, and what is simply unknown.
                  </p>
                </Reveal>
              </div>

              <Reveal delay={200}>
                <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {[
                    ["Measured", "Extracted from the file. Duration, resolution, frame rate, brightness, scene changes.", "var(--ink)", "#fff"],
                    ["Estimated", "Model output with a range and a confidence level. Always labelled.", "var(--signal)", "#fff"],
                    ["Unavailable", "Missing audio, OCR, or training data. Shown as a gap, never filled with a guess.", "var(--paper)", "var(--ink)"],
                  ].map(([t, d, bg, fg]) => (
                    <div key={t} className="rounded-[var(--r)] p-6 min-h-[200px] flex flex-col justify-between border border-[var(--hairline)]" style={{ background: bg as string, color: fg as string }}>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ opacity: .7 }}>Signal</span>
                      <div>
                        <p className="font-display font-bold text-[24px] tracking-[-0.02em]">{t}</p>
                        <p className="text-[12.5px] leading-relaxed mt-2" style={{ opacity: .78 }}>{d}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ============================== 02 ANALYZE ============================== */}
      <section className="section bg-[var(--paper)] border-y border-[var(--hairline)]">
        <div className="wrap">
          <div className="grid grid-cols-12 gap-6 md:gap-10 items-center">
            <div className="col-span-12 lg:col-span-5">
              <Reveal>
                <p className="label">02 — Analyze</p>
                <h2 className="display-2 mt-5">Read the<br />signal first.</h2>
                <p className="lede mt-6 max-w-md">
                  Upload a Reel or Short. The pipeline extracts real features from the file — no upload to a social platform, no guessing at what the video contains.
                </p>
                <ul className="mt-8 space-y-0 max-w-md">
                  {["Duration, resolution, frame rate, aspect ratio", "Brightness and contrast across sampled frames", "Scene-change frequency and silent sections", "Speech onset and on-screen text when available"].map((t) => (
                    <li key={t} className="py-3.5 border-t border-[var(--hairline)] flex items-start gap-3 text-[13.5px]">
                      <span className="mono text-[12px] text-[var(--signal)] pt-0.5">+</span>{t}
                    </li>
                  ))}
                </ul>
                <Link href="/app/analyze" className="btn btn-signal mt-8">Open the analyzer</Link>
              </Reveal>
            </div>
            <div className="col-span-12 lg:col-span-7">
              <Reveal delay={100}>
                <div className="panel-ink p-6 md:p-8 relative overflow-hidden">
                  <div className="absolute inset-0 hairgrid-dark opacity-50" />
                  <div className="relative">
                    <div className="flex items-center justify-between mb-7">
                      <span className="label">Pipeline</span>
                      <span className="tag tag-dark">what runs</span>
                    </div>
                    <ol className="space-y-0">
                      {[
                        ["01", "Validate media", ""],
                        ["02", "Extract video features", ""],
                        ["03", "Extract speech & text", "OCR N/A"],
                        ["04", "Analyze hook", ""],
                        ["05", "Evaluate metadata", ""],
                        ["06", "Run available models", ""],
                      ].map(([n, t, s]) => (
                        <li key={n} className="flex items-center gap-4 py-3.5 border-t border-[var(--night-line)] first:border-t-0">
                          <span className="mono text-[10px] w-5" style={{ color: "var(--night-muted)" }}>{n}</span>
                          <span className="flex-1 text-[13.5px] text-[var(--night-soft)]">{t}</span>
                          {s === "OCR N/A" && <span className="text-[10px] font-semibold tracking-[0.1em] text-[var(--signal)]">OCR N/A</span>}
                        </li>
                      ))}
                    </ol>
                    <p className="mt-7 mono text-[10px] leading-relaxed" style={{ color: "var(--night-muted)" }}>
                      STEPS MAP TO REAL JOB STATES. A FAILED STEP STOPS THE RUN AND SURFACES THE ERROR.
                    </p>
                  </div>
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ============================== 03 HOOK ============================== */}
      <section className="block-signal section">
        <div className="wrap">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <Reveal>
              <p className="label" style={{ color: "rgba(255,255,255,.72)" }}>03 — Find the hook</p>
              <h2 className="display-2 mt-5 max-w-2xl text-white">The first three<br />seconds decide.</h2>
            </Reveal>
            <Reveal delay={100}>
              <p className="lede max-w-sm md:text-right text-white/85" style={{ color: "rgba(255,255,255,.85)" }}>
                We isolate the opening interval, then show what is actually there: speech onset, on-screen text, and where the payoff lands.
              </p>
            </Reveal>
          </div>

          <Reveal delay={80}>
            <div className="rounded-[var(--r-lg)] overflow-hidden bg-[var(--night)] shadow-[var(--shadow-lg)]">
              <div className="grid grid-cols-1 lg:grid-cols-[1.05fr_1fr]">
                <div className="p-6 md:p-8 border-b lg:border-b-0 lg:border-r border-[var(--night-line)]">
                  <div className="flex items-center justify-between mb-6">
                    <span className="label">Opening timeline</span>
                    <span className="tag tag-dark">0:00 — 0:03</span>
                  </div>
                  <Waveform bars={70} height={96} accentFrom={0.42} tone="orange" />
                  <div className="flex justify-between mt-3">
                    {["0.0s", "1.0s", "2.0s", "3.0s", "4.0s", "5.0s", "6.0s"].map((t) => (
                      <span key={t} className="mono text-[9px]" style={{ color: "var(--night-muted)" }}>{t}</span>
                    ))}
                  </div>
                  <div className="mt-7 space-y-3.5">
                    {[
                      ["Speech onset", "—", "var(--night-muted)"],
                      ["Hook window", "first 3s", "var(--signal)"],
                      ["Payoff line", "—", "var(--night-muted)"],
                    ].map(([k, v, c]) => (
                      <div key={k} className="flex items-center gap-3">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
                        <span className="text-[13px] flex-1 text-[var(--night-soft)]">{k}</span>
                        <span className="mono text-[12px]" style={{ color: "var(--night-muted)" }}>{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="p-6 md:p-8">
                  <p className="label mb-5">What the Hook Lab reports</p>
                  <ul className="space-y-0">
                    {[
                      ["Opening window", "The first seconds of your file, isolated and timed."],
                      ["Speech onset", "Reported when speech recognition is available — stated as a gap when it is not."],
                      ["On-screen text", "Read from sampled frames when OCR is installed in the build."],
                      ["Alternatives", "Editable suggestions for a stronger opening — never retention predictions."],
                    ].map(([t, d]) => (
                      <li key={t} className="py-3.5 border-t border-[var(--night-line)] first:border-t-0 first:pt-0">
                        <p className="text-[13.5px] font-semibold text-[var(--night-soft)]">{t}</p>
                        <p className="text-[12.5px] leading-relaxed mt-1" style={{ color: "var(--night-muted)" }}>{d}</p>
                      </li>
                    ))}
                  </ul>
                  <Link href="/app/hook-lab" className="btn btn-dark mt-6">Open Hook Lab</Link>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================== 04 PREDICT ============================== */}
      <section className="section block-ink relative overflow-hidden">
        <div className="absolute inset-0 hairgrid-dark opacity-40" />
        <div className="wrap relative">
          <div className="grid grid-cols-12 gap-6 md:gap-10 items-start">
            <div className="col-span-12 lg:col-span-5">
              <Reveal>
                <p className="label">04 — Predict</p>
                <h2 className="display-2 mt-5 text-white">Estimates,<br />not promises.</h2>
                <p className="lede mt-6 max-w-md">
                  When a model has been trained on your imported history, it returns a range. When it has not, the app says so and falls back to a clearly labelled illustrative estimate.
                </p>
                <div className="mt-8 rounded-[var(--r)] border border-[var(--night-line)] p-5">
                  <p className="label mb-4">Model status</p>
                  {[
                    ["Trained on your history", "not yet", "var(--night-muted)"],
                    ["Method", "RandomForest", undefined],
                    ["Minimum rows", "10", undefined],
                  ].map(([k, v, c], i) => (
                    <div key={k} className={`flex items-center justify-between py-2.5 ${i > 0 ? "border-t border-[var(--night-line)]" : ""}`}>
                      <span className="text-[13px]" style={{ color: "var(--night-soft)" }}>{k}</span>
                      <span className="mono text-[11px]" style={{ color: (c as string) || "var(--night-muted)" }}>{v}</span>
                    </div>
                  ))}
                </div>
              </Reveal>
            </div>

            <div className="col-span-12 lg:col-span-7">
              <Reveal delay={100}>
                <div className="rounded-[var(--r)] border border-[var(--night-line)] p-6 md:p-8 bg-[rgba(255,255,255,.02)]">
                  <div className="flex items-center justify-between">
                    <span className="label">Relative performance</span>
                    <span className="tag tag-dark">Estimate</span>
                  </div>
                  <div className="mt-8">
                    <PredictionChart />
                  </div>
                  <div className="grid grid-cols-3 gap-4 mt-8 pt-6 border-t border-[var(--night-line)]">
                    {[
                      ["Expected range", "—"],
                      ["Category", "—"],
                      ["Confidence", "—"],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <p className="label mb-2">{k}</p>
                        <p className="mono text-[14px]" style={{ color: "var(--night-soft)" }}>{v}</p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-6 mono text-[10px] leading-relaxed" style={{ color: "var(--night-muted)" }}>
                    ESTIMATES ONLY — NEVER A MEASURED RESULT. SCORES ARE NOT VIRALITY PROBABILITIES.
                  </p>
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ============================== 05 PLATFORM ============================== */}
      <section className="section">
        <div className="wrap">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
            <Reveal>
              <p className="label">05 — Choose your platform</p>
              <h2 className="display-2 mt-5">One edit.<br />Two audiences.</h2>
            </Reveal>
            <Reveal delay={100}>
              <p className="lede max-w-sm md:text-right">The same asset is assessed against each platform's format, duration and metadata rules — with your own account history where it exists.</p>
            </Reveal>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <Reveal><PlatformCard platform="instagram" /></Reveal>
            <Reveal delay={100}><PlatformCard platform="youtube" /></Reveal>
          </div>

          <Reveal delay={140}>
            <div className="mt-6 panel p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="tag tag-sage mt-0.5"><span className="dot" />No verdict</span>
                <p className="text-[13px] text-[var(--muted)] max-w-2xl leading-relaxed">
                  With limited history the app will not declare a winner. It reports what each platform rewards and what to change, then leaves the decision to you.
                </p>
              </div>
              <Link href="/app/platform-comparison" className="btn btn-ghost btn-sm shrink-0">Compare a video</Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================== 06 SCHEDULE ============================== */}
      <section className="section bg-[var(--paper)] border-y border-[var(--hairline)]">
        <div className="wrap">
          <div className="grid grid-cols-12 gap-6 md:gap-10 items-center">
            <div className="col-span-12 lg:col-span-5 order-2 lg:order-1">
              <Reveal>
                <p className="label">06 — Time the release</p>
                <h2 className="display-2 mt-5">A plan,<br />not a pile.</h2>
                <p className="lede mt-6 max-w-md">
                  Drafts, scheduled jobs and published posts live on one calendar. Sandbox jobs are labelled as simulations. Nothing is reported as published until a platform confirms it.
                </p>
                <div className="mt-8 flex flex-wrap gap-2">
                  <span className="tag">Month</span>
                  <span className="tag">Week</span>
                  <span className="tag">Agenda</span>
                  <span className="tag tag-signal">Sandbox</span>
                </div>
                <Link href="/app/calendar" className="btn btn-signal mt-7">Open calendar</Link>
              </Reveal>
            </div>
            <div className="col-span-12 lg:col-span-7 order-1 lg:order-2">
              <Reveal delay={100}>
                <CalendarSketch />
                <div className="mt-3 flex items-center justify-between">
                  <span className="label">Timezone-aware · conflict checks</span>
                  <span className="label">Sandbox scheduling</span>
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ============================== CTA ============================== */}
      <section className="section block-ink relative overflow-hidden">
        <div className="absolute inset-0 hairgrid-dark opacity-40" />
        <div className="wrap relative">
          <div className="grid grid-cols-12 gap-8 items-end">
            <div className="col-span-12 lg:col-span-8">
              <Reveal>
                <p className="label">Start</p>
                <h2 className="display-2 mt-6 text-white">
                  Your next post<br />deserves a<br /><span className="text-[var(--signal)]">better plan.</span>
                </h2>
              </Reveal>
            </div>
            <div className="col-span-12 lg:col-span-4">
              <Reveal delay={120}>
                <p className="lede max-w-sm">Open the studio, upload one video, and read what is actually there before you publish.</p>
                <div className="mt-7 flex flex-col gap-3 max-w-xs">
                  <Link href="/signup" className="btn btn-signal btn-lg btn-block">Open Signal Studio</Link>
                  <Link href="/login" className="btn btn-dark btn-lg btn-block">Sign in</Link>
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ============================== FOOTER ============================== */}
      <footer className="block-ink border-t border-[var(--night-line)] pt-14 pb-10">
        <div className="wrap">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-8 pb-10 border-b border-[var(--night-line)]">
            <div>
              <p className="font-display font-bold tracking-[-0.03em] text-[26px] text-white">SIGNAL<span className="text-[var(--signal)]">.</span></p>
              <p className="label mt-2">Powered by SocialBoost AI</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/signup" className="btn btn-signal">Start free</Link>
              <Link href="/product" className="btn btn-dark">Product tour</Link>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-10">
            {[
              ["Product", [["Overview", "/product"], ["How it works", "/how-it-works"], ["Pricing", "/pricing"]]],
              ["Studio", [["Overview", "/app"], ["Analyze", "/app/analyze"], ["Hook Lab", "/app/hook-lab"]]],
              ["Account", [["Sign in", "/login"], ["Create account", "/signup"], ["Accounts", "/app/integrations"]]],
            ].map(([title, links]) => (
              <div key={title as string}>
                <p className="label mb-4">{title as string}</p>
                <ul className="space-y-2.5">
                  {(links as string[][]).map(([l, h]) => (
                    <li key={l}><Link href={h} className="text-[13px] text-[var(--night-body)] hover:text-white transition-colors">{l}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
            <div>
              <p className="label mb-4">Principle</p>
              <p className="text-[13px] text-[var(--night-body)] leading-relaxed">
                Every number is measured, estimated, or marked unavailable. Nothing is invented.
              </p>
            </div>
          </div>
          <div className="pt-7 border-t border-[var(--night-line)] flex flex-col sm:flex-row justify-between gap-3">
            <span className="text-[11px] text-[var(--night-muted)]">© 2026 Signal Studio — SocialBoost AI</span>
            <span className="text-[11px] text-[var(--night-muted)]">Local build · no fake metrics</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
