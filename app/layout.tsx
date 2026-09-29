import type { Metadata } from "next";
import { Barlow, Barlow_Condensed, Geist_Mono } from "next/font/google";
import { BottomNav } from "@/components/bottom-nav";
import { Mark } from "@/components/mark";
import { formatGenerated } from "@/lib/format";
import { getSeason, previousWeek } from "@/lib/season";
import Link from "next/link";
import "./globals.css";

const sans = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-barlow",
  display: "swap",
});

const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display-face",
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Yardline",
    template: "%s · Yardline",
  },
  description:
    "A weekly NFL forecast you can check against the scoreboard. Research only. Not a bet recommendation.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  const season = getSeason();
  const last = previousWeek(season);
  const currentPath = `/week/${season.current.season}/${season.current.week}`;
  const lastPath = last ? `/week/${last.season}/${last.week}` : null;

  return (
    <html
      lang="en"
      className={`${sans.variable} ${display.variable} ${geistMono.variable} dark h-full antialiased`}
    >
      <body className="min-h-full">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-forecast focus:px-3 focus:py-2 focus:text-primary-foreground"
        >
          Skip to the slate
        </a>
        <div className="flex min-h-full flex-col">
          <header className="sticky top-0 z-30 border-b border-forecast/20 bg-background/85 backdrop-blur">
            <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
              <Link href="/" className="flex items-center gap-2 text-forecast">
                <Mark />
                <span className="font-display text-2xl tracking-[0.16em] text-foreground">
                  YARDLINE
                </span>
              </Link>
              <p className="hidden max-w-sm text-right text-xs leading-5 text-muted-foreground sm:block">
                A weekly NFL forecast you can check against the scoreboard.
                <span className="block text-uncertainty">
                  Updated {formatGenerated(season.generatedAt)}
                </span>
              </p>
            </div>
            <p className="px-4 pb-3 text-xs leading-5 text-muted-foreground sm:hidden">
              A weekly NFL forecast you can check against the scoreboard.
            </p>
          </header>
          <main id="content" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 pb-32">
            {children}
          </main>
          <BottomNav currentPath={currentPath} lastPath={lastPath} />
        </div>
      </body>
    </html>
  );
}
