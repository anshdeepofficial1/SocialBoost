"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Panel, PlatformMark, StatusTag, Empty } from "@/components/app/ui";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function startOfMonthGrid(year: number, month: number) {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday-first
  const start = new Date(year, month, 1 - offset);
  return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
}

export default function CalendarPage() {
  const today = new Date();
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [view, setView] = useState<"month" | "agenda">("month");
  const [events, setEvents] = useState<any[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({
    video_id: "",
    platform: "instagram",
    scheduled_at: "",
    caption: "",
    title: "",
    is_sandbox: true,
  });

  const load = () => api.calendarEvents().then(setEvents).catch(() => {});
  useEffect(() => {
    load();
    api.listVideos().then(setVideos).catch(() => {});
  }, []);

  const days = useMemo(() => startOfMonthGrid(cursor.getFullYear(), cursor.getMonth()), [cursor]);

  const byDay = useMemo(() => {
    const m: Record<string, any[]> = {};
    events.forEach((e) => {
      const d = new Date(e.scheduled_at);
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      (m[key] ||= []).push(e);
    });
    return m;
  }, [events]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.scheduled_at) { setErr("Pick a date and time."); return; }
    setSaving(true);
    setErr("");
    try {
      await api.schedule({ ...form, scheduled_at: new Date(form.scheduled_at).toISOString() });
      setForm({ ...form, scheduled_at: "", caption: "", title: "" });
      setOpen(false);
      load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const cancel = async (id: string) => {
    setErr("");
    try {
      await api.cancelSchedule(id);
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Remove this entry from the calendar?")) return;
    setErr("");
    try {
      await api.deleteSchedule(id);
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const upcoming = [...events].sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());
  const activeCount = events.filter((e) => e.status === "scheduled").length;

  return (
    <>
      <PageHeader
        eyebrow="Calendar · 05"
        title={<>A plan, not a pile.</>}
        description="Drafts and scheduled jobs live on one timeline. Sandbox jobs are simulated and labelled — nothing is reported as published without provider confirmation."
        actions={<button className="btn btn-signal" onClick={() => setOpen((v) => !v)}>{open ? "Close form" : "Schedule a post"}</button>}
      />

      {open && (
        <Panel title="Schedule a release" className="mb-4">
          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="field-label" htmlFor="video">Video</label>
              <select id="video" className="field" value={form.video_id} onChange={(e) => setForm({ ...form, video_id: e.target.value })}>
                <option value="">No video attached</option>
                {videos.map((v) => <option key={v.id} value={v.id}>{v.original_name}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="platform">Platform</label>
              <select id="platform" className="field" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
                <option value="instagram">Instagram Reels</option>
                <option value="youtube">YouTube Shorts</option>
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="when">Date & time</label>
              <input id="when" type="datetime-local" className="field" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} required />
            </div>
            <div className="md:col-span-1">
              <label className="field-label" htmlFor="title">Title</label>
              <input id="title" className="field" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="md:col-span-2">
              <label className="field-label" htmlFor="caption">Caption</label>
              <input id="caption" className="field" value={form.caption} onChange={(e) => setForm({ ...form, caption: e.target.value })} />
            </div>
            <div className="md:col-span-3 flex flex-wrap items-center justify-between gap-3 pt-1">
              <label className="flex items-center gap-2 text-[12px]">
                <input type="checkbox" checked={form.is_sandbox} onChange={(e) => setForm({ ...form, is_sandbox: e.target.checked })} />
                Sandbox — simulate publishing
              </label>
              <div className="flex gap-2">
                <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
                <button className="btn btn-signal" disabled={saving}>{saving ? "Scheduling…" : "Add to calendar"}</button>
              </div>
            </div>
          </form>
          {err && <p className="mt-3 text-[12px] text-[var(--red)]">{err}</p>}
        </Panel>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost btn-sm" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Previous month">←</button>
          <p className="font-display font-semibold text-[16px] min-w-[160px] text-center">{MONTHS[cursor.getMonth()]} {cursor.getFullYear()}</p>
          <button className="btn btn-ghost btn-sm" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Next month">→</button>
          <button className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)] ml-1" onClick={() => setCursor(new Date(today.getFullYear(), today.getMonth(), 1))}>Today</button>
        </div>
        <div className="flex items-center gap-1 border border-[var(--hairline)]">
          {(["month", "agenda"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`mono text-[9px] uppercase tracking-[0.12em] px-3 py-2 ${view === v ? "bg-[var(--ink)] text-[var(--paper)]" : "text-[var(--muted)] hover:text-[var(--ink)]"}`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {err && <p className="mb-3 text-[12px] text-[var(--red)]">{err}</p>}

      {view === "month" ? (
        <div className="panel overflow-hidden">
          <div className="grid grid-cols-7 border-b border-[var(--hairline)] bg-[var(--paper-2)]">
            {DOW.map((d) => <div key={d} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] px-2 py-2">{d}</div>)}
          </div>
          <div className="grid grid-cols-7">
            {days.map((d, i) => {
              const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
              const list = byDay[key] || [];
              const inMonth = d.getMonth() === cursor.getMonth();
              const isToday = d.toDateString() === today.toDateString();
              return (
                <div key={i} className={`min-h-[96px] border-b border-r border-[var(--hairline)] p-1.5 ${inMonth ? "bg-[var(--paper)]" : "bg-[var(--paper-2)]"}`}>
                  <div className="flex items-center justify-between">
                    <span className={`mono text-[9px] ${isToday ? "bg-[var(--ink)] text-[var(--paper)] px-1" : inMonth ? "text-[var(--ink-2)]" : "text-[var(--muted)]"}`}>
                      {d.getDate()}
                    </span>
                    {list.length > 2 && <span className="mono text-[8px] text-[var(--muted)]">+{list.length - 2}</span>}
                  </div>
                  <div className="mt-1 space-y-1">
                    {list.slice(0, 2).map((e) => (
                      <div key={e.id} className="flex items-center gap-1">
                        <span className="w-1 h-1 shrink-0" style={{ background: e.platform === "instagram" ? "var(--signal)" : "var(--cobalt)" }} />
                        <span className="text-[8.5px] truncate text-[var(--ink-2)]">{e.title || e.caption || e.platform}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-4 px-4 py-2.5">
            <span className="flex items-center gap-1.5 mono text-[8.5px] uppercase text-[var(--muted)]"><span className="w-1.5 h-1.5" style={{ background: "var(--signal)" }} />Instagram</span>
            <span className="flex items-center gap-1.5 mono text-[8.5px] uppercase text-[var(--muted)]"><span className="w-1.5 h-1.5" style={{ background: "var(--cobalt)" }} />YouTube</span>
            <span className="ml-auto mono text-[8.5px] uppercase text-[var(--muted)]">{activeCount} active · {events.length} total</span>
          </div>
        </div>
      ) : (
        <Panel title={`Agenda · ${events.length}`} flush>
          {upcoming.length === 0 ? (
            <div className="p-5"><Empty title="Nothing scheduled" body="Add a release to see it here." action={<button className="btn btn-signal btn-sm" onClick={() => setOpen(true)}>Schedule a post</button>} /></div>
          ) : (
            <ul>
              {upcoming.map((e) => (
                <li key={e.id} className="flex items-center gap-4 px-5 py-3.5 border-b border-[var(--hairline)] last:border-b-0">
                  <div className="w-16 shrink-0">
                    <p className="mono text-[10px]">{new Date(e.scheduled_at).toLocaleDateString(undefined, { month: "short", day: "2-digit" })}</p>
                    <p className="mono text-[8.5px] text-[var(--muted)]">{new Date(e.scheduled_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                  <PlatformMark platform={e.platform} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] truncate">{e.title || e.caption || "Untitled release"}</p>
                    <p className="mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--muted)] mt-0.5">{e.is_sandbox ? "sandbox" : "live"}</p>
                  </div>
                  <StatusTag status={e.status} />
                  {e.status === "scheduled" ? (
                    <button onClick={() => cancel(e.id)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] hover:text-[var(--red)]">Cancel</button>
                  ) : (
                    <button onClick={() => remove(e.id)} className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)] hover:text-[var(--red)]">Remove</button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </>
  );
}
