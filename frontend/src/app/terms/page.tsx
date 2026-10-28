import Link from "next/link";
import { Wordmark } from "@/components/Brand";

export const metadata = {
  title: "Terms of Service",
  description: "Terms for using SocialBoost AI creator analytics and content-planning tools.",
};

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="mt-8">
    <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
    <div className="mt-3 space-y-3 text-sm leading-7 text-[var(--ink-2)]">{children}</div>
  </section>
);

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <header className="border-b border-[var(--hairline)] bg-[var(--paper)]">
        <div className="wrap flex items-center justify-between gap-4 py-5">
          <Link href="/" aria-label="SocialBoost AI home"><Wordmark size={23} mark={34} /></Link>
          <Link href="/" className="btn btn-ghost btn-sm">Back to home</Link>
        </div>
      </header>
      <article className="wrap max-w-3xl py-12 md:py-16">
        <p className="label">Legal · Last updated October 28, 2026</p>
        <h1 className="display-2 mt-4">Terms of Service</h1>
        <p className="lede mt-5">
          These terms govern your use of SocialBoost AI ("SocialBoost", "we", "us").
          By using the service, you agree to these terms.
        </p>

        <Section title="Using SocialBoost">
          <p>You must provide accurate account information, protect your sign-in credentials, and use the service lawfully. You are responsible for activity in your account and for ensuring that you have permission to connect any channel, upload any file, or import any dataset you submit.</p>
          <p>You must not attempt to bypass security, disrupt the service, access another user's workspace, or use SocialBoost to infringe another person's rights or violate a platform's terms.</p>
        </Section>

        <Section title="Connected platforms and permissions">
          <p>When you connect YouTube or another supported platform, you authorize SocialBoost to access the information permitted by the scopes shown during that platform's consent flow. You must own or be authorized to manage the account you connect. Platform access is governed by the platform's own terms and permissions, and you can disconnect an account from SocialBoost.</p>
          <p>YouTube data is requested through Google's YouTube Data API. SocialBoost's current YouTube connection is read-only: it retrieves channel information and available statistics. Live publishing is not enabled, and scheduled publishing must not be interpreted as a successful publication.</p>
        </Section>

        <Section title="Analytics and availability">
          <p>SocialBoost presents platform-provided data, imported history, and analysis generated from information available to the service. Statistics may be delayed, incomplete, changed by a provider, or unavailable because of account permissions or API limitations. Predictions and recommendations are informational and are not guarantees of future performance.</p>
          <p>We work to keep the service available, but features may change or be temporarily unavailable for maintenance, security, or provider-side reasons.</p>
        </Section>

        <Section title="Your content and data">
          <p>You retain the rights you have in content and data you upload. You give SocialBoost permission to process that material only as needed to operate the features you request. Do not upload material you are not entitled to use.</p>
          <p>Our handling of account information, connected-platform data, retention, and data requests is described in our <Link href="/privacy" className="underline underline-offset-4">Privacy Policy</Link>.</p>
        </Section>

        <Section title="Third-party services">
          <p>SocialBoost may rely on third-party services such as Google, YouTube, Vercel, Render, and Neon. Their services are subject to their own terms, availability, and privacy practices. We are not responsible for provider outages or changes to third-party APIs, permissions, or policies.</p>
        </Section>

        <Section title="Changes and termination">
          <p>You may stop using SocialBoost at any time. We may suspend access where reasonably needed to protect the service, comply with law, or address misuse. We may update these terms as the service evolves; the current version and update date will appear here.</p>
        </Section>

        <Section title="Disclaimer and contact">
          <p>To the extent permitted by law, SocialBoost is provided on an "as available" basis without a guarantee that every metric, integration, or recommendation will always be available or accurate. Nothing in these terms limits rights that cannot legally be limited.</p>
          <p>Questions about these terms can be sent to <a className="underline underline-offset-4" href="mailto:anshdeepofficial1@gmail.com">anshdeepofficial1@gmail.com</a>.</p>
        </Section>

        <div className="mt-12 flex flex-wrap gap-4 border-t border-[var(--hairline)] pt-6 text-sm">
          <Link href="/privacy" className="underline underline-offset-4">Privacy Policy</Link>
          <Link href="/" className="underline underline-offset-4">SocialBoost AI home</Link>
        </div>
      </article>
    </main>
  );
}
