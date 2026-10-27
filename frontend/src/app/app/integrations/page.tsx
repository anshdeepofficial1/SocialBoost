"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Panel, PlatformMark, StatusTag, Empty } from "@/components/app/ui";

type Provider = {
  platform: string;
  label: string;
  product: string;
  configured: boolean;
  mode: string;
  required_env: string[];
  scopes: string[];
  note: string;
};

export default function Integrations() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [handle, setHandle] = useState<Record<string, string>>({ instagram: "", youtube: "" });
  const [name, setName] = useState<Record<string, string>>({ instagram: "", youtube: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = () => {
    api.socialAccounts().then(setAccounts).catch(() => {});
    api.socialProviders().then(setProviders).catch(() => {});
  };
  useEffect(load, []);

  const connect = async (platform: string) => {
    setBusy(platform);
    setMsg(null);
    try {
      await api.connectSocial({
        platform,
        handle: handle[platform],
        display_name: name[platform] || handle[platform],
        mode: "sandbox",
      });
      setMsg({ kind: "ok", text: `${platform === "instagram" ? "Instagram" : "YouTube"} account linked.` });
      setHandle({ ...handle, [platform]: "" });
      setName({ ...name, [platform]: "" });
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally {
      setBusy(null);
    }
  };

  const sync = async (id: string) => {
    setBusy(id);
    setMsg(null);
    try {
      await api.syncSocial(id);
      setMsg({ kind: "ok", text: "Account statistics recalculated from imported history." });
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async (id: string) => {
    if (!confirm("Disconnect this account? Imported historical posts are kept.")) return;
    setBusy(id);
    try {
      await api.disconnectSocial(id);
      setMsg({ kind: "ok", text: "Account disconnected." });
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally {
      setBusy(null);
    }
  };

  const oauthStart = async (platform: string) => {
    setBusy(`oauth-${platform}`);
    setMsg(null);
    try {
      const r: any = await api.oauthStart(platform);
      window.location.href = r.authorize_url;
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Accounts · 10"
        title={
          <>
            Link your channels.
            <br />
            See real evidence.
          </>
        }
        description="Connect Instagram and YouTube to tie analysis and scheduling to a specific identity. On this build connections are sandbox records; metrics are computed only from history you import."
      />

      {msg && (
        <div className={`mb-5 border px-4 py-3 text-[12px] ${msg.kind === "ok" ? "border-[var(--sage-deep)] bg-[var(--sage)] text-[#3E4C34]" : "border-[var(--red)] text-[var(--red)]"}`}>
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {providers.map((p) => {
          const acc = accounts.find((a) => a.platform === p.platform);
          return (
            <section key={p.platform} className="panel">
              <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--hairline)]">
                <div className="flex items-center gap-3">
                  <PlatformMark platform={p.platform} size={34} />
                  <div>
                    <p className="text-[14px] font-medium">{p.label}</p>
                    <p className="mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--muted)]">{p.product} · {p.mode}</p>
                  </div>
                </div>
                <StatusTag status={acc ? acc.status : "not connected"} />
              </div>

              <div className="p-5">
                {acc ? (
                  <>
                    <div className="flex items-baseline justify-between">
                      <div>
                        <p className="font-display font-semibold text-[22px] tracking-[-0.02em]">@{acc.handle}</p>
                        <p className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] mt-1">
                          linked {new Date(acc.connected_at).toLocaleDateString()} · {acc.mode} mode
                        </p>
                      </div>
                    </div>

                    <dl className="mt-5">
                      <div className="kv"><dt>Followers</dt><dd>{acc.followers.toLocaleString()}</dd></div>
                      <div className="kv"><dt>Imported posts</dt><dd>{acc.post_count}</dd></div>
                      <div className="kv"><dt>Average views</dt><dd>{acc.avg_views.toLocaleString()}</dd></div>
                      <div className="kv"><dt>Engagement</dt><dd>{(acc.engagement_rate * 100).toFixed(2)}%</dd></div>
                      <div className="kv"><dt>Last synced</dt><dd>{acc.last_synced_at ? new Date(acc.last_synced_at).toLocaleString() : "—"}</dd></div>
                    </dl>

                    <p className="mt-4 mono text-[9px] leading-relaxed text-[var(--muted)]">{acc.evidence}.</p>

                    <div className="mt-5 flex flex-wrap gap-2">
                      <button className="btn btn-ghost btn-sm" onClick={() => sync(acc.id)} disabled={busy === acc.id}>
                        {busy === acc.id ? "Syncing…" : "Recalculate stats"}
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => disconnect(acc.id)} disabled={busy === acc.id}>
                        Disconnect
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-[12.5px] text-[var(--ink-2)] leading-relaxed">{p.note}</p>

                    <div className="mt-5 space-y-3">
                      <div>
                        <label className="field-label" htmlFor={`handle-${p.platform}`}>Account handle</label>
                        <div className="flex">
                          <span className="mono text-[12px] px-3 flex items-center border border-r-0 border-[var(--hairline)] bg-[var(--paper-2)] text-[var(--muted)]">@</span>
                          <input
                            id={`handle-${p.platform}`}
                            className="field"
                            placeholder={p.platform === "instagram" ? "your.studio" : "yourchannel"}
                            value={handle[p.platform]}
                            onChange={(e) => setHandle({ ...handle, [p.platform]: e.target.value })}
                          />
                        </div>
                      </div>
                      <div>
                        <label className="field-label" htmlFor={`name-${p.platform}`}>Display name (optional)</label>
                        <input
                          id={`name-${p.platform}`}
                          className="field"
                          placeholder="Studio name"
                          value={name[p.platform]}
                          onChange={(e) => setName({ ...name, [p.platform]: e.target.value })}
                        />
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          className="btn btn-signal btn-sm"
                          onClick={() => connect(p.platform)}
                          disabled={!handle[p.platform].trim() || busy === p.platform}
                        >
                          {busy === p.platform ? "Connecting…" : "Connect in sandbox"}
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => oauthStart(p.platform)}
                          disabled={busy === `oauth-${p.platform}`}
                        >
                          {p.configured ? "Connect with OAuth" : "OAuth unavailable"}
                        </button>
                      </div>
                      {!p.configured && (
                        <p className="mono text-[9px] leading-relaxed text-[var(--muted)]">
                          Set {p.required_env.join(" and ")} on the backend to enable real OAuth. Publishing remains simulated until a provider confirms it.
                        </p>
                      )}
                    </div>
                  </>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel title="What connecting changes">
          <ul className="space-y-3">
            {[
              ["Identity", "Analysis and scheduled posts are attributed to the linked handle."],
              ["Evidence", "Platform comparison uses your imported history for that channel."],
              ["Publishing", "Scheduled jobs target the linked platform. Sandbox jobs stay labelled."],
            ].map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="mono text-[9px] text-[var(--signal)] pt-0.5">+</span>
                <div>
                  <p className="text-[12px] font-medium">{t}</p>
                  <p className="text-[11.5px] text-[var(--muted)] leading-relaxed mt-0.5">{d}</p>
                </div>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Permissions requested">
          <ul className="space-y-2">
            {providers.flatMap((p) => p.scopes.map((s) => ({ platform: p.platform, scope: s }))).map((s) => (
              <li key={s.platform + s.scope} className="flex items-start gap-2">
                <PlatformMark platform={s.platform} size={18} />
                <code className="mono text-[10px] text-[var(--ink-2)] break-all">{s.scope}</code>
              </li>
            ))}
          </ul>
          <p className="mt-4 mono text-[9px] leading-relaxed text-[var(--muted)]">
            This build requests read-only scopes. No token is stored in this database; a production deployment should use a secrets vault.
          </p>
        </Panel>

        <Panel title="Honest limitations">
          <div className="space-y-3">
            {[
              "No OAuth credentials are configured in this environment, so connections are sandbox records.",
              "Follower counts come from imported history, not a live API call.",
              "Scheduled publishing is simulated and clearly labelled sandbox.",
            ].map((t) => (
              <p key={t} className="text-[11.5px] leading-relaxed text-[var(--muted)] border-l border-[var(--hairline-strong)] pl-3">{t}</p>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
