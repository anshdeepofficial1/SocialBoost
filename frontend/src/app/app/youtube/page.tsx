"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  Eye,
  Film,
  MessageCircle,
  RefreshCw,
  Search,
  ThumbsUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, Stat } from "@/components/app/ui";

type VideoItem = {
  id: string;
  title: string;
  description: string;
  thumbnail: string | null;
  published_at: string | null;
  views: number;
  likes: number | null;
  comments: number | null;
  duration: string;
  url: string;
};

type Dashboard = {
  channel: {
    id: string;
    title: string;
    handle: string;
    description: string;
    thumbnail: string | null;
    subscribers: number | null;
    total_views: number;
    video_count: number;
    published_at: string | null;
    url: string;
  };
  videos: VideoItem[];
  source: string;
};

function compact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Hidden";
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function dateLabel(value: string | null | undefined): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" });
}

function durationLabel(value: string): string {
  const match = value.match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
  if (!match) return "";
  const hours = Number(match[1] || 0);
  const minutes = Number(match[2] || 0);
  const seconds = Number(match[3] || 0);
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export default function YouTubeStudio() {
  const [lookup, setLookup] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const runLookup = async () => {
    const value = lookup.trim();
    if (!value || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.youtubeDashboard(value, 10) as Dashboard;
      setData(result);
    } catch (reason: any) {
      setData(null);
      setError(reason?.message || "Could not load this YouTube channel.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="YouTube · Public analytics"
        title={<>Know the channel.<br />Read the signal.</>}
        description="Look up any public YouTube channel to review channel totals and its latest videos. Data comes from the YouTube Data API; private Studio analytics are not included."
        actions={
          <a href="/app/integrations" className="btn btn-ghost">
            Manage connected accounts <ArrowUpRight size={15} />
          </a>
        }
      />

      <section className="panel p-4 md:p-5 mb-6">
        <form
          className="flex flex-col sm:flex-row gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void runLookup();
          }}
        >
          <label className="sr-only" htmlFor="youtube-channel-lookup">YouTube channel handle, URL, or channel ID</label>
          <div className="flex-1 flex items-center gap-3 border border-[var(--hairline-strong)] bg-[var(--paper)] px-3.5 rounded-[var(--r-sm)] focus-within:border-[var(--ink)]">
            <Search size={17} className="text-[var(--muted)] shrink-0" />
            <input
              id="youtube-channel-lookup"
              className="w-full py-3 text-[13px] bg-transparent outline-none"
              placeholder="Try @YouTube, a channel URL, or channel ID"
              value={lookup}
              onChange={(event) => setLookup(event.target.value)}
              autoComplete="off"
            />
          </div>
          <button className="btn btn-signal" type="submit" disabled={!lookup.trim() || busy}>
            {busy ? <RefreshCw size={15} className="animate-spin" /> : <Search size={15} />}
            {busy ? "Loading channel…" : "Look up channel"}
          </button>
        </form>
        <p className="mono text-[9px] uppercase tracking-[0.08em] text-[var(--muted)] mt-3">
          Public channel data only · API key stays on the server · No publishing actions
        </p>
      </section>

      {error && (
        <div role="alert" className="mb-6 border border-[var(--red)] bg-[var(--red-soft)] px-4 py-3 text-[12px] text-[var(--red)]">
          {error}
        </div>
      )}

      {!data && !busy && !error && (
        <section className="panel p-8 md:p-12 text-center mb-6">
          <div className="w-12 h-12 mx-auto mb-4 border border-[var(--hairline-strong)] rounded-full flex items-center justify-center">
            <Film size={20} className="text-[var(--signal)]" />
          </div>
          <h2 className="text-[20px] font-semibold tracking-[-0.03em]">Start with a channel</h2>
          <p className="mt-2 mx-auto max-w-xl text-[12.5px] leading-relaxed text-[var(--muted)]">
            Enter a channel handle such as @YouTube, a youtube.com/@handle URL, or a channel ID. We’ll show its public totals and the latest ten videos.
          </p>
        </section>
      )}

      {data && (
        <>
          <section className="panel p-5 md:p-6 mb-4">
            <div className="flex flex-col md:flex-row md:items-start gap-4">
              {data.channel.thumbnail ? (
                <img
                  src={data.channel.thumbnail}
                  alt=""
                  className="w-[76px] h-[76px] rounded-full object-cover border border-[var(--hairline)] bg-[var(--paper-2)]"
                  referrerPolicy="strict-origin-when-cross-origin"
                />
              ) : (
                <div className="w-[76px] h-[76px] rounded-full border border-[var(--hairline)] bg-[var(--paper-2)] flex items-center justify-center">
                  <Film size={26} className="text-[var(--muted)]" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="label">Channel snapshot</p>
                  <span className="tag tag-sage">Public data</span>
                </div>
                <h2 className="text-[25px] md:text-[32px] font-semibold leading-tight tracking-[-0.04em] mt-1">
                  {data.channel.title}
                </h2>
                <p className="text-[12px] text-[var(--muted)] mt-1">
                  {data.channel.handle || data.channel.id} · Joined {dateLabel(data.channel.published_at)}
                </p>
                {data.channel.description && (
                  <p className="text-[12.5px] leading-relaxed text-[var(--ink-2)] mt-3 line-clamp-3">
                    {data.channel.description}
                  </p>
                )}
              </div>
              <a
                href={data.channel.url}
                target="_blank"
                rel="noreferrer"
                className="btn btn-ghost btn-sm shrink-0"
              >
                Open channel <ArrowUpRight size={14} />
              </a>
            </div>
          </section>

          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
            <Stat
              label="Subscribers"
              value={compact(data.channel.subscribers)}
              hint={data.channel.subscribers === null ? "Hidden by channel owner" : "Public subscriber count"}
            />
            <Stat label="Total channel views" value={compact(data.channel.total_views)} hint="Lifetime public views" />
            <Stat label="Videos published" value={compact(data.channel.video_count)} hint="Public channel total" />
            <Stat label="Recent videos loaded" value={data.videos.length} hint="Latest uploads returned by YouTube" />
          </div>

          <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
            <div>
              <p className="eyebrow">Latest uploads</p>
              <h2 className="text-[24px] font-semibold tracking-[-0.04em] mt-2">Recent videos</h2>
            </div>
            <p className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)]">
              Source · {data.source}
            </p>
          </div>

          {data.videos.length === 0 ? (
            <section className="panel p-6 text-[12.5px] text-[var(--muted)]">
              No public videos were returned for this channel.
            </section>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.videos.map((video) => (
                <a
                  key={video.id}
                  href={video.url}
                  target="_blank"
                  rel="noreferrer"
                  className="panel overflow-hidden group hover:border-[var(--hairline-strong)] transition-colors"
                >
                  <div className="relative aspect-video bg-[var(--paper-2)] overflow-hidden">
                    {video.thumbnail && (
                      <img
                        src={video.thumbnail}
                        alt=""
                        loading="lazy"
                        className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                        referrerPolicy="strict-origin-when-cross-origin"
                      />
                    )}
                    {video.duration && (
                      <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-white mono text-[10px]">
                        {durationLabel(video.duration)}
                      </span>
                    )}
                  </div>
                  <div className="p-4">
                    <h3 className="text-[13px] font-medium leading-snug line-clamp-2 min-h-[2.7em]">{video.title}</h3>
                    <p className="mono text-[9px] uppercase tracking-[0.06em] text-[var(--muted)] mt-2">
                      <CalendarDays size={11} className="inline mr-1" />
                      {dateLabel(video.published_at)}
                    </p>
                    <div className="grid grid-cols-3 gap-2 border-t border-[var(--hairline)] mt-3 pt-3">
                      <span className="flex items-center gap-1.5 mono text-[10px] text-[var(--ink-2)]"><Eye size={12} />{compact(video.views)}</span>
                      <span className="flex items-center gap-1.5 mono text-[10px] text-[var(--ink-2)]"><ThumbsUp size={12} />{compact(video.likes)}</span>
                      <span className="flex items-center gap-1.5 mono text-[10px] text-[var(--ink-2)]"><MessageCircle size={12} />{compact(video.comments)}</span>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
          <p className="mono text-[9px] leading-relaxed text-[var(--muted)] mt-5">
            Counts reflect public YouTube Data API responses. Subscriber counts can be rounded or hidden; likes and comments may be unavailable for some videos. This does not access YouTube Studio private analytics.
          </p>
        </>
      )}
    </>
  );
}
