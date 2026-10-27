"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/Brand";

const links = [
  { href: "/product", label: "Product" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
];

export default function SiteNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 border-b transition-colors duration-300 ${
        scrolled ? "border-[var(--hairline)] bg-[rgba(239,238,234,0.86)] backdrop-blur-xl" : "border-transparent bg-transparent"
      }`}
    >
      <div className="wrap h-[66px] flex items-center justify-between gap-6">
        <Link href="/" aria-label="SocialBoost AI home">
          <Wordmark />
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {links.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`relative px-3.5 py-2 text-[13.5px] font-medium rounded-[var(--r-pill)] transition-colors ${
                  active ? "text-[var(--ink)] bg-[var(--paper)]" : "text-[var(--ink-2)] hover:text-[var(--ink)]"
                }`}
              >
                {l.label}
                {active && <span className="absolute -bottom-[1px] left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />}
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link href="/login" className="px-3 py-2 text-[13.5px] font-medium text-[var(--ink-2)] hover:text-[var(--ink)] transition-colors">
            Sign in
          </Link>
          <Link href="/signup" className="btn btn-signal btn-sm">Start free</Link>
        </div>

        <button
          className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-[10px] border border-[var(--hairline-strong)] bg-[var(--paper)]"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-label="Toggle navigation"
        >
          <span className="relative w-4 h-[10px]">
            <span className={`absolute left-0 right-0 h-[1.5px] bg-[var(--ink)] transition-all ${open ? "top-1/2 rotate-45" : "top-0"}`} />
            <span className={`absolute left-0 right-0 h-[1.5px] bg-[var(--ink)] transition-all ${open ? "top-1/2 -rotate-45" : "bottom-0"}`} />
          </span>
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-[var(--hairline)] bg-[var(--paper)] px-6 py-5 flex flex-col gap-1 shadow-[var(--shadow-md)]">
          {links.map((l) => (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="py-2.5 text-[15px] font-medium">
              {l.label}
            </Link>
          ))}
          <div className="h-px bg-[var(--hairline)] my-3" />
          <Link href="/login" onClick={() => setOpen(false)} className="py-2.5 text-[15px] font-medium">Sign in</Link>
          <Link href="/signup" onClick={() => setOpen(false)} className="btn btn-signal btn-block mt-2">Start free</Link>
        </div>
      )}
    </header>
  );
}
