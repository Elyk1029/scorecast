import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Separator } from "@/components/ui/separator";
import { formatGenerated, formatSigned } from "@/lib/format";
import { getSeason } from "@/lib/season";

export const metadata: Metadata = {
  title: "Method",
};

export default function MethodPage() {
  const file = getSeason();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Method"
        title="How the number is made"
        lede="Short version: scoring form, Elo strength, rest, and home field estimate the score. A separate calibration turns that margin into win probability. Every coefficient is trained on completed prior seasons only."
      />
      <p className="text-xs tracking-wide text-uncertainty uppercase">
        {file.modelVersion} · updated {formatGenerated(file.generatedAt)} · home field{" "}
        {formatSigned(file.homeField)}
      </p>

      <div className="max-w-2xl space-y-6 text-sm leading-6">
        <Section title="Past games only">
          The entire week is forecast before any result from that week updates a rating, so a Sunday result cannot leak into another game on the same slate. Scoring form and Elo carry into a new season at reduced strength. The regression and probability coefficients are then fit once using completed prior seasons and held fixed for the season being forecast.
        </Section>
        <Section title="The score">
          A ridge regression estimates margin from opponent-adjusted scoring form, Elo difference, rest difference, and home field. A second regression estimates the total from both teams’ scoring form and their strength gap. The penalty keeps noisy features from producing extreme scores. The published score is the fitted mean, rounded; the model spread keeps the unrounded margin. The slate band is 18 points either side of each team’s mean.
        </Section>
        <Section title="Locked forecasts">
          A week becomes locked when it is the current slate. Later refreshes add the scoreboard but keep its score, probability, players, context, and comparison line unchanged. Future weeks are provisional. Older reconstructed games are labeled as backtests rather than pretending they were published live.
        </Section>
        <Section title="Home field">
          Home field is a single number, currently {formatSigned(file.homeField)} points, fit from completed prior seasons. Neutral sites get none of it. It is one row on the game sheet, not a secret factor.
        </Section>
        <Section title="Quarterback">
          If the recent starter is out or doubtful before an upcoming game, that team is docked 3.5 points. Questionable is written down and does not change the score. Historical backtests do not use week-level injury rows because nflverse does not provide a reliable pre-kickoff timestamp for this feed.
        </Section>
        <Section title="Win probability">
          A regularized logistic calibration learns how often each fitted margin became a home win in completed prior seasons. Home win, away win, and tie always sum to 100%. If the rounded score is level, the card flags likely overtime instead of inventing an exact overtime score. About six percent of regular-season overtimes still end tied.
        </Section>
        <Section title="Player lines">
          Quarterback attempts and running back carries follow recent volume, shrunk toward a typical week. Yards are that volume times a shrunk per-play rate. The bar is a fixed window around the median, about eight attempts, 70 passing yards, five carries, and 32 rushing yards either side. If the leader is out or doubtful, the line moves to the next player with enough recent work. Only an unavailable quarterback changes the team score, by 3.5 points. It is not a sportsbook prop and not a full player simulation.
        </Section>
        <Section title="What does not move the score">
          EPA, weather, roof, and travel across time zones are context in this version. They are worth zero points because adding EPA did not improve the held-out margin and win metrics. An early East Coast body-clock spot, or wind at 20 mph or more, can show up as an X-factor, also worth zero, until that idea earns a backtest. If it is on the card and it is not in the adjustment list, it did not change the number.
        </Section>
        <Section title="The posted line">
          Spread, total, and the no-vig price from nflverse are stored beside the forecast so the record can be compared. They are not model inputs. They are not a live sportsbook. On the{" "}
          <Link href="/accuracy" className="text-forecast underline-offset-4 hover:underline">
            record
          </Link>{" "}
          the posted line has been the sharper probability. Yardline does not claim to beat the market.
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="font-display text-2xl tracking-wide">{title}</h2>
      <p>{children}</p>
      <Separator />
    </section>
  );
}
