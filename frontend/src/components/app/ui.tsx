"use client";
import Link from "next/link";
import { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-9">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6">
        <div className="max-w-3xl">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="display-3 mt-4">{title}</h1>
          {description && <p className="lede mt-4 text-[15px] max-w-2xl">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2.5 shrink-0">{actions}</div>}
      </div>
      <div className="mt-8 h-px w-full bg-[var(--hairline)]" />
    </header>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="panel panel-hover p-5">
      <p className="stat-label">{label}</p>
      <p className="stat-value mt-3">{value}</p>
      {hint && <p className="mono text-[10px] text-[var(--muted)] mt-2.5">{hint}</p>}
    </div>
  );
}

export function Panel({
  title,
  aside,
  children,
  className = "",
  flush = false,
}: {
  title?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={`panel overflow-hidden ${className}`}>
      {(title || aside) && (
        <div className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-[var(--hairline)]">
          {title && <p className="label">{title}</p>}
          {aside}
        </div>
      )}
      <div className={flush ? "" : "p-5"}>{children}</div>
    </section>
  );
}

export function Empty({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="border border-dashed border-[var(--hairline-strong)] rounded-[var(--r)] px-6 py-12 text-center bg-[var(--paper-2)]">
      <p className="font-display font-bold text-[18px] tracking-[-0.02em]">{title}</p>
      <p className="text-[13px] text-[var(--muted)] mt-2 max-w-sm mx-auto leading-relaxed">{body}</p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function Meter({ value, max = 100, tone = "signal" }: { value: number; max?: number; tone?: "signal" | "ink" | "cobalt" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={`meter ${tone === "ink" ? "meter-ink" : tone === "cobalt" ? "meter-cobalt" : ""}`}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

export function PlatformMark({ platform, size = 26 }: { platform: string; size?: number }) {
  const ig = platform.toLowerCase().startsWith("insta") || platform === "instagram";
  return (
    <span
      className="inline-flex items-center justify-center shrink-0 font-semibold"
      style={{
        width: size,
        height: size,
        borderRadius: Math.max(6, size * 0.28),
        background: ig ? "var(--signal)" : "var(--cobalt)",
        color: "#fff",
        fontSize: size * 0.38,
        fontFamily: "var(--font-display)",
        letterSpacing: "-0.02em",
      }}
      aria-hidden="true"
    >
      {ig ? "IG" : "YT"}
    </span>
  );
}

export function StatusTag({ status }: { status: string }) {
  const s = (status || "").toLowerCase();
  const cls =
    s === "done" || s === "connected" || s === "published"
      ? "tag-sage"
      : s === "failed" || s === "needs_reauth"
      ? "tag-red"
      : s === "scheduled" || s === "processing"
      ? "tag-signal"
      : "tag";
  return (
    <span className={`tag ${cls}`}>
      <span className="dot" />
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function LinkButton({ href, children, variant = "ghost" }: { href: string; children: ReactNode; variant?: "ghost" | "signal" | "dark" }) {
  return (
    <Link href={href} className={`btn btn-${variant} btn-sm`}>
      {children}
    </Link>
  );
}
