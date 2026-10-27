"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Wordmark } from "@/components/Brand";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      await login(email, password);
      router.push("/app");
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
        <div className="absolute -top-40 -right-24 w-[560px] h-[560px] rounded-full opacity-70 blur-3xl" style={{ background: "radial-gradient(circle, rgba(240,80,31,.9), rgba(240,80,31,0) 62%)" }} />
        <div className="absolute inset-0 halftone text-white/10 opacity-40" />

        <Link href="/" className="relative"><Wordmark light size={16} mark={26} /></Link>

        <div className="relative">
          <p className="eyebrow">Studio access</p>
          <h1 className="display-2 mt-5 text-white">
            Make every
            <br />
            second count.
          </h1>
          <p className="lede mt-6 max-w-sm">Sign in to see your connected channels, analyses and scheduled releases.</p>
        </div>

        <div className="relative flex items-center justify-between">
          <span className="label">SocialBoost AI</span>
          <span className="label">Local build · sandbox</span>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-[400px]">
          <Link href="/" className="lg:hidden inline-flex mb-10">
            <Wordmark size={15} mark={24} />
          </Link>

          <p className="eyebrow">Sign in</p>
          <h2 className="display-3 mt-4">Welcome back.</h2>
          <p className="text-[13px] text-[var(--muted)] mt-2.5">Use your studio account to continue.</p>

          <form onSubmit={submit} className="mt-9 space-y-4">
            <div>
              <label className="field-label" htmlFor="email">Email</label>
              <input id="email" type="email" required autoComplete="email" className="field" placeholder="you@studio.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="password">Password</label>
              <input id="password" type="password" required autoComplete="current-password" className="field" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {err && <p className="text-[12.5px] text-[var(--red)] font-medium">{err}</p>}
            <button className="btn btn-signal btn-block" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
          </form>

          <p className="mt-6 text-[13px] text-[var(--muted)]">
            No account? <Link href="/signup" className="text-[var(--signal)] font-semibold underline underline-offset-4">Create one</Link>
          </p>

          <div className="mt-9 rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--paper)] px-4 py-3">
            <p className="label mb-1.5">Demo account</p>
            <p className="mono text-[11.5px] text-[var(--ink-2)]">test@test.com / pass123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
