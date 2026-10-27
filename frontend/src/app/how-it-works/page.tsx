import Link from "next/link";
import SiteNav from "@/components/SiteNav";

const steps = [
  { n: "01", t: "Connect your channels", d: "Link Instagram and YouTube so analysis, history and scheduling are attributed to a specific identity. Sandbox connections are labelled." },
  { n: "02", t: "Upload a video", d: "The file is stored locally and validated. The pipeline extracts duration, resolution, frame rate, brightness, contrast and sampled scene changes." },
  { n: "03", t: "Read the hook", d: "The opening window is isolated. Speech onset and on-screen text are reported when available; OCR gaps are stated, not hidden." },
  { n: "04", t: "Evaluate the format", d: "Aspect ratio, duration and resolution are checked against Reels and Shorts expectations, with specific issues listed." },
  { n: "05", t: "Import history", d: "A CSV of past posts becomes the evidence base. At least ten rows are required before a model will train." },
  { n: "06", t: "Predict a range", d: "The trained model returns expected views, engagement and a confidence value. No model, no fabricated number." },
  { n: "07", t: "Choose a platform", d: "The same asset is scored against both platforms. With thin evidence, no winner is declared." },
  { n: "08", t: "Schedule the release", d: "Add the job to the calendar. Sandbox jobs simulate publishing and are never reported as live." },
];

export default function HowItWorks() {
  return (
    <main className="bg-[var(--porcelain)] text-[var(--ink)]">
      <SiteNav />
      <section className="pt-32 md:pt-40 pb-12">
        <div className="wrap">
          <p className="eyebrow">How it works</p>
          <h1 className="display-1 mt-6 max-w-4xl">
            From upload
            <br />
            to release.
          </h1>
          <p className="lede mt-8 max-w-xl">
            Eight stages, each with a visible state. A failed step stops the run and surfaces the error instead of skipping ahead.
          </p>
        </div>
      </section>

      <section className="border-t border-[var(--hairline)]">
        <div className="wrap py-10">
          <ol className="border-t border-[var(--hairline)]">
            {steps.map((s) => (
              <li key={s.n} className="grid grid-cols-12 gap-4 py-8 border-b border-[var(--hairline)] items-start">
                <span className="col-span-2 md:col-span-1 mono text-[13px] font-medium text-[var(--signal)] pt-0.5">{s.n}</span>
                <h2 className="col-span-10 md:col-span-4 font-display font-bold text-[20px] tracking-[-0.02em] leading-snug">{s.t}</h2>
                <p className="col-span-12 md:col-span-7 text-[13.5px] text-[var(--muted)] leading-relaxed">{s.d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="night section relative overflow-hidden">
        <div className="absolute inset-0 hairgrid-dark opacity-40" />
        <div className="absolute -bottom-40 -left-20 w-[520px] h-[520px] rounded-full opacity-60 blur-3xl" style={{ background: "radial-gradient(circle, rgba(240,80,31,.7), rgba(240,80,31,0) 62%)" }} />
        <div className="wrap grid grid-cols-12 gap-8 items-center relative">
          <div className="col-span-12 lg:col-span-7">
            <p className="eyebrow">Under the hood</p>
            <h2 className="display-2 mt-5 text-white">Honest by<br />construction.</h2>
            <p className="lede mt-6 max-w-lg">
              OpenCV extracts features. Scikit-learn trains on your imported rows. FastAPI serves the results. Every unavailable capability returns a labelled gap.
            </p>
          </div>
          <div className="col-span-12 lg:col-span-5">
            <dl className="rounded-[var(--r)] border border-[var(--night-line)] p-6 bg-[rgba(255,255,255,.02)]">
              {[
                ["Feature extraction", "OpenCV"],
                ["Prediction model", "RandomForest"],
                ["Minimum training rows", "10"],
                ["OCR", "Unavailable"],
                ["Live publishing", "Sandbox"],
              ].map(([k, v], i) => (
                <div key={k} className={`flex justify-between py-3 ${i > 0 ? "border-t border-[var(--night-line)]" : ""}`}>
                  <dt className="text-[13px] text-[var(--night-body)]">{k}</dt>
                  <dd className="mono text-[11.5px] text-[var(--night-soft)]">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
          <h2 className="display-2 max-w-xl">Ready to read<br />your own signal?</h2>
          <div className="flex gap-3">
            <Link href="/signup" className="btn btn-signal">Create account</Link>
            <Link href="/product" className="btn btn-ghost">Product</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
