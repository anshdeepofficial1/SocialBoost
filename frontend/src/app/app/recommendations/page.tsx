"use client";

import { useEffect, useState } from "react";
import { api, syncConnectedAccountsIfNeeded } from "@/lib/api";
import Link from "next/link";
import { ArrowUpRight, BarChart3, Users, Video } from "lucide-react";
import { PageHeader, Panel, Empty, PlatformMark } from "@/components/app/ui";

const AREA_LABEL: Record<string, string> = {
  technical: "Technical",
  hook: "Hook",
  prediction: "Prediction",
  account: "Account data",
  performance: "Performance",
  model: "ML model",
  competitor: "Competitors",
  sync: "Sync",
};

type Recommendation = {
  area: string;
  problem: string;
  fix: string;
  evidence?: string;
  video?: string;
  videoId?: string;
  href?: string;
  action?: string;
  platform?: string;
};

function countLabel(value: number | null | undefined) {
  return value == null ? "Unavailable" : Number(value).toLocaleString();
}

export default function Recommendations() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [videos, initialSummary, initialPosts, initialAccounts] = await Promise.all([
        api.listVideos().catch(() => []),
        api.analyticsSummary().catch(() => null),
        api.analyticsPosts().catch(() => []),
        api.socialAccounts().catch(() => []),
      ]);
      const storedPostCounts: Record<string, number> = {
        instagram: Number(initialSummary?.by_platform?.instagram?.posts ?? initialPosts.filter((post: any) => post.platform === "instagram").length),
        youtube: Number(initialSummary?.by_platform?.youtube?.posts ?? initialPosts.filter((post: any) => post.platform === "youtube").length),
      };
      await syncConnectedAccountsIfNeeded(initialAccounts, storedPostCounts);
      const [summary, posts, accounts, model, coach, winners] = await Promise.all([
        api.analyticsSummary().catch(() => initialSummary),
        api.analyticsPosts().catch(() => initialPosts),
        api.socialAccounts().catch(() => initialAccounts),
        api.modelDetail().catch(() => ({ available: false })),
        api.coachStatus().catch(() => ({ available: false })),
        api.coachWinners().catch(() => ({ available: false, top_posts: [] })),
      ]);

      const all: Recommendation[] = [];
      const reports = await Promise.allSettled(
        videos.map(async (video: any) => ({
          video,
          report: await api.videoAnalysis(video.id),
        }))
      );
      for (const outcome of reports) {
        if (outcome.status !== "fulfilled") continue;
        const { video, report } = outcome.value;
        for (const recommendation of report.result?.recommendations || []) {
          all.push({
            ...recommendation,
            video: video.original_name,
            videoId: video.id,
            href: `/app/analyze/${video.id}`,
            action: "Open video report",
          });
        }
      }

      const platformPosts: Record<string, any[]> = {
        instagram: posts.filter((post: any) => post.platform === "instagram"),
        youtube: posts.filter((post: any) => post.platform === "youtube"),
      };
      const labels: Record<string, string> = {
        instagram: "Instagram Reels",
        youtube: "YouTube Shorts",
      };
      const liveAccounts = accounts.filter((account: any) =>
        account.mode === "oauth" && account.status === "connected" &&
        ["instagram", "youtube"].includes(account.platform)
      );

      if (liveAccounts.length === 0) {
        all.push({
          area: "account",
          problem: "Connect your real Instagram and YouTube channels",
          fix: "Link each platform through Accounts, then sync. SocialBoost will fetch the public/account-authorised metrics it is allowed to access; CSV history is optional for data providers cannot return.",
          evidence: "No live-linked provider accounts were returned by the account API.",
          href: "/app/integrations",
          action: "Connect accounts",
        });
      }

      for (const account of liveAccounts) {
        const platform = account.platform;
        const history = platformPosts[platform] || [];
        const named = labels[platform] || platform;
        if (history.length === 0) {
          all.push({
            area: "sync",
            platform,
            problem: `${named} is connected, but no post history has been synced`,
            fix: "Fetch the latest available uploads and metrics so Overview, Analytics, Recommendations and training all use the same post records.",
            evidence: `Account ${account.handle || account.display_name || "connected"} is OAuth-linked; stored post rows for this platform: 0.`,
            href: "/app/datasets",
            action: "Sync account data",
          });
          continue;
        }

        const withViews = history.filter((post: any) => post.views != null).sort(
          (a: any, b: any) => Number(b.views) - Number(a.views)
        );
        const averageViews = withViews.length
          ? Math.round(withViews.reduce((sum: number, post: any) => sum + Number(post.views), 0) / withViews.length)
          : null;
        if (withViews[0]) {
          const top = withViews[0];
          all.push({
            area: "performance",
            platform,
            problem: `Review the strongest recent ${named} post before planning the next one`,
            fix: "Compare its opening, subject, duration and headline/caption with your lower-view posts. Treat it as a useful experiment, not proof that one feature caused the result.",
            evidence: `Highest recorded views in stored ${named} history: ${countLabel(top.views)} on “${(top.title || top.caption || "Untitled post").slice(0, 100)}”. Sample size: ${withViews.length} posts with view data; average: ${countLabel(averageViews)} views.`,
            href: "/app/analytics",
            action: "Compare post history",
          });
        } else {
          all.push({
            area: "performance",
            platform,
            problem: `Public view counts are not available for stored ${named} posts`,
            fix: "Use provider metrics when available or import older view-count history. The app will not invent view values for training.",
            evidence: `${history.length} post records exist, but none has a known view count.`,
            href: "/app/datasets",
            action: "Review training data",
          });
        }

        const staleAt = account.last_synced_at ? new Date(account.last_synced_at).getTime() : 0;
        if (!staleAt || Date.now() - staleAt > 24 * 60 * 60 * 1000) {
          all.push({
            area: "sync",
            platform,
            problem: `${named} data may be out of date`,
            fix: "Run a fresh sync before drawing conclusions or training a new model.",
            evidence: account.last_synced_at ? `Last sync: ${new Date(account.last_synced_at).toLocaleString()}.` : "No last-sync timestamp is available.",
            href: "/app/integrations",
            action: "Refresh account",
          });
        }
      }

      const totalWithViews = posts.filter((post: any) => post.views != null).length;
      if (!model?.available) {
        all.push({
          area: "model",
          problem: "The workspace model needs more real post-level examples",
          fix: "Sync both connected platforms first. Training uses actual view-count examples from the workspace; unknown/private metrics are not filled with made-up numbers. Import CSV only if you want to add older history.",
          evidence: `${totalWithViews} stored posts have real view counts; at least 10 are required for the current Random Forest models.`,
          href: "/app/datasets",
          action: "Sync data & train",
        });
      } else if ((model.top_features || []).length > 0) {
        const features = model.top_features.slice(0, 3)
          .map((feature: any) => `${String(feature.factor).replace(/_/g, " ")} (${Number(feature.importance).toFixed(3)})`)
          .join(", ");
        all.push({
          area: "model",
          problem: "Use your trained model’s feature importance to choose the next tests",
          fix: "Test one variable at a time (for example duration versus title/caption length) and compare the next posts with this baseline. Feature importance describes model association, not a proven cause of growth.",
          evidence: `Random Forest trained with ${model.n_samples} post samples. Highest feature importances: ${features}. R²: ${model.metrics?.r2 == null ? "unavailable" : Number(model.metrics.r2).toFixed(3)}.`,
          href: "/app/predictions",
          action: "Inspect model",
        });
      }

      if (coach?.available) {
        const topPost = (winners?.top_posts || [])[0];
        const topFeatures = (coach.top_features || []).slice(0, 4)
          .map((feature: any) => `${String(feature.factor).replace(/_/g, " ")} (${Number(feature.importance).toFixed(2)})`)
          .join(", ");
        all.push({
          area: "model",
          problem: "Run the next growth experiment from your own cross-platform history",
          fix: "Use the Growth Coach diagnosis to choose one change for your next Reel or Short, then compare its real metrics with this baseline. The growth index is a within-workspace ranking, not a promise of views or proof of causation.",
          evidence: `Growth Coach ${coach.version || "active"} trained on ${coach.n_samples ?? "—"} posts. Top signals: ${topFeatures || "not available"}. ${topPost ? `Strongest recorded post: ${topPost.platform === "youtube" ? "YouTube" : "Instagram"} · ${countLabel(topPost.views)} views · ${(topPost.title || topPost.caption || "Untitled post").slice(0, 90)}.` : ""}`,
          href: "/app/predictions",
          action: "Score next content",
        });
      } else {
        all.push({
          area: "model",
          problem: "Build the personalised Growth Coach from connected posts",
          fix: "Sync Instagram and YouTube so SocialBoost can train on available post metrics and compare upcoming ideas with your own stronger content. CSV import remains optional for older history.",
          evidence: `${coach?.n_samples_available ?? totalWithViews} posts with real view counts available; ${coach?.required ?? 10} are required.`,
          href: "/app/datasets",
          action: "Sync data & train",
        });
      }

      const youtube = liveAccounts.find((account: any) => account.platform === "youtube");
      if (youtube) {
        try {
          const competitorResult: any = await api.youtubeCompetitors(5);
          for (const competitor of (competitorResult.competitors || []).slice(0, 5)) {
            const recent = competitor.recent_videos?.[0];
            all.push({
              area: "competitor",
              platform: "youtube",
              video: competitor.title,
              problem: `Study a niche-matched channel: ${competitor.title}`,
              fix: "Compare its latest upload title, opening promise and publishing pattern with your best-performing Shorts. Adapt the insight—do not copy the video.",
              evidence: `Matched topics: ${(competitor.matched_topics || []).join(", ") || "topic query"} · Subscribers: ${countLabel(competitor.subscribers)} · Channel views: ${countLabel(competitor.total_views)} · Latest upload: ${recent?.title || "not returned"}`,
              href: "/app/youtube",
              action: "Review competitor",
            });
          }
        } catch {
          // The connected account can still be analysed even when YouTube's
          // public search quota or channel search is temporarily unavailable.
        }
      }

      if (!cancelled) setItems(all);
      if (!cancelled) setLoading(false);
    };
    void load().catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const areas = Array.from(new Set(items.map((item) => item.area).filter(Boolean)));
  const shown = items.filter((item) => filter === "all" || item.area === filter);

  return (
    <>
      <PageHeader
        eyebrow="Recommendations · 08"
        title={<>Your accounts. Your evidence.</>}
        description="Recommendations combine video-analysis evidence, synced account history, trained-model diagnostics and niche-matched YouTube channels. Public or unavailable metrics are never fabricated."
        actions={<Link href="/app/datasets" className="btn btn-ghost">Sync & train</Link>}
      />

      {loading ? (
        <p className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Reviewing account data and analysis reports…</p>
      ) : items.length === 0 ? (
        <Panel title="No recommendations yet">
          <Empty
            title="Nothing has been analysed yet"
            body="Sync your connected Instagram and YouTube accounts or upload a video for analysis. Recommendations will be based on the records returned."
            action={<Link href="/app/datasets" className="btn btn-signal btn-sm">Sync account data</Link>}
          />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              { title: "Evidence items", value: items.length, icon: BarChart3 },
              { title: "Connected sources", value: new Set(items.map((item) => item.platform).filter(Boolean)).size, icon: Users },
              { title: "Video reports", value: new Set(items.map((item) => item.videoId).filter(Boolean)).size, icon: Video },
              { title: "Competitor ideas", value: items.filter((item) => item.area === "competitor").length, icon: ArrowUpRight },
            ].map((stat) => (
              <div key={stat.title} className="panel p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="mono text-[8px] uppercase tracking-[0.1em] text-[var(--muted)]">{stat.title}</p>
                  <stat.icon size={14} className="text-[var(--muted)]" />
                </div>
                <p className="font-display text-[26px] font-semibold mt-2">{stat.value}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {([["all", `All ${items.length}`], ...areas.map((area) => [area, `${AREA_LABEL[area] || area} ${items.filter((item) => item.area === area).length}`])] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`mono text-[9px] uppercase tracking-[0.1em] px-3 py-2 border ${filter === key ? "bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)]" : "border-[var(--hairline)] text-[var(--muted)] hover:border-[var(--ink)]"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {shown.map((recommendation, index) => (
              <article key={`${recommendation.area}-${recommendation.platform || ""}-${recommendation.problem}-${index}`} className="panel p-5 flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {recommendation.platform && <PlatformMark platform={recommendation.platform} size={22} />}
                    <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] truncate max-w-[260px]">{recommendation.video || (recommendation.platform ? (recommendation.platform === "instagram" ? "Instagram" : "YouTube") : "Workspace")}</span>
                  </div>
                  <span className={`tag shrink-0 ${recommendation.area === "hook" ? "tag-signal" : recommendation.area === "prediction" || recommendation.area === "model" ? "tag-cobalt" : ""}`}>
                    {AREA_LABEL[recommendation.area] || recommendation.area || "General"}
                  </span>
                </div>
                <h3 className="font-display font-medium text-[16px] mt-3 leading-snug">{recommendation.problem}</h3>
                <p className="text-[12px] text-[var(--muted)] mt-2 leading-relaxed flex-1">{recommendation.fix}</p>
                {recommendation.evidence && (
                  <p className="mono text-[9px] leading-relaxed text-[var(--muted)] mt-3 border-l border-[var(--hairline-strong)] pl-2.5">
                    {recommendation.evidence}
                  </p>
                )}
                <Link href={recommendation.href || (recommendation.videoId ? `/app/analyze/${recommendation.videoId}` : "/app/analytics")} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)] mt-4 inline-flex items-center gap-1.5">
                  {recommendation.action || (recommendation.videoId ? "Open video report" : "View evidence")} <ArrowUpRight size={12} />
                </Link>
              </article>
            ))}
            {shown.length === 0 && <p className="text-[12px] text-[var(--muted)]">No items in this area.</p>}
          </div>
        </>
      )}
    </>
  );
}
