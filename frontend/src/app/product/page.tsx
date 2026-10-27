import Link from "next/link";
import SiteNav from "@/components/SiteNav";

export default function Product() {
  return (
    <main className="bg-[var(--porcelain)] text-[var(--ink)]">
      <SiteNav />
      <section className="pt-32 md:pt-40 pb-14">
        <div className="wrap">
          <p className="eyebrow">Product</p>
          <h1 className="display-1 mt-6 max-w-4xl">
            Content intelligence,
            <br />
            <span className="text-[var(--muted)]">without the theatre.</span>
          </h1>
          <div className="grid grid-cols-12 gap-6 mt-10">
            <div className="col-span-12 md:col-span-7">
              <p className="lede max-w-xl">
                Signal Studio reads the media you already made. It measures what is measurable, estimates what a model supports, and leaves the rest visibly unknown.
              </p>
            </div>
            <div className="col-span-12 md:col-span-5 md:text-right">
              <Link href="/signup" className="btn btn-signal btn-lg">Open the studio</Link>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-[var(--hairline)]">
        <div className="wrap py-14">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-[var(--hairline)] border border-[var(--hairline)] rounded-[var(--r)] overflow-hidden">
            {[
              { n: "01", t: "Hook analysis", d: "Opening window, speech onset, on-screen text where OCR is available, and a transparent heuristic score.", h: "/app/hook-lab" },
              { n: "02", t: "Technical signal", d: "Duration, resolution, frame rate, brightness, contrast and sampled scene changes from the actual file.", h: "/app/analyze" },
              { n: "03", t: "Prediction range", d: "A model trained on your imported history returns a range and a confidence value — never a virality guarantee.", h: "/app/predictions" },
              { n: "04", t: "Platform fit", d: "The same asset scored against Instagram and YouTube expectations, with your own evidence where it exists.", h: "/app/platform-comparison" },
              { n: "05", t: "Publishing plan", d: "Drafts and scheduled jobs on one calendar. Sandbox jobs are labelled and simulated.", h: "/app/calendar" },
              { n: "06", t: "Connected accounts", d: "Link both channels so analysis and scheduling are attributed to a real identity.", h: "/app/integrations" },
            ].map((f) => (
              <Link key={f.n} href={f.h} className="bg-[var(--paper)] p-7 group hover:bg-[var(--paper-2)] transition-colors">
                <div className="flex items-start justify-between">
                  <span className="num">{f.n}</span>
                  <span className="text-[15px] text-[var(--hairline-strong)] group-hover:text-[var(--signal)] transition-colors">→</span>
                </div>
                <h3 className="font-display font-bold text-[19px] tracking-[-0.02em] mt-10">{f.t}</h3>
                <p className="text-[13px] text-[var(--muted)] leading-relaxed mt-2.5">{f.d}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="night section relative overflow-hidden">
        <div className="absolute inset-0 hairgrid-dark opacity-40" />
        <div className="absolute -top-40 right-0 w-[520px] h-[520px] rounded-full opacity-60 blur-3xl" style={{ background: "radial-gradient(circle, rgba(240,80,31,.7), rgba(240,80,31,0) 62%)" }} />
        <div className="wrap grid grid-cols-12 gap-8 items-start relative">
          <div className="col-span-12 lg:col-span-5">
            <p className="eyebrow">Principles</p>
            <h2 className="display-2 mt-5 text-white">No fake<br />metrics.</h2>
          </div>
          <div className="col-span-12 lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-6">
            {[
              ["Measured", "Extracted directly from the uploaded file. Reproducible."],
              ["Estimated", "Model output with a range and confidence. Always labelled."],
              ["Unknown", "Missing audio, OCR or history is reported as a gap."],
              ["Simulated", "Sandbox publishing never claims a real post went live."],
            ].map(([t, d]) => (
              <div key={t} className="border-t border-[var(--night-line)] pt-5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--signal)]">{t}</p>
                <p className="text-[13.5px] text-[var(--night-body)] leading-relaxed mt-2.5">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
          <div>
            <p className="eyebrow">Next</p>
            <h2 className="display-2 mt-4">See the workflow.</h2>
          </div>
          <div className="flex gap-3">
            <Link href="/how-it-works" className="btn btn-ghost">How it works</Link>
            <Link href="/pricing" className="btn btn-signal">Pricing</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
