"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Panel, Meter, Empty } from "@/components/app/ui";

export default function HookLab() {
  const [text, setText] = useState("");
  const [duration, setDuration] = useState(3);
  const [res, setRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  const loadDrafts = () => api.drafts().then(setDrafts).catch(() => {});
  useEffect(() => { loadDrafts(); }, []);

  const run = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setErr("");
    setSavedMsg("");
    try { setRes(await api.hook(text, duration)); } catch (e: any) { setErr(e.message); } finally { setLoading(false); }
  };

  const saveDraft = async () => {
    if (!text.trim()) return;
    setSaving(true);
    setSavedMsg("");
    setErr("");
    try {
      await api.createDraft({ platform: "instagram", caption: text.trim() });
      setSavedMsg("Saved as a draft. Open the calendar to schedule it.");
      loadDrafts();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const removeDraft = async (id: string) => {
    try {
      await api.deleteDraft(id);
      loadDrafts();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const copy = async (s: string, i: number) => {
    try { await navigator.clipboard.writeText(s); setCopied(i); setTimeout(() => setCopied(null), 1400); } catch {}
  };

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const readingTime = words ? (words / 2.8).toFixed(1) : "0.0";

  return (
    <>
      <PageHeader
        eyebrow="Hook Lab · 02"
        title={<>The first three seconds decide.</>}
        description="Write the opening line, set the window, and get a transparent heuristic score with editable alternatives. This is a writing aid, not a retention prediction."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel title="Opening line" aside={<span className="mono text-[9px] text-[var(--muted)]">{words} words · ~{readingTime}s spoken</span>}>
            <textarea
              className="field min-h-[150px] resize-y leading-relaxed"
              placeholder="Nobody tells you this about hooks…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={600}
            />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="field-label" htmlFor="duration">Hook window (seconds)</label>
                <input id="duration" type="number" min={0} max={60} step={0.5} className="field" value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
              </div>
              <div>
                <label className="field-label">Trigger words</label>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {["stop", "why", "secret", "mistake", "how"].map((w) => (
                    <span key={w} className={`tag ${text.toLowerCase().includes(w) ? "tag-signal" : ""}`}>{w}</span>
                  ))}
                </div>
              </div>
            </div>
            {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}
            {savedMsg && <p className="mt-3 text-[12px] text-[var(--sage-ink)]">{savedMsg}</p>}
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button className="btn btn-signal" onClick={run} disabled={loading || !text.trim()}>
                {loading ? "Scoring…" : "Score this hook"}
              </button>
              <button className="btn btn-ghost" onClick={saveDraft} disabled={saving || !text.trim()}>
                {saving ? "Saving…" : "Save as draft"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setText(""); setRes(null); setSavedMsg(""); }}>Clear</button>
            </div>
          </Panel>

          <Panel title="Scoring model" >
            <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">
              The score starts at 50 and adjusts for length, question form, trigger vocabulary, word count and window duration. Every adjustment is listed in the result — there is no hidden model.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[["Substantive text", "+10"], ["Question form", "+5"], ["Trigger word", "+8"], ["Window > 4s", "−10"], ["Fewer than 4 words", "−10"]].map(([k, v]) => (
                <div key={k} className="flex justify-between text-[11px] py-1.5 border-b border-[var(--hairline)]">
                  <span className="text-[var(--muted)]">{k}</span>
                  <span className="mono">{v}</span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title={`Saved drafts · ${drafts.length}`} flush>
            {drafts.length === 0 ? (
              <div className="p-5"><p className="text-[12px] text-[var(--muted)]">No drafts yet. Save an opening line to reuse it later.</p></div>
            ) : (
              <ul>
                {drafts.slice(0, 8).map((d) => (
                  <li key={d.id} className="px-5 py-3 border-b border-[var(--hairline)] last:border-b-0">
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-[12px] leading-relaxed truncate">{d.caption || d.title || "Untitled draft"}</p>
                        <p className="mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--muted)] mt-1">
                          {d.platform} · {new Date(d.updated_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button onClick={() => setText(d.caption)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)]">load</button>
                        <button onClick={() => removeDraft(d.id)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] hover:text-[var(--red)]">delete</button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          {!res ? (
            <Panel title="Result">
              <Empty title="No score yet" body="Write an opening line and score it to see the breakdown and alternative openings." />
            </Panel>
          ) : (
            <>
              <Panel title="Hook score" aside={<span className="tag">heuristic</span>}>
                <div className="flex items-end gap-3">
                  <span className="font-display font-semibold text-[64px] leading-none tracking-[-0.05em]">{res.hook_score}</span>
                  <span className="mono text-[10px] text-[var(--muted)] pb-2">/100</span>
                </div>
                <div className="mt-4"><Meter value={res.hook_score} /></div>
                <p className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] mt-3">
                  Window {res.opening_duration}s · {res.band || (res.hook_score >= 70 ? "strong" : res.hook_score >= 50 ? "workable" : "weak")}
                </p>
                <div className="mt-5">
                  <p className="label mb-2">Adjustments</p>
                  <ul className="space-y-1.5">
                    {(res.adjustments || []).map((a: any, i: number) => (
                      <li key={i} className="flex items-center justify-between text-[12px] py-1.5 border-b border-[var(--hairline)] last:border-b-0">
                        <span className="text-[var(--ink-2)]">{a.rule}</span>
                        <span className={`mono text-[10px] ${a.delta > 0 ? "text-[var(--sage-ink)]" : a.delta < 0 ? "text-[var(--signal)]" : "text-[var(--muted)]"}`}>
                          {a.delta > 0 ? `+${a.delta}` : a.delta}
                        </span>
                      </li>
                    ))}
                    {(res.adjustments || []).length === 0 && <li className="text-[12px] text-[var(--muted)]">No scoring adjustments applied.</li>}
                  </ul>
                </div>
                {res.reasons?.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {res.reasons.map((r: string, i: number) => (
                      <li key={i} className="flex gap-2.5 text-[11.5px] leading-relaxed text-[var(--muted)]">
                        <span className="mono text-[9px] text-[var(--signal)] pt-0.5">·</span>{r}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel title={`Alternatives · ${res.alternatives?.length ?? 0}`} flush>
                <ul>
                  {res.alternatives?.map((a: string, i: number) => (
                    <li key={i} className="px-5 py-4 border-b border-[var(--hairline)] last:border-b-0">
                      <div className="flex items-start gap-3">
                        <span className="mono text-[9px] text-[var(--muted)] pt-0.5">{String(i + 1).padStart(2, "0")}</span>
                        <p className="flex-1 text-[12.5px] leading-relaxed">{a}</p>
                        <button onClick={() => copy(a, i)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--signal)] shrink-0">
                          {copied === i ? "copied" : "copy"}
                        </button>
                      </div>
                      <button onClick={() => setText(a)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] mt-2 ml-7 hover:text-[var(--ink)]">
                        use as draft →
                      </button>
                    </li>
                  ))}
                </ul>
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}
