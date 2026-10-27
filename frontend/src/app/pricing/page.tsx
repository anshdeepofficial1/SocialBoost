import Link from "next/link";
import SiteNav from "@/components/SiteNav";

const plans = [
  {
    name: "Solo",
    price: "Free",
    note: "While in local preview",
    features: ["1 workspace", "Unlimited uploads on this machine", "Hook and technical analysis", "CSV history import", "Sandbox scheduling"],
    cta: "Create account",
    href: "/signup",
    accent: false,
  },
  {
    name: "Studio",
    price: "—",
    note: "Not for sale in this build",
    features: ["Everything in Solo", "Model training and versioning", "Platform comparison", "Connected account records", "Recommendation queue"],
    cta: "Open the studio",
    href: "/signup",
    accent: true,
  },
  {
    name: "Scale",
    price: "—",
    note: "Requires production OAuth",
    features: ["Everything in Studio", "Real provider credentials", "Scheduled publishing", "Team workspaces", "Audit history"],
    cta: "Read the limits",
    href: "/how-it-works",
    accent: false,
  },
];

export default function Pricing() {
  return (
    <main className="bg-[var(--canvas)] text-[var(--ink)]">
      <SiteNav />
      <section className="pt-32 md:pt-40 pb-12">
        <div className="wrap">
          <p className="eyebrow">Pricing</p>
          <h1 className="display-1 mt-6 max-w-4xl">
            No checkout
            <br />
            <span className="text-[var(--muted)]">theatre.</span>
          </h1>
          <p className="lede mt-8 max-w-xl">
            This is a local build. There is no billing integration, and no plan is being sold. The tiers below describe intended scope, not a live product.
          </p>
        </div>
      </section>

      <section className="border-t border-[var(--hairline)]">
        <div className="wrap py-14">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {plans.map((p) => (
              <div key={p.name} className={`rounded-[var(--r)] p-6 flex flex-col ${p.accent ? "block-ink" : "panel panel-hover"}`}>
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: p.accent ? "var(--night-muted)" : "var(--muted)" }}>{p.name}</p>
                  {p.accent && <span className="tag tag-signal">Most complete</span>}
                </div>
                <p className={`font-display font-bold text-[46px] tracking-[-0.04em] mt-6 leading-none ${p.accent ? "text-white" : ""}`}>{p.price}</p>
                <p className="text-[11px] mt-2" style={{ color: p.accent ? "var(--night-muted)" : "var(--muted)" }}>{p.note}</p>
                <ul className="mt-7 flex-1">
                  {p.features.map((f) => (
                    <li
                      key={f}
                      className={`flex items-start gap-2.5 py-2.5 border-t text-[12.5px] ${p.accent ? "border-[var(--night-line)] text-[var(--night-body)]" : "border-[var(--hairline)]"}`}
                    >
                      <span className="text-[13px] leading-none text-[var(--signal)] pt-0.5">+</span>{f}
                    </li>
                  ))}
                </ul>
                <Link href={p.href} className={`btn mt-7 ${p.accent ? "btn-signal" : "btn-ghost"}`}>{p.cta}</Link>
              </div>
            ))}
          </div>

          <div className="mt-8 panel p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="tag tag-sage mt-0.5"><span className="dot" />Honest</span>
              <p className="text-[13px] text-[var(--muted)] max-w-2xl leading-relaxed">
                No card is collected, no subscription is created, and no feature is gated behind a fake paywall.
              </p>
            </div>
            <Link href="/signup" className="btn btn-ghost btn-sm shrink-0">Get started</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
