"use client";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PlatformMark } from "@/components/app/ui";
import { Wordmark } from "@/components/Brand";

const nav = [
  { href: "/app", label: "Overview", num: "00" },
  { href: "/app/analyze", label: "Analyze", num: "01" },
  { href: "/app/hook-lab", label: "Hook Lab", num: "02" },
  { href: "/app/predictions", label: "Predictions", num: "03" },
  { href: "/app/platform-comparison", label: "Platforms", num: "04" },
  { href: "/app/youtube", label: "YouTube Studio", num: "05" },
  { href: "/app/calendar", label: "Calendar", num: "06" },
  { href: "/app/analytics", label: "Analytics", num: "07" },
  { href: "/app/library", label: "Library", num: "08" },
  { href: "/app/recommendations", label: "Recommendations", num: "09" },
  { href: "/app/datasets", label: "Datasets", num: "10" },
  { href: "/app/integrations", label: "Accounts", num: "11" },
  { href: "/app/settings", label: "Settings", num: "12" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    api.socialAccounts().then(setAccounts).catch(() => {});
  }, [user, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)]">
        <span className="label animate-pulse">Loading studio…</span>
      </div>
    );
  }
  if (!user) return null;

  const isPlaceholder = (a: any) => typeof a?.handle === "string" && /^(instagram|youtube)-user-/i.test(a.handle);
  const ig = accounts.find((a) => a.platform === "instagram" && !isPlaceholder(a));
  const yt = accounts.find((a) => a.platform === "youtube" && !isPlaceholder(a));

  const Rail = (
    <aside className="app-rail w-[262px] shrink-0 border-r border-[var(--hairline)] bg-[var(--paper)] flex flex-col h-full">
      <div className="px-5 h-[66px] flex items-center justify-between border-b border-[var(--hairline)]">
        <Link href="/" aria-label="SocialBoost home">
          <Wordmark />
        </Link>
        <button className="lg:hidden text-[var(--muted)] text-[15px]" onClick={() => setOpen(false)} aria-label="Close menu">✕</button>
      </div>

      {/* connected accounts surfaced immediately */}
      <div className="px-4 py-4 border-b border-[var(--hairline)]">
        <div className="flex items-center justify-between mb-3">
          <p className="label">Connected</p>
          <Link href="/app/integrations" className="text-[11px] font-semibold text-[var(--signal)]">Manage</Link>
        </div>
        <div className="space-y-2">
          {[
            { p: "instagram", a: ig, label: "Instagram" },
            { p: "youtube", a: yt, label: "YouTube" },
          ].map(({ p, a, label }) => {
            const active = pathname.startsWith("/app/integrations");
            return (
              <Link
                key={p}
                href="/app/integrations"
                className={`flex items-center gap-3 px-2.5 py-2 rounded-[var(--r-sm)] border transition-colors ${
                  active ? "border-[var(--ink)]" : "border-[var(--hairline)] hover:border-[var(--hairline-strong)]"
                }`}
              >
                <PlatformMark platform={p} size={28} imageUrl={a?.profile_picture_url} />
                <span className="min-w-0 flex-1">
                  <span className="block text-[12px] font-medium truncate">{a ? `@${a.handle}` : label}</span>
                  <span className="block text-[10px] uppercase tracking-[0.08em] text-[var(--muted)]">
                    {a ? (a.mode === "sandbox" ? "manual profile" : a.status === "needs_reauth" ? "reconnect needed" : a.platform === "youtube" ? "connected via Google" : "connected via Meta") : "not connected"}
                  </span>
                </span>
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: a ? (a.status === "needs_reauth" ? "var(--signal)" : "var(--sage-deep)") : "var(--hairline-strong)" }} />
              </Link>
            );
          })}
        </div>
      </div>

      <nav className="flex-1 py-3 overflow-y-auto">
        {nav.map((n) => {
          const active = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className="rail-link" data-active={active} aria-current={active ? "page" : undefined} onClick={() => setOpen(false)}>
              <span className="rail-num">{n.num}</span>
              {n.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-[var(--hairline)]">
        <div className="flex items-center gap-2.5 px-2 py-2">
          <span className="w-8 h-8 rounded-full bg-[var(--ink)] text-white flex items-center justify-center text-[11px] font-semibold uppercase shrink-0">
            {(user.full_name || user.email).slice(0, 2)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[12px] font-medium truncate">{user.full_name || "Studio owner"}</p>
            <p className="text-[10.5px] text-[var(--muted)] truncate">{user.email}</p>
          </div>
        </div>
        <button onClick={logout} className="w-full text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)] hover:text-[var(--ink)] px-2 py-2 transition-colors">
          Sign out
        </button>
      </div>
    </aside>
  );

  return (
    <div className="app-shell min-h-screen bg-[var(--canvas)] text-[var(--ink)] flex">
      <div className="hidden lg:block h-screen sticky top-0">{Rail}</div>

      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="h-full">{Rail}</div>
          <div className="flex-1 bg-[rgba(12,12,10,0.5)] backdrop-blur-sm" onClick={() => setOpen(false)} />
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <div className="lg:hidden h-[58px] border-b border-[var(--hairline)] bg-[var(--paper)] flex items-center justify-between px-4 sticky top-0 z-40">
          <button onClick={() => setOpen(true)} className="inline-flex items-center justify-center w-10 h-10 rounded-[10px] border border-[var(--hairline-strong)]" aria-label="Open menu">
            <span className="flex flex-col gap-[3px]">
              <span className="w-4 h-[1.5px] bg-[var(--ink)]" />
              <span className="w-4 h-[1.5px] bg-[var(--ink)]" />
            </span>
          </button>
          <Wordmark />
          <Link href="/app/analyze" className="text-[11px] font-semibold text-[var(--signal)] uppercase tracking-[0.08em]">New</Link>
        </div>

        <main className="flex-1 min-w-0">
          <div className="max-w-[1300px] mx-auto px-5 md:px-8 py-8 md:py-11">{children}</div>
        </main>
      </div>
    </div>
  );
}
