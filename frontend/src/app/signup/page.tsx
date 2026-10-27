"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Wordmark } from "@/components/Brand";

export default function Signup() {
  const { signup } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) { setErr("Use at least 6 characters."); return; }
    setLoading(true);
    setErr("");
    try {
      await signup(email, password, name);
      router.push("/app/integrations");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--canvas)] grid lg:grid-cols-[1.05fr_1fr]">
      <div className="hidden lg:flex night flex-col justify-between p-11 relative overflow-hidden">
        <div className="absolute inset-0 hairgrid-dark opacity-50" />
        <div className="absolute -top-40 -left-24 w-[560px] h-[560px] rounded-full opacity-70 blur-3xl" style={{ background: "radial-gradient(circle, rgba(240,80,31,.9), rgba(240,80,31,0) 62%)" }} />
        <div className="absolute inset-0 halftone text-white/10 opacity-40" />

        <Link href="/" className="relative"><Wordmark light size={16} mark={26} /></Link>

        <div className="relative">
          <p className="eyebrow">New studio</p>
          <h1 className="display-2 mt-5 text-white">
            Analyze.
            <br />
            Predict.
            <br />
            <span className="text-[var(--signal)]">Publish.</span>
          </h1>
          <ol className="mt-9 space-y-3 max-w-xs">
            {["Create your workspace", "Connect Instagram and YouTube", "Upload your first video"].map((s, i) => (
              <li key={s} className="flex items-center gap-3 text-[13px] text-[var(--night-body)]">
                <span className="mono text-[10px] text-[var(--night-muted)]">0{i + 1}</span>{s}
              </li>
            ))}
          </ol>
        </div>

        <span className="relative label">Local build · no fake metrics</span>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-[400px]">
          <Link href="/" className="lg:hidden inline-flex mb-10">
            <Wordmark size={15} mark={24} />
          </Link>

          <p className="eyebrow">Create account</p>
          <h2 className="display-3 mt-4">Start your studio.</h2>
          <p className="text-[13px] text-[var(--muted)] mt-2.5">You will connect your channels next.</p>

          <form onSubmit={submit} className="mt-9 space-y-4">
            <div>
              <label className="field-label" htmlFor="name">Name</label>
              <input id="name" required className="field" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="email">Email</label>
              <input id="email" type="email" required autoComplete="email" className="field" placeholder="you@studio.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <input id="password" type="password" required autoComplete="new-password" className="field" placeholder="At least 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {err && <p className="text-[12.5px] text-[var(--red)] font-medium">{err}</p>}
            <button className="btn btn-signal btn-block" disabled={loading}>{loading ? "Creating…" : "Create account"}</button>
          </form>

          <p className="mt-6 text-[13px] text-[var(--muted)]">
            Already have an account? <Link href="/login" className="text-[var(--signal)] font-semibold underline underline-offset-4">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
