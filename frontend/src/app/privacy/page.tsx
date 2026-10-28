import Link from "next/link";
import { Wordmark } from "@/components/Brand";

export const metadata = {
  title: "Privacy Policy",
  description: "How SocialBoost AI collects, uses, stores, and protects account and YouTube channel data.",
};

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="mt-8">
    <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
    <div className="mt-3 space-y-3 text-sm leading-7 text-[var(--ink-2)]">{children}</div>
  </section>
);

export default function PrivacyPage() {
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
        <h1 className="display-2 mt-4">Privacy Policy</h1>
        <p className="lede mt-5">
          This policy explains how SocialBoost AI ("SocialBoost", "we", "us") handles
          information when you use our creator analytics and content-planning service.
        </p>

        <Section title="Information we collect">
          <p>We collect the account information you provide, such as your email address, name, and workspace details. If you connect a social platform, we receive the information needed to identify the connected channel and provide the features you request.</p>
          <p>When you connect YouTube, SocialBoost requests read-only access using the YouTube Data API. Depending on what the API makes available, this may include your channel ID, channel name or handle, subscriber count, video count, view count, and related channel information. We do not request permission to upload, edit, or delete YouTube content.</p>
          <p>You may also provide video files, captions, CSV files, post history, and other information you choose to analyze or import. We process and store information needed to deliver analysis, analytics, planning, and history features.</p>
        </Section>

        <Section title="How we use information">
          <p>We use information to authenticate you, connect the channel you select, display channel information and available statistics, provide creator analysis and planning tools, maintain your workspace, secure the service, and troubleshoot failures.</p>
          <p>We use Google/YouTube user data only to provide or improve user-facing features that you request. We do not sell YouTube API data, use it for advertising, or use it to build advertising profiles. We do not use it for purposes unrelated to the service without your consent.</p>
        </Section>

        <Section title="OAuth tokens and storage">
          <p>When you authorize a platform, SocialBoost stores the tokens needed to maintain that connection. OAuth token payloads are encrypted by the application before being stored. Our production backend uses a managed PostgreSQL database; access to stored data is limited to the service functions that need it.</p>
          <p>No internet service can promise absolute security. Keep your sign-in credentials private and contact us promptly if you believe your account has been accessed without permission.</p>
        </Section>

        <Section title="Service providers and sharing">
          <p>We use infrastructure providers to host the website, run the backend, and store application data (currently Vercel, Render, and Neon). Google and YouTube process authorization and API requests when you connect a Google account. These providers may process information as needed to deliver their services under their own terms and privacy policies.</p>
          <p>We do not sell personal information. We disclose information only as needed to operate the service, at your direction, to protect users or the service, or when required by law.</p>
        </Section>

        <Section title="Retention and your choices">
          <p>We keep workspace information and imported history while needed to provide your account and its features. You can disconnect a connected channel from the Accounts page. Disconnecting stops the active connection in SocialBoost, but imported history may remain in your workspace.</p>
          <p>To ask about access to or deletion of information associated with your account, email us from the address below and identify your SocialBoost account. We may retain limited records where required for security, dispute resolution, or legal compliance.</p>
        </Section>

        <Section title="Children and changes">
          <p>SocialBoost is a creator productivity service and is not designed for children under 13. We may update this policy as the service changes. The latest version will be published on this page with its updated date.</p>
        </Section>

        <Section title="Contact">
          <p>For privacy questions or data requests, contact <a className="underline underline-offset-4" href="mailto:anshdeepofficial1@gmail.com">anshdeepofficial1@gmail.com</a>.</p>
        </Section>

        <div className="mt-12 flex flex-wrap gap-4 border-t border-[var(--hairline)] pt-6 text-sm">
          <Link href="/terms" className="underline underline-offset-4">Terms of Service</Link>
          <Link href="/" className="underline underline-offset-4">SocialBoost AI home</Link>
        </div>
      </article>
    </main>
  );
}
