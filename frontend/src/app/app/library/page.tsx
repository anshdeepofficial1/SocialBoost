"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { ArrowUpRight, ExternalLink, Film, RefreshCw } from "lucide-react";
import { PageHeader, Panel, Empty, PlatformMark } from "@/components/app/ui";

type LibraryPost = {
  id: string;
  post_id?: string;
  platform: string;
  url?: string | null;
  published_at?: string | null;
  title?: string | null;
  caption?: string | null;
  content_type?: string | null;
  duration_seconds?: number | null;
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
};

function count(value: number | null | undefined) {
  return value == null ? "—" : Number(value).toLocaleString();
}

export default function Library() {
  const [videos, setVideos] = useState<any[]>([]);
  const [posts, setPosts] = useState<LibraryPost[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"new" | "duration" | "views">("new");
  const [tab, setTab] = useState<"uploads" | "synced">("uploads");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    const [videoRows, postRows, accountRows] = await Promise.all([
      api.listVideos().catch(() => []),
      api.analyticsPosts().catch(() => []),
      api.socialAccounts().catch(() => []),
    ]);
    setVideos(videoRows);
    setPosts(postRows);
    setAccounts(accountRows);
    setLoading(false);
  };

  useEffect(() => { void load(); }, []);

  const isPlaceholder = (a: any) => typeof a?.handle === "string" && /^(instagram|youtube)-user-/i.test(a.handle);
  const connected = accounts.filter((a) =>
    a.mode === "oauth" && a.status === "connected" && !isPlaceholder(a) &&
    ["instagram", "youtube"].includes(a.platform)
  );

  const filteredVideos = useMemo(() => {
    const rows = videos.filter((v) => String(v.original_name || "").toLowerCase().includes(q.toLowerCase()));
    return [...rows].sort((a, b) =>
      sort === "duration"
        ? (Number(b.duration_seconds) || 0) - (Number(a.duration_seconds) || 0)
        : new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [videos, q, sort]);

  const filteredPosts = useMemo(() => {
    const rows = posts.filter((p) =>
      `${p.title || ""} ${p.caption || ""} ${p.platform} ${p.post_id || ""}`.toLowerCase().includes(q.toLowerCase())
    );
    return [...rows].sort((a, b) => sort === "views"
      ? (Number(b.views) || 0) - (Number(a.views) || 0)
      : new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime()
    );
  }, [posts, q, sort]);

  const syncNow = async () => {
    setRefreshing(true);
    await Promise.allSettled(connected.map((account) => api.syncSocial(account.id)));
    await load();
    setRefreshing(false);
  };

  const visibleCount = tab === "uploads" ? filteredVideos.length : filteredPosts.length;

  return (
    <>
      <PageHeader
        eyebrow="Library · 08"
        title={<>Your creative archive.</>}
        description="Uploaded files have full file-based analysis reports. Synced Instagram and YouTube posts show the provider data available to SocialBoost; source videos are not downloaded unless you upload them."
        actions={
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-ghost" onClick={syncNow} disabled={refreshing || connected.length === 0}>
              <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Syncing…" : "Sync accounts"}
            </button>
            <Link href="/app/analyze" className="btn btn-signal"><Film size={14} /> Upload & analyze</Link>
          </div>
        }
      />

      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
        <div className="inline-flex gap-1 border border-[var(--hairline)] p-1">
          <button
            className={`px-3 py-2 mono text-[9px] uppercase tracking-[0.08em] ${tab === "uploads" ? "bg-[var(--ink)] text-[var(--paper)]" : "text-[var(--muted)]"}`}
            onClick={() => { setTab("uploads"); setSort("new"); }}
          >Uploaded files · {videos.length}</button>
          <button
            className={`px-3 py-2 mono text-[9px] uppercase tracking-[0.08em] ${tab === "synced" ? "bg-[var(--ink)] text-[var(--paper)]" : "text-[var(--muted)]"}`}
            onClick={() => { setTab("synced"); setSort("new"); }}
          >Synced posts · {posts.length}</button>
        </div>
        <input className="field md:max-w-xs" placeholder={tab === "uploads" ? "Search uploaded filename…" : "Search synced title or caption…"} value={q} onChange={(e) => setQ(e.target.value)} />
        {tab === "uploads" ? (
          <select className="field !w-auto" value={sort === "duration" ? "duration" : "new"} onChange={(e) => setSort(e.target.value as "new" | "duration")}>
            <option value="new">Newest first</option>
            <option value="duration">Longest first</option>
          </select>
        ) : (
          <select className="field !w-auto" value={sort === "views" ? "views" : "new"} onChange={(e) => setSort(e.target.value as "new" | "views")}>
            <option value="new">Newest first</option>
            <option value="views">Most views</option>
          </select>
        )}
        <span className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] md:ml-auto">{visibleCount} shown</span>
      </div>

      {loading ? (
        <Panel title="Loading library"><p className="text-[12px] text-[var(--muted)]">Loading uploaded files and synced post metadata…</p></Panel>
      ) : tab === "uploads" ? (
        filteredVideos.length === 0 ? (
          <Panel title="Uploaded files">
            <Empty
              title={videos.length === 0 ? "No videos uploaded yet" : "No matches"}
              body={videos.length === 0 ? "Connect accounts to see synced post metadata, or upload a video file to run full OCR, speech and technical analysis." : "Try a different search term."}
              action={videos.length === 0 ? <Link href="/app/analyze" className="btn btn-signal btn-sm">Upload & analyze</Link> : undefined}
            />
          </Panel>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {filteredVideos.map((v) => (
              <Link key={v.id} href={`/app/analyze/${v.id}`} className="panel panel-hover overflow-hidden group">
                <div className="aspect-[16/10] bg-[var(--night)] relative flex items-center justify-center">
                  <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "repeating-linear-gradient(120deg, rgba(255,255,255,.06) 0 1px, transparent 1px 22px)" }} />
                  <div className="relative w-9 h-9 border border-[#4A4D40] flex items-center justify-center group-hover:border-[var(--signal)]">
                    <span className="w-0 h-0 border-y-[5px] border-y-transparent border-l-[8px] border-l-[var(--porcelain)] group-hover:border-l-[var(--signal)]" />
                  </div>
                  <span className="absolute top-2 right-2 mono text-[8.5px] text-[var(--night-body)] bg-[rgba(12,12,10,.72)] px-1.5 py-0.5">{v.duration_seconds?.toFixed(1)}s</span>
                  <span className="absolute bottom-2 left-2 mono text-[8px] uppercase tracking-[0.1em] text-[var(--night-muted)]">{v.aspect_ratio || "—"}</span>
                </div>
                <div className="p-3.5">
                  <p className="text-[12.5px] truncate group-hover:text-[var(--signal)]">{v.original_name}</p>
                  <div className="flex items-center justify-between gap-3 mt-2">
                    <span className="mono text-[8.5px] text-[var(--muted)]">{v.width && v.height ? `${v.width}×${v.height}` : "—"} · {v.fps ? `${v.fps.toFixed(0)}fps` : "—"}</span>
                    <span className="mono text-[8.5px] text-[var(--muted)]">{new Date(v.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)] mt-3">Open full analysis report →</p>
                </div>
              </Link>
            ))}
          </div>
        )
      ) : (
        filteredPosts.length === 0 ? (
          <Panel title="Synced posts">
            <Empty
              title={posts.length === 0 ? "No synced posts yet" : "No matches"}
              body={posts.length === 0 ? "Sync the connected Instagram and YouTube accounts. Public/provider metrics will appear here; you do not need to upload a CSV for recent posts." : "Try a different search term."}
              action={<Link href="/app/datasets" className="btn btn-signal btn-sm">Sync account data</Link>}
            />
          </Panel>
        ) : (
          <div className="space-y-2">
            {filteredPosts.map((post) => (
              <article key={post.id} className="panel p-4 md:p-5">
                <div className="flex items-start gap-3">
                  <PlatformMark platform={post.platform} size={28} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-[12.5px] font-semibold leading-snug">{post.title || "Untitled post"}</h3>
                      <span className="tag">{post.platform === "instagram" ? "Instagram" : "YouTube"}</span>
                      {post.content_type && <span className="tag">{post.content_type}</span>}
                    </div>
                    <p className="text-[11px] text-[var(--muted)] leading-relaxed mt-1 line-clamp-3">{post.caption || "No description/caption returned by the provider."}</p>
                    <p className="mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--muted)] mt-2">{post.published_at ? new Date(post.published_at).toLocaleString() : "Publish date unavailable"} · Post ID {post.post_id || "unavailable"}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
                      {[
                        ["Views", post.views],
                        ["Likes", post.likes],
                        ["Comments", post.comments],
                        ["Shares", post.shares],
                      ].map(([label, value]) => (
                        <span key={String(label)} className="mono text-[9px] text-[var(--muted)]">{label} <strong className="text-[var(--ink)]">{count(value as number | null)}</strong></span>
                      ))}
                    </div>
                  </div>
                  {post.url && (
                    <a href={post.url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm shrink-0" aria-label="Open source post">
                      <ExternalLink size={13} />
                    </a>
                  )}
                </div>
              </article>
            ))}
          </div>
        )
      )}
    </>
  );
}
