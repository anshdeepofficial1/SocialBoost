"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Empty } from "@/components/app/ui";

export default function Library() {
  const [videos, setVideos] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"new" | "duration">("new");

  useEffect(() => { api.listVideos().then(setVideos).catch(() => {}); }, []);

  const filtered = useMemo(() => {
    const rows = videos.filter((v) => v.original_name.toLowerCase().includes(q.toLowerCase()));
    return [...rows].sort((a, b) => sort === "duration" ? (b.duration_seconds || 0) - (a.duration_seconds || 0) : new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [videos, q, sort]);

  return (
    <>
      <PageHeader
        eyebrow="Library · 07"
        title={<>Your creative archive.</>}
        description="Every upload with its measured properties. Open a report to see the full analysis."
        actions={<Link href="/app/analyze" className="btn btn-signal">Upload video</Link>}
      />

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input className="field max-w-xs" placeholder="Search by filename…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="field !w-auto" value={sort} onChange={(e) => setSort(e.target.value as any)}>
          <option value="new">Newest first</option>
          <option value="duration">Longest first</option>
        </select>
        <span className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] ml-auto">{filtered.length} of {videos.length} videos</span>
      </div>

      {filtered.length === 0 ? (
        <Panel title="Library">
          <Empty
            title={videos.length === 0 ? "No videos yet" : "No matches"}
            body={videos.length === 0 ? "Upload a Reel or Short to run the analysis pipeline." : "Try a different search term."}
            action={videos.length === 0 ? <Link href="/app/analyze" className="btn btn-signal btn-sm">Analyze a video</Link> : undefined}
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {filtered.map((v) => (
            <Link key={v.id} href={`/app/analyze/${v.id}`} className="panel panel-hover overflow-hidden group">
              <div className="aspect-[16/10] bg-[var(--night)] relative flex items-center justify-center">
                <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "repeating-linear-gradient(120deg, rgba(255,255,255,.06) 0 1px, transparent 1px 22px)" }} />
                <div className="relative w-9 h-9 border border-[#4A4D40] flex items-center justify-center group-hover:border-[var(--signal)]">
                  <span className="w-0 h-0 border-y-[5px] border-y-transparent border-l-[8px] border-l-[var(--porcelain)] group-hover:border-l-[var(--signal)]" />
                </div>
                <span className="absolute top-2 right-2 mono text-[8.5px] text-[var(--night-body)] bg-[rgba(12,12,10,.72)] px-1.5 py-0.5">
                  {v.duration_seconds?.toFixed(1)}s
                </span>
                <span className="absolute bottom-2 left-2 mono text-[8px] uppercase tracking-[0.1em] text-[var(--night-muted)]">{v.aspect_ratio || "—"}</span>
              </div>
              <div className="p-3.5">
                <p className="text-[12.5px] truncate group-hover:text-[var(--signal)]">{v.original_name}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="mono text-[8.5px] text-[var(--muted)]">
                    {v.width && v.height ? `${v.width}×${v.height}` : "—"} · {v.fps ? `${v.fps.toFixed(0)}fps` : "—"}
                  </span>
                  <span className="mono text-[8.5px] text-[var(--muted)]">{new Date(v.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
