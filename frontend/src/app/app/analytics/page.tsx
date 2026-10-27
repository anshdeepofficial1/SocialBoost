"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell,
} from "recharts";
import { PageHeader, Panel, Stat, PlatformMark, Empty } from "@/components/app/ui";

export default function Analytics() {
  const [summary, setSummary] = useState<any>(null);
  const [posts, setPosts] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [platform, setPlatform] = useState("all");
  const [sort, setSort] = useState<"views" | "date" | "engagement">("date");

  useEffect(() => {
    api.analyticsSummary().then(setSummary).catch(() => {});
    api.analyticsPosts().then(setPosts).catch(() => {});
    api.socialAccounts().then(setAccounts).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    let rows = platform === "all" ? posts : posts.filter((p) => p.platform === platform);
    rows = [...rows].sort((a, b) => {
      if (sort === "views") return Number(b.views || 0) - Number(a.views || 0);
      if (sort === "engagement") return Number(b.engagement_rate || 0) - Number(a.engagement_rate || 0);
      return new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime();
    });
    return rows;
  }, [posts, platform, sort]);

  const trend = useMemo(() => {
    const rows = (platform === "all" ? posts : posts.filter((p) => p.platform === platform))
      .filter((p) => p.published_at)
      .sort((a, b) => new Date(a.published_at).getTime() - new Date(b.published_at).getTime());
    return rows.map((p) => ({
      date: new Date(p.published_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      views: p.views == null ? null : Number(p.views),
      engagement: p.engagement_rate == null ? null : +(p.engagement_rate * 100).toFixed(2),
    }));
  }, [posts, platform]);

  const byPlatform = useMemo(() => {
    const src = summary?.by_platform;
    if (src) {
      return (["instagram", "youtube"] as const)
        .filter((p) => src[p])
        .map((p) => ({
          platform: p === "instagram" ? "Instagram" : "YouTube",
          views: src[p].views == null ? null : Number(src[p].views),
          posts: src[p].posts || 0,
        }));
    }
    const map: Record<string, { platform: string; views: number; posts: number }> = {};
    posts.forEach((p) => {
      const k = p.platform;
      map[k] ||= { platform: k === "instagram" ? "Instagram" : "YouTube", views: 0, posts: 0 };
      map[k].views += p.views;
      map[k].posts += 1;
    });
    return Object.values(map);
  }, [posts, summary]);

  const exportCsv = () => {
    const head = "platform,published_at,views,likes,comments,shares,engagement_rate\n";
    const body = filtered.map((p) => [p.platform, p.published_at, p.views, p.likes, p.comments, p.shares, p.engagement_rate].join(",")).join("\n");
    const blob = new Blob([head + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "socialboost-posts.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader
        eyebrow="Analytics · 06"
        title={<>Actuals, not vibes.</>}
        description="This view combines imported history with posts synced from connected platforms. Metrics the provider does not return remain missing — they are never estimated."
        actions={<button className="btn btn-ghost" onClick={exportCsv} disabled={filtered.length === 0}>Export CSV</button>}
      />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <Stat label="Total views" value={!summary ? "—" : summary.total_views == null ? "—" : Number(summary.total_views).toLocaleString()} hint="Across posts with view data" />
        <Stat label="Total reach" value={!summary ? "—" : summary.total_reach == null ? "—" : Number(summary.total_reach).toLocaleString()} hint="Accounts reached, when available" />
        <Stat label="Saves" value={!summary ? "—" : summary.total_saves == null ? "—" : Number(summary.total_saves).toLocaleString()} hint="Times posts were saved" />
        <Stat label="Follows gained" value={!summary ? "—" : summary.total_follows == null ? "—" : Number(summary.total_follows).toLocaleString()} hint="From available history" />
        <Stat label="Engagement" value={!summary || summary.engagement_rate == null ? "—" : `${(summary.engagement_rate * 100).toFixed(2)}%`} hint="Likes + comments + shares / views" />
        <Stat label="Posts" value={summary?.historical_posts ?? "—"} hint={summary?.source || "Checking data"} />
      </div>

      <div className="panel panel-hover flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 md:px-5 mb-5">
        <div className="flex items-start gap-3">
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-[10px] bg-[var(--signal-soft)] text-[var(--signal-deep)] font-bold" aria-hidden="true">↗</span>
          <div>
            <p className="text-[12.5px] font-semibold">Your data source</p>
            <p className="text-[11px] leading-relaxed text-[var(--muted)] mt-1">{summary?.source || "Checking imported and connected data…"}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[.1em] text-[var(--muted)]">Connected channels</p>
            <p className="font-display font-bold text-[19px] mt-0.5">{accounts.filter((a) => !/^(instagram|youtube)-user-/i.test(a.handle || "") && a.mode === "oauth" && a.status === "connected").length} <span className="text-[11px] font-medium text-[var(--muted)]">live-linked</span></p>
          </div>
          <Link href="/app/integrations" className="btn btn-ghost btn-sm">Manage</Link>
        </div>
      </div>

      {posts.length === 0 ? (
        <Panel title="No history">
          <Empty
            title="Nothing to chart yet"
            body="Connect your Instagram professional account and sync it, or import a CSV of past posts. SocialBoost will chart the data available to it."
            action={<Link href="/app/datasets" className="btn btn-signal btn-sm">Import CSV</Link>}
          />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 mb-4">
            <Panel
              title="Views over time"
              aside={
                <select className="field !py-1.5 !text-[10px] !w-auto" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                  <option value="all">All platforms</option>
                  <option value="instagram">Instagram</option>
                  <option value="youtube">YouTube</option>
                </select>
              }
            >
              <div className="h-[240px] -ml-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="viewsFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#F0501F" stopOpacity={0.24} />
                        <stop offset="100%" stopColor="#F0501F" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#E4E3DD" strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 9, fontFamily: "var(--font-mono)", fill: "#6E6E66" }} tickLine={false} axisLine={{ stroke: "#E4E3DD" }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 9, fontFamily: "var(--font-mono)", fill: "#6E6E66" }} tickLine={false} axisLine={false} width={44} />
                    <Tooltip
                      contentStyle={{ background: "#FFFFFF", border: "1px solid #E4E3DD", borderRadius: 2, fontSize: 11, fontFamily: "var(--font-mono)" }}
                      labelStyle={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.1em", color: "#6E6E66" }}
                    />
                    <Area type="monotone" dataKey="views" stroke="#F0501F" strokeWidth={1.6} fill="url(#viewsFill)" dot={{ r: 2, fill: "#F0501F", strokeWidth: 0 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Views by platform">
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={byPlatform} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke="#E4E3DD" strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="platform" tick={{ fontSize: 9, fontFamily: "var(--font-mono)", fill: "#6E6E66" }} tickLine={false} axisLine={{ stroke: "#E4E3DD" }} />
                    <YAxis tick={{ fontSize: 9, fontFamily: "var(--font-mono)", fill: "#6E6E66" }} tickLine={false} axisLine={false} width={44} />
                    <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E4E3DD", borderRadius: 2, fontSize: 11, fontFamily: "var(--font-mono)" }} />
                    <Bar dataKey="views" barSize={44}>
                      {byPlatform.map((b) => <Cell key={b.platform} fill={b.platform === "Instagram" ? "#F0501F" : "#2B3AD4"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <Panel
            title={`Posts · ${filtered.length}`}
            flush
            aside={
              <select className="field !py-1.5 !text-[10px] !w-auto" value={sort} onChange={(e) => setSort(e.target.value as any)}>
                <option value="date">Newest first</option>
                <option value="views">Most views</option>
                <option value="engagement">Best engagement</option>
              </select>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] min-w-[640px]">
                <thead>
                  <tr className="border-b border-[var(--hairline)] bg-[var(--paper-2)]">
                    {["Platform", "Published", "Views", "Likes", "Comments", "Shares", "Engagement"].map((h) => (
                      <th key={h} className="text-left mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] px-4 py-2 font-normal whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.id} className="border-b border-[var(--hairline)] last:border-b-0 hover:bg-[var(--paper-2)]">
                      <td className="px-4 py-2.5"><PlatformMark platform={p.platform} size={20} /></td>
                      <td className="px-4 py-2.5 mono text-[10px] text-[var(--muted)] whitespace-nowrap">{p.published_at ? new Date(p.published_at).toLocaleDateString() : "—"}</td>
                      <td className="px-4 py-2.5 mono">{p.views == null ? "—" : Number(p.views).toLocaleString()}</td>
                      <td className="px-4 py-2.5 mono">{p.likes.toLocaleString()}</td>
                      <td className="px-4 py-2.5 mono">{p.comments.toLocaleString()}</td>
                      <td className="px-4 py-2.5 mono">{p.shares.toLocaleString()}</td>
                      <td className="px-4 py-2.5 mono text-[var(--signal)]">{p.engagement_rate == null ? "—" : (p.engagement_rate * 100).toFixed(2) + "%"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
