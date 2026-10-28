"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, Panel, StatusTag } from "@/components/app/ui";
import Link from "next/link";

export default function SettingsPage() {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState<any>({ theme: "light", timezone: "UTC", platforms: "instagram,youtube", target_audience: "" });
  const [models, setModels] = useState<any[]>([]);
  const [model, setModel] = useState<any>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const timezoneChoices = Array.from(new Set([
    "Asia/Kolkata", "UTC", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo",
    "Asia/Karachi", "Asia/Dhaka", "Asia/Bangkok", "Asia/Jakarta",
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Istanbul",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Toronto", "America/Vancouver", "Australia/Sydney", "Australia/Perth",
    prefs.timezone || "UTC",
  ])).sort((a, b) => a === "Asia/Kolkata" ? -1 : b === "Asia/Kolkata" ? 1 : a.localeCompare(b));

  useEffect(() => {
    api.getPrefs().then(setPrefs).catch(() => {});
    api.modelStatus().then(setModels).catch(() => {});
    api.modelDetail().then(setModel).catch(() => {});
    api.socialAccounts().then(setAccounts).catch(() => {});
  }, []);

  const save = async () => {
    setBusy(true);
    setSaved(false);
    setMsg("");
    try {
      const next: any = await api.updatePrefs(prefs);
      setPrefs(next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2200);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const train = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r: any = await api.train();
      setMsg(
        r.status === "trained"
          ? `Training complete — ${r.n_samples} samples, R² ${r.metrics?.r2?.toFixed(3) ?? "—"}.`
          : r.message || "Training did not run."
      );
      api.modelStatus().then(setModels);
      api.modelDetail().then(setModel);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Settings · 11"
        title={<>Workspace.</>}
        description="Preferences, connected identities and model controls. Changes save to your workspace."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-4 items-start">
        <div className="space-y-4">
          <Panel title="Profile">
            <dl>
              <div className="kv"><dt>Name</dt><dd>{user?.full_name || "—"}</dd></div>
              <div className="kv"><dt>Email</dt><dd>{user?.email}</dd></div>
              <div className="kv"><dt>Niche</dt><dd>{user?.niche || "Not set"}</dd></div>
            </dl>
          </Panel>

          <Panel title="Studio preferences">
            <div className="space-y-3">
              <div>
                <label className="field-label" htmlFor="tz">Timezone</label>
                <select id="tz" className="field" value={prefs.timezone || "UTC"} onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}>
                  {timezoneChoices.map((zone) => (
                    <option key={zone} value={zone}>{zone.replace(/_/g, " ")}</option>
                  ))}
                </select>
                <p className="mono text-[8.5px] text-[var(--muted)] mt-1.5">Used for calendar dates, schedules and release times. Choose one zone here, then save.</p>
              </div>
              <div>
                <label className="field-label" htmlFor="platforms">Active platforms</label>
                <div className="flex flex-wrap gap-4 pt-1">
                  {["instagram", "youtube"].map((p) => {
                    const on = prefs.platforms.split(",").map((s: string) => s.trim()).includes(p);
                    return (
                      <label key={p} className="flex items-center gap-2 text-[12px] capitalize">
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={(e) => {
                            const current = prefs.platforms.split(",").map((s: string) => s.trim()).filter(Boolean);
                            const next = e.target.checked ? [...current, p] : current.filter((s: string) => s !== p);
                            setPrefs({ ...prefs, platforms: ["instagram", "youtube"].filter((x) => next.includes(x)).join(",") });
                          }}
                        />
                        {p}
                      </label>
                    );
                  })}
                </div>
              </div>
              <div>
                <label className="field-label" htmlFor="audience">Target audience</label>
                <input id="audience" className="field" placeholder="e.g. early-stage founders" value={prefs.target_audience} onChange={(e) => setPrefs({ ...prefs, target_audience: e.target.value })} />
              </div>
              <div className="flex items-center gap-3 pt-1">
                <button className="btn btn-signal" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save preferences"}</button>
                {saved && <span className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--sage-ink)]">Saved</span>}
              </div>
              {msg && <p className="text-[12px] text-[var(--ink-2)]">{msg}</p>}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Connected accounts" aside={<Link href="/app/integrations" className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]">Manage</Link>}>
            {accounts.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)]">No accounts connected. Link Instagram and YouTube to attribute analysis and scheduling.</p>
            ) : (
              <ul className="space-y-2">
                {accounts.map((a) => (
                  <li key={a.id} className="flex items-center justify-between py-2 border-b border-[var(--hairline)] last:border-b-0">
                    <div>
                      <p className="text-[12px]">@{a.handle}</p>
                      <p className="mono text-[8.5px] uppercase text-[var(--muted)]">{a.platform} · {a.mode}</p>
                    </div>
                    <StatusTag status={a.status} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="ML models">
            <div className="border-l-2 border-[var(--cobalt)] pl-3 mb-4">
              <p className="text-[11.5px] font-semibold">Algorithms in this project</p>
              <p className="text-[10.5px] text-[var(--muted)] leading-relaxed mt-1">RandomForestRegressor predicts view counts; RandomForestClassifier classifies posts above or below the workspace median. Both use scikit-learn and only train on this workspace's posts with known view counts. Text and video opening analysis are separately labelled as deterministic heuristics or local OCR/ASR evidence, not ML predictions.</p>
            </div>
            <p className="text-[12px] leading-relaxed text-[var(--muted)]">
              {model?.available
                ? `Model ${model.version} · ${model.n_samples} samples · R² ${model.metrics?.r2 != null ? model.metrics.r2.toFixed(3) : "—"}.`
                : models.length
                ? `${models.length} version${models.length > 1 ? "s" : ""} recorded, but no active model artifact was found for this workspace.`
                : "No active model yet. Sync your connected Instagram and YouTube accounts first; at least 10 posts with real view counts are required. CSV import is optional for older history."}
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              <button className="btn btn-ghost btn-sm" onClick={train} disabled={busy}>Train models</button>
              <Link href="/app/datasets" className="btn btn-ghost btn-sm">Dataset import</Link>
            </div>
          </Panel>

          <Panel title="Data handling">
            <ul className="space-y-2.5">
              {[
                "Uploaded videos stay on the server's local disk.",
                "Historical posts are used only for this workspace.",
                "Sandbox publishing never contacts a social platform.",
              ].map((t) => (
                <li key={t} className="text-[11.5px] leading-relaxed text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-3">{t}</li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </>
  );
}
