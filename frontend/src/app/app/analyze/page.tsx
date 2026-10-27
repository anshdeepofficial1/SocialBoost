"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Meter } from "@/components/app/ui";

const STEPS = [
  "Validate media",
  "Extract video features",
  "Extract speech & text",
  "Analyze hook",
  "Evaluate metadata",
  "Run available models",
];

export default function Analyze() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pick = (f: File | null) => {
    setErr("");
    if (f && !f.type.startsWith("video/")) {
      setErr("That file is not a video. Use MP4, MOV, WebM or MKV.");
      return;
    }
    setFile(f);
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setErr("");
    try {
      const r: any = await api.uploadVideo(file);
      setJobId(r.job_id);
      setVideoId(r.video_id);
      poll(r.job_id, r.video_id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setUploading(false);
    }
  };

  const poll = (id: string, vid: string) => {
    const iv = setInterval(async () => {
      try {
        const s = await api.jobStatus(id);
        setStatus(s);
        if (s.status === "done" || s.status === "failed") {
          clearInterval(iv);
          if (s.status === "done") router.push(`/app/analyze/${vid}`);
        }
      } catch {}
    }, 1500);
  };

  const progress = status?.progress ?? 0;
  const stepIndex = Math.min(STEPS.length - 1, Math.floor((progress / 100) * STEPS.length));

  return (
    <>
      <PageHeader
        eyebrow="Analyze · 01"
        title={
          <>
            Read the signal
            <br />
            before you publish.
          </>
        }
        description="Upload a Reel or Short. Features are extracted from the file itself; anything the pipeline cannot measure is shown as a gap."
        actions={<Link href="/app/library" className="btn btn-ghost">Open library</Link>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-4">
        <Panel title="Source media" aside={<span className="mono text-[9px] text-[var(--muted)]">MP4 · MOV · WEBM · MKV</span>}>
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0] || null); }}
            onClick={() => inputRef.current?.click()}
            className={`relative cursor-pointer border border-dashed transition-colors ${drag ? "border-[var(--signal)] bg-[#FBF1EC]" : "border-[var(--hairline-strong)] hover:border-[var(--ink)]"}`}
          >
            {preview ? (
              <div className="relative bg-[var(--night)]">
                <video src={preview} className="w-full max-h-[380px] object-contain" muted playsInline controls />
              </div>
            ) : (
              <div className="px-6 py-16 text-center">
                <div className="w-12 h-12 mx-auto border border-[var(--hairline-strong)] flex items-center justify-center">
                  <span className="w-0 h-0 border-y-[5px] border-y-transparent border-l-[8px] border-l-[var(--ink)]" />
                </div>
                <p className="mt-4 text-[13.5px] font-medium">Drop a video, or click to browse</p>
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-[var(--muted)] mt-2">Nothing leaves this machine</p>
              </div>
            )}
            <input ref={inputRef} type="file" accept="video/*" className="hidden" onChange={(e) => pick(e.target.files?.[0] || null)} />
          </div>

          {file && (
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
              <span className="text-[12px] truncate max-w-[240px]">{file.name}</span>
              <span className="mono text-[10px] text-[var(--muted)]">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              <button className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]" onClick={() => { setFile(null); setStatus(null); }}>
                Remove
              </button>
            </div>
          )}

          {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button className="btn btn-signal" onClick={upload} disabled={!file || uploading || !!status}>
              {uploading ? "Uploading…" : status ? "Analyzing…" : "Upload & analyze"}
            </button>
            {status?.status === "failed" && (
              <button className="btn btn-ghost" onClick={() => { setStatus(null); setJobId(null); }}>Try again</button>
            )}
            {videoId && status?.status === "done" && (
              <Link href={`/app/analyze/${videoId}`} className="btn btn-ghost">Open report</Link>
            )}
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel title="Pipeline" aside={status ? <span className="mono text-[9px] text-[var(--muted)]">{progress}%</span> : undefined}>
            <div className="mb-4"><Meter value={progress} /></div>
            <ol>
              {STEPS.map((s, i) => {
                const done = status && (progress >= ((i + 1) / STEPS.length) * 100 || status.status === "done");
                const active = status && !done && i === stepIndex;
                const partial = s === "Extract speech & text" && done;
                return (
                  <li key={s} className="flex items-center gap-3 py-2.5 border-b border-[var(--hairline)] last:border-b-0">
                    <span className="mono text-[9px] text-[var(--muted)] w-5">{String(i + 1).padStart(2, "0")}</span>
                    <span className={`flex-1 text-[12px] ${done || active ? "" : "text-[var(--muted)]"}`}>{s}</span>
                    {partial ? (
                      <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)]">limited</span>
                    ) : done ? (
                      <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--sage-ink)]">done</span>
                    ) : active ? (
                      <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)] pulse">running</span>
                    ) : (
                      <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)]">queued</span>
                    )}
                  </li>
                );
              })}
            </ol>
            {status?.current_step && (
              <p className="mt-4 mono text-[9.5px] text-[var(--muted)]">Current step: {status.current_step}</p>
            )}
            {status?.error && <p className="mt-2 text-[11.5px] text-[var(--red)]">{status.error}</p>}
          </Panel>

          <Panel title="What is measured">
            <dl>
              {[
                ["Duration & resolution", "Measured"],
                ["Frame rate & aspect", "Measured"],
                ["Brightness / contrast", "Measured"],
                ["Scene-change rhythm", "Measured"],
                ["Speech recognition", "Unavailable"],
                ["On-screen text", "Only if Tesseract is installed"],
              ].map(([k, v]) => (
                <div key={k} className="kv">
                  <dt className="text-[11.5px]">{k}</dt>
                  <dd className={`text-[9px] uppercase tracking-[0.08em] text-right ${v === "Measured" ? "text-[var(--muted)]" : "text-[var(--signal)]"}`}>{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 mono text-[9px] leading-relaxed text-[var(--muted)]">
              A missing capability is reported, never filled with a fabricated value.
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}
