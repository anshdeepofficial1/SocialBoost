"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Empty } from "@/components/app/ui";

const AREA_LABEL: Record<string, string> = {
  technical: "Technical",
  hook: "Hook",
  prediction: "Prediction",
};

export default function Recommendations() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    (async () => {
      try {
        const vids = await api.listVideos();
        const all: any[] = [];
        for (const v of vids) {
          try {
            const a = await api.videoAnalysis(v.id);
            (a.result?.recommendations || []).forEach((r: any) =>
              all.push({ video: v.original_name, videoId: v.id, ...r })
            );
          } catch {}
        }
        setItems(all);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const areas = Array.from(new Set(items.map((i) => i.area).filter(Boolean)));
  const shown = items.filter((i) => filter === "all" || i.area === filter);

  return (
    <>
      <PageHeader
        eyebrow="Recommendations · 08"
        title={<>Prioritized improvements.</>}
        description="Each item comes from an actual analysis result and carries the evidence that produced it. Nothing here is a generic tip."
        actions={<Link href="/app/analyze" className="btn btn-signal">Analyze another</Link>}
      />

      {loading ? (
        <p className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Loading recommendations…</p>
      ) : items.length === 0 ? (
        <Panel title="No recommendations">
          <Empty
            title="Nothing to improve yet"
            body="Recommendations are generated from analysis results. Upload a video to start."
            action={<Link href="/app/analyze" className="btn btn-signal btn-sm">Analyze a video</Link>}
          />
        </Panel>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {([["all", `All ${items.length}`], ...areas.map((a) => [a, `${AREA_LABEL[a] || a} ${items.filter((i) => i.area === a).length}`])] as const).map(([k, l]) => (
              <button
                key={k}
                onClick={() => setFilter(k)}
                className={`mono text-[9px] uppercase tracking-[0.1em] px-3 py-2 border ${filter === k ? "bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)]" : "border-[var(--hairline)] text-[var(--muted)] hover:border-[var(--ink)]"}`}
              >
                {l}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {shown.map((r, i) => (
              <article key={i} className="panel p-5 flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <span className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] truncate max-w-[70%]">{r.video}</span>
                  <span className={`tag shrink-0 ${r.area === "hook" ? "tag-signal" : r.area === "prediction" ? "tag-cobalt" : ""}`}>
                    {AREA_LABEL[r.area] || r.area || "general"}
                  </span>
                </div>
                <h3 className="font-display font-medium text-[16px] mt-3 leading-snug">{r.problem}</h3>
                <p className="text-[12px] text-[var(--muted)] mt-2 leading-relaxed flex-1">{r.fix}</p>
                {r.evidence && (
                  <p className="mono text-[9px] leading-relaxed text-[var(--muted)] mt-3 border-l border-[var(--hairline-strong)] pl-2.5">
                    {r.evidence}
                  </p>
                )}
                <Link href={`/app/analyze/${r.videoId}`} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)] mt-4">
                  Open report →
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
