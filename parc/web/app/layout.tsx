import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const sans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "PARC Lab",
  description: "LIBERO-plus / PARC2026 experiment console",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body className={`${sans.variable} ${mono.variable}`}>
        <div className="shell">
          <header className="topbar">
            <Link href="/" className="brand">
              PARC Lab
            </Link>
            <nav className="nav">
              <Link href="/">Runs</Link>
              <Link href="/#jobs">Jobs</Link>
              <Link href="/docs">Docs</Link>
              <a href="/api/v1/health" target="_blank" rel="noreferrer">
                API
              </a>
            </nav>
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
