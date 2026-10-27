"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Stat, Panel, Empty, PlatformMark, StatusTag, Meter } from "@/components/app/ui";

export default function Overview() {
  const [summary, setSummary] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [posts, setPosts] = useState<any[]>([]);

  useEffect(() => {
    api.analyticsSummary().then(setSummary).catch(() => {});
    api.calendarEvents().then(setEvents).catch(() => {});
    api.listVideos().then(setVideos).catch(() => {});
    api.socialAccounts().then(setAccounts).catch(() => {});
    api.analyticsPosts().then(setPosts).catch(() => {});
  }, []);

  const upcoming = [...events]
    .filter((e) => e.status === "scheduled" || e.status === "processing")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());

  const ig = accounts.find((a) => a.platform === "instagram");
  const yt = accounts.find((a) => a.platform === "youtube");
  const connectedCount = accounts.length;

  const topPosts = [...posts].sort((a, b) => b.views - a.views).slice(0, 4);

  return (
    <>
      <PageHeader
        eyebrow="Control room"
        title={
          <>
            Your next release
            <br />
            starts here.
          </>
        }
        description="Everything measured, estimated and scheduled lives in one place. No vanity metrics — only what the data supports."
        actions={
          <>
            <Link href="/app/analyze" className="btn btn-signal">Analyze a video</Link>
            <Link href="/app/calendar" className="btn btn-ghost">Open calendar</Link>
          </>
        }
      />

      {/* connected accounts banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {[
          { p: "instagram", label: "Instagram Reels", acc: ig },
          { p: "youtube", label: "YouTube Shorts", acc: yt },
        ].map(({ p, label, acc }) => (
          <div key={p} className={`panel p-4 flex items-center gap-4 ${!acc ? "border-dashed" : ""}`}>
            <PlatformMark platform={p} size={34} />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium truncate">
                {acc ? `@${acc.handle}` : `Connect ${label}`}
              </p>
              <p className="mono text-[9px] tracking-[0.1em] uppercase text-[var(--muted)] mt-0.5">
                {acc
                  ? `${acc.mode} · ${acc.post_count} posts · ${acc.followers.toLocaleString()} followers`
                  : "No account linked yet"}
              </p>
            </div>
            {acc ? (
              <div className="text-right shrink-0">
                <p className="mono text-[11px]">{acc.avg_views.toLocaleString()}</p>
                <p className="mono text-[8px] uppercase text-[var(--muted)]">avg views</p>
              </div>
            ) : (
              <Link href="/app/integrations" className="btn btn-ghost btn-sm shrink-0">Connect</Link>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Stat label="Videos analyzed" value={summary?.videos ?? 0} hint="uploaded to this workspace" />
        <Stat label="Analyses run" value={summary?.analyses ?? 0} hint="all jobs, including re-runs" />
        <Stat label="Historical posts" value={summary?.historical_posts ?? 0} hint="imported performance rows" />
        <Stat
          label="Total views"
          value={(summary?.total_views ?? 0).toLocaleString()}
          hint={`${((summary?.engagement_rate ?? 0) * 100).toFixed(2)}% engagement`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4 mb-4">
        <Panel
          title="Publishing timeline"
          aside={<Link href="/app/calendar" className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]">Calendar →</Link>}
          flush
        >
          {upcoming.length === 0 ? (
            <div className="p-5">
              <Empty
                title="Nothing scheduled"
                body="Queue a release from the calendar. Sandbox jobs are labelled and never reported as published."
                action={<Link href="/app/calendar" className="btn btn-ghost btn-sm">Schedule a post</Link>}
              />
            </div>
          ) : (
            <ul>
              {upcoming.slice(0, 6).map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-5 py-3 border-b border-[var(--hairline)] last:border-b-0">
                  <PlatformMark platform={e.platform} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] truncate">{e.title || e.caption || "Untitled release"}</p>
                    <p className="mono text-[9px] text-[var(--muted)] mt-0.5">
                      {new Date(e.scheduled_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>
                  <StatusTag status={e.is_sandbox && e.status !== "scheduled" ? "sandbox" : e.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Next actions">
          <ol className="space-y-0">
            {[
              { done: connectedCount >= 2, label: "Connect both accounts", href: "/app/integrations" },
              { done: (summary?.videos ?? 0) > 0, label: "Analyze your first video", href: "/app/analyze" },
              { done: (summary?.historical_posts ?? 0) >= 10, label: "Import 10+ historical posts", href: "/app/datasets" },
              { done: upcoming.length > 0, label: "Schedule one release", href: "/app/calendar" },
            ].map((s, i) => (
              <li key={s.label} className="flex items-center gap-3 py-2.5 border-b border-[var(--hairline)] last:border-b-0">
                <span
                  className="w-4 h-4 border flex items-center justify-center mono text-[8px] shrink-0"
                  style={{
                    borderColor: s.done ? "var(--sage-deep)" : "var(--hairline-strong)",
                    background: s.done ? "var(--sage)" : "transparent",
                    color: s.done ? "var(--sage-ink)" : "var(--muted)",
                  }}
                >
                  {s.done ? "✓" : String(i + 1).padStart(2, "0")}
                </span>
                <Link href={s.href} className={`text-[12px] flex-1 hover:text-[var(--signal)] ${s.done ? "text-[var(--muted)] line-through" : ""}`}>
                  {s.label}
                </Link>
                <span className="mono text-[9px] text-[var(--muted)]">→</span>
              </li>
            ))}
          </ol>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="Recent videos" aside={<Link href="/app/library" className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]">Library →</Link>} className="lg:col-span-1" flush>
          {videos.length === 0 ? (
            <div className="p-5"><p className="text-[12px] text-[var(--muted)]">No uploads yet.</p></div>
          ) : (
            <ul>
              {videos.slice(0, 4).map((v) => (
                <li key={v.id} className="px-4 py-3 border-b border-[var(--hairline)] last:border-b-0">
                  <Link href={`/app/analyze/${v.id}`} className="flex items-center gap-3 group">
                    <span className="w-8 h-10 bg-[var(--night)] shrink-0 flex items-center justify-center">
                      <span className="w-0 h-0 border-y-[3px] border-y-transparent border-l-[5px] border-l-[var(--porcelain)]" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[12px] truncate group-hover:text-[var(--signal)]">{v.original_name}</span>
                      <span className="block mono text-[8.5px] text-[var(--muted)] mt-0.5">
                        {v.duration_seconds?.toFixed(1)}s · {v.aspect_ratio || "—"}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Top posts" className="lg:col-span-2" flush>
          {topPosts.length === 0 ? (
            <div className="p-5">
              <Empty title="No history yet" body="Import a CSV of past posts to unlock model training and platform evidence." action={<Link href="/app/datasets" className="btn btn-ghost btn-sm">Import CSV</Link>} />
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--hairline)]">
                  {["Platform", "Published", "Views", "Engagement"].map((h) => (
                    <th key={h} className="text-left mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] px-4 py-2 font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {topPosts.map((p) => (
                  <tr key={p.id} className="border-b border-[var(--hairline)] last:border-b-0">
                    <td className="px-4 py-2.5"><PlatformMark platform={p.platform} size={20} /></td>
                    <td className="px-4 py-2.5 mono text-[10.5px] text-[var(--muted)]">
                      {p.published_at ? new Date(p.published_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-2.5 mono text-[11px]">{p.views == null ? "—" : Number(p.views).toLocaleString()}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-16"><Meter value={Math.min(100, p.engagement_rate * 1000)} tone="ink" /></div>
                        <span className="mono text-[10px] text-[var(--muted)]">{(p.engagement_rate * 100).toFixed(2)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </>
  );
}
