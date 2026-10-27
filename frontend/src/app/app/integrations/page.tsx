"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, Panel, PlatformMark, StatusTag } from "@/components/app/ui";

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

const isPlaceholder = (account: any) =>
  typeof account?.handle === "string" && /^(instagram|youtube)-user-/i.test(account.handle);

export default function Integrations() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [handle, setHandle] = useState<Record<string, string>>({ instagram: "", youtube: "" });
  const [name, setName] = useState<Record<string, string>>({ instagram: "", youtube: "" });
  const [manualOpen, setManualOpen] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const load = () => {
    api.socialAccounts().then(setAccounts).catch(() => {});
    api.socialProviders().then(setProviders).catch(() => {});
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("oauth_connected");
    const error = params.get("oauth_error");
    if (connected) {
      setMsg({
        kind: "ok",
        text: `${connected === "instagram" ? "Instagram" : "YouTube"} is linked. You can now sync the data the platform makes available.`,
      });
    } else if (error) {
      const detail = params.get("detail");
      const message = detail === "instagram_business_account_not_found"
        ? "Meta accepted the login, but did not return an Instagram professional account linked to the Pages you selected. Check that the correct Instagram account is set to Business or Creator and linked to the selected Page."
        : detail === "graph_lookup_failed"
          ? "Meta accepted the login, but SocialBoost could not read the Instagram profile. The connection needs another check; no Facebook Page metrics were substituted for Instagram data."
          : `The connection could not be completed${detail ? ` (${detail.replace(/_/g, " ")})` : ""}. Please try again.`;
      setMsg({ kind: "err", text: message });
    }
    if (connected || error) window.history.replaceState({}, "", window.location.pathname);
    load();
  }, []);

  const connect = async (platform: string) => {
    setBusy(platform);
    setMsg(null);
    try {
      const cleanHandle = handle[platform].trim().replace(/^@+/, "");
      await api.connectSocial({
        platform,
        handle: cleanHandle,
        display_name: name[platform].trim() || cleanHandle,
        mode: "sandbox",
      });
      setMsg({ kind: "ok", text: `${platform === "instagram" ? "Instagram" : "YouTube"} profile added. Import past posts to build its performance history.` });
      setHandle({ ...handle, [platform]: "" });
      setName({ ...name, [platform]: "" });
      setManualOpen({ ...manualOpen, [platform]: false });
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message || "Could not add this profile." });
    } finally {
      setBusy(null);
    }
  };

  const sync = async (id: string) => {
    setBusy(id);
    setMsg(null);
    try {
      const result: any = await api.syncSocial(id);
      if (result?.sync_source === "live Instagram API data") {
        const metrics = result.live_metrics || {};
        const viewNote = metrics.view_metrics_available
          ? ` View counts were available for ${metrics.view_metrics_available} recent posts.`
          : " Some view counts are not provided for the recent posts, so those values will remain blank.";
        setMsg({
          kind: "ok",
          text: `Instagram data synced: ${Number(result.followers || 0).toLocaleString()} followers and ${Number(result.post_count || 0).toLocaleString()} media items.${viewNote}`,
        });
      } else if (result?.sync_note) {
        setMsg({ kind: "err", text: result.sync_note });
      } else {
        setMsg({ kind: "err", text: "SocialBoost could not retrieve live stats this time. Reconnect the account and make sure the right Instagram account is linked to your Page." });
      }
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message || "Sync failed. Please try again." });
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async (id: string) => {
    if (!confirm("Disconnect this profile from SocialBoost? Imported post history will be kept.")) return;
    setBusy(id);
    try {
      await api.disconnectSocial(id);
      setMsg({ kind: "ok", text: "Profile disconnected. Imported post history is still available." });
      load();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message || "Could not disconnect this profile." });
    } finally {
      setBusy(null);
    }
  };

  const oauthStart = async (platform: string) => {
    setBusy(`oauth-${platform}`);
    setMsg(null);
    try {
      const result: any = await api.oauthStart(platform);
      window.location.href = result.authorize_url;
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message || "Could not open the provider authorization page." });
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Workspace · Accounts"
        title={<>Your channels.<br />One clear view.</>}
        description="Connect the accounts you create with, then use their available stats alongside your video analyses and content history."
        actions={
          <button className="btn btn-ghost" onClick={load} type="button">
            Refresh accounts
          </button>
        }
      />

      {msg && (
        <div
          role={msg.kind === "err" ? "alert" : "status"}
          aria-live="polite"
          className={`mb-5 flex items-start gap-3 rounded-[var(--r-sm)] border px-4 py-3 text-[13px] ${msg.kind === "ok" ? "border-[var(--sage-deep)] bg-[var(--sage)] text-[var(--sage-ink)]" : "border-[var(--red)] bg-[var(--red-soft)] text-[var(--red)]"}`}
        >
          <span className="font-bold" aria-hidden="true">{msg.kind === "ok" ? "✓" : "!"}</span>
          <p>{msg.text}</p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-6">
        {providers.map((provider) => {
          const rawAccount = accounts.find((a) => a.platform === provider.platform);
          const account = isPlaceholder(rawAccount) ? null : rawAccount;
          const oldPlaceholderExists = !!rawAccount && !account;
          const manual = !!manualOpen[provider.platform];
          const instagram = provider.platform === "instagram";

          return (
            <section key={provider.platform} className="panel panel-hover overflow-hidden">
              <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--hairline)] bg-[linear-gradient(120deg,var(--paper),var(--paper-2))]">
                <div className="flex items-center gap-3 min-w-0">
                  <PlatformMark platform={provider.platform} size={40} />
                  <div className="min-w-0">
                    <h2 className="font-display font-bold text-[17px] tracking-[-0.025em]">{provider.label}</h2>
                    <p className="text-[11px] text-[var(--muted)] mt-0.5">{instagram ? "Instagram professional account" : "YouTube channel"}</p>
                  </div>
                </div>
                <StatusTag status={account ? account.status : oldPlaceholderExists ? "needs_reauth" : "not connected"} />
              </div>

              <div className="p-5 md:p-6">
                {account ? (
                  <>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-display font-semibold text-[24px] tracking-[-0.04em] truncate">@{account.handle}</p>
                        <p className="text-[12px] text-[var(--muted)] mt-1">{account.display_name || provider.label}</p>
                        <p className="text-[11px] text-[var(--muted)] mt-2">
                          {account.mode === "oauth" ? "Linked directly to your platform account" : "Profile added manually"}
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-[10px] font-semibold bg-[var(--paper-2)] text-[var(--ink-2)]">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: account.status === "connected" ? "var(--sage-deep)" : "var(--signal)" }} />
                        {account.status === "connected" ? "Active" : account.status.replace(/_/g, " ")}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-5">
                      <div className="rounded-[var(--r-sm)] bg-[var(--paper-2)] p-3.5">
                        <p className="text-[10px] uppercase tracking-[.1em] text-[var(--muted)]">Followers</p>
                        <p className="font-display font-bold text-[22px] tracking-[-.04em] mt-1">{Number(account.followers || 0).toLocaleString()}</p>
                      </div>
                      <div className="rounded-[var(--r-sm)] bg-[var(--paper-2)] p-3.5">
                        <p className="text-[10px] uppercase tracking-[.1em] text-[var(--muted)]">{account.mode === "oauth" ? "Total media" : "Imported posts"}</p>
                        <p className="font-display font-bold text-[22px] tracking-[-.04em] mt-1">{Number(account.post_count || 0).toLocaleString()}</p>
                      </div>
                      <div className="rounded-[var(--r-sm)] bg-[var(--paper-2)] p-3.5 col-span-2 sm:col-span-1">
                        <p className="text-[10px] uppercase tracking-[.1em] text-[var(--muted)]">Average views</p>
                        <p className="font-display font-bold text-[22px] tracking-[-.04em] mt-1">{account.avg_views == null ? "—" : Number(account.avg_views).toLocaleString()}</p>
                      </div>
                    </div>

                    <p className="text-[11px] text-[var(--muted)] leading-relaxed mt-4">
                      {account.mode === "oauth"
                        ? "Stats come from your connected platform where available. Some post insights may not be exposed by the platform."
                        : "This profile is linked manually. Import a history file to populate analytics; live stats will not be fetched until the platform is connected."}
                    </p>
                    <p className="mono text-[9px] text-[var(--muted)] mt-2">
                      Last updated: {account.last_synced_at ? new Date(account.last_synced_at).toLocaleString() : "Not synced yet"}
                    </p>

                    <div className="flex flex-wrap gap-2 mt-5">
                      {account.mode === "oauth" && (
                        <button className="btn btn-signal btn-sm" onClick={() => sync(account.id)} disabled={busy === account.id}>
                          {busy === account.id ? "Syncing…" : "Sync live stats"}
                        </button>
                      )}
                      {provider.configured && (
                        <button className="btn btn-ghost btn-sm" onClick={() => oauthStart(provider.platform)} disabled={busy === `oauth-${provider.platform}`}>
                          {busy === `oauth-${provider.platform}` ? "Opening…" : "Reconnect account"}
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" onClick={() => disconnect(account.id)} disabled={busy === account.id}>
                        Disconnect
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-[13px] text-[var(--ink-2)] leading-relaxed">
                      {instagram
                        ? "Bring in your Instagram profile and the post insights Meta makes available. You’ll choose the Facebook Page and Instagram account during the secure connection."
                        : "Connect the YouTube channel you manage to bring its public channel totals into your workspace."}
                    </p>

                    <div className="flex flex-wrap gap-2 mt-5">
                      {provider.configured && (
                        <button className="btn btn-signal btn-sm" onClick={() => oauthStart(provider.platform)} disabled={busy === `oauth-${provider.platform}`}>
                          {busy === `oauth-${provider.platform}`
                            ? "Opening secure connection…"
                            : `Connect ${instagram ? "Instagram" : "YouTube"}`}
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" onClick={() => setManualOpen({ ...manualOpen, [provider.platform]: !manual })}>
                        {manual ? "Cancel manual setup" : "Add profile manually"}
                      </button>
                    </div>
                    {!provider.configured && (
                      <p className="text-[11px] text-[var(--muted)] mt-3">Direct connection is not configured yet. You can add the profile manually and import history in the meantime.</p>
                    )}
                    {oldPlaceholderExists && (
                      <p className="text-[11px] text-[var(--signal-deep)] mt-3">Your previous connection did not resolve to a real platform profile. Reconnect to finish linking the correct account.</p>
                    )}

                    {manual && (
                      <div className="mt-5 pt-5 border-t border-[var(--hairline)] space-y-3">
                        <div>
                          <label className="field-label" htmlFor={`handle-${provider.platform}`}>Account handle</label>
                          <div className="flex">
                            <span className="mono text-[12px] px-3 flex items-center border border-r-0 border-[var(--hairline)] bg-[var(--paper-2)] text-[var(--muted)]">@</span>
                            <input
                              id={`handle-${provider.platform}`}
                              className="field"
                              placeholder={instagram ? "your.account" : "yourchannel"}
                              value={handle[provider.platform]}
                              onChange={(e) => setHandle({ ...handle, [provider.platform]: e.target.value })}
                            />
                          </div>
                        </div>
                        <div>
                          <label className="field-label" htmlFor={`name-${provider.platform}`}>Display name (optional)</label>
                          <input
                            id={`name-${provider.platform}`}
                            className="field"
                            placeholder="Channel or creator name"
                            value={name[provider.platform]}
                            onChange={(e) => setName({ ...name, [provider.platform]: e.target.value })}
                          />
                        </div>
                        <button className="btn btn-signal btn-sm" onClick={() => connect(provider.platform)} disabled={!handle[provider.platform].trim() || busy === provider.platform}>
                          {busy === provider.platform ? "Adding…" : "Save profile"}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel title="Built around your identity">
          <p className="text-[12px] text-[var(--muted)] leading-relaxed">Your analyses and history stay tied to the creator profile you choose, instead of mixing numbers from unrelated Pages or channels.</p>
        </Panel>
        <Panel title="Live data, clearly labelled">
          <p className="text-[12px] text-[var(--muted)] leading-relaxed">Use Sync live stats to refresh the profile and recent post data the platform provides. Unavailable metrics remain unavailable rather than being guessed.</p>
        </Panel>
        <Panel title="You stay in control">
          <p className="text-[12px] text-[var(--muted)] leading-relaxed">You can disconnect an account at any time. SocialBoost’s scheduled publishing remains simulated until a separate publishing flow is enabled.</p>
        </Panel>
      </div>
    </>
  );
}
