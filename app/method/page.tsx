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
        lede="Short version: separate home and away score regressions use scoring form, the opponent’s defense, Elo, rest, home field, and quarterback form. Margin and total come from those two scores. A separate calibration turns margin into win probability. Every coefficient is trained on completed prior seasons only."
      />
      <p className="text-xs tracking-wide text-uncertainty uppercase">
        {file.modelVersion} · updated {formatGenerated(file.generatedAt)} · home field{" "}
        {formatSigned(file.homeField)}
      </p>

      <div className="max-w-2xl space-y-6 text-sm leading-6">
        <Section title="Past games only">
          The entire week is forecast before any result from that week updates a rating, so a Sunday result cannot leak into another game on the same slate. Scoring form and Elo carry into a new season at reduced strength. The score and probability coefficients are then fit once using completed prior seasons and held fixed for the season being forecast.
        </Section>
        <Section title="The score">
          Two ridge regressions estimate home points and away points. Each uses the team’s recent scoring, the opponent’s recent points allowed, Elo, rest, home field, and both recent starters’ passing form. Margin is home points minus away points, and the total is their sum. The published score is each fitted mean, rounded; accuracy uses the unrounded margin, total, and team scores. This direct score model replaced a single margin regression and a single total regression because it lowered held-out error on the margin, the total, and both team scores.
        </Section>
        <Section title="Locked forecasts">
          A week becomes locked when it is the current slate. Later refreshes add the scoreboard but keep its score, probability, players, context, and comparison line unchanged. Future weeks are provisional. Older reconstructed games are labeled as backtests rather than pretending they were published live.
        </Section>
        <Section title="Home field">
          The home-field row is the extra margin for a true home game beyond the league baseline, currently {formatSigned(file.homeField)} points. Most of the ordinary home advantage stays in the baseline, because nearly every training game is at home and the penalty leaves that average in the intercept. Neutral sites omit the home-field row and still receive the baseline. Both numbers are fit from completed prior seasons.
        </Section>
        <Section title="Quarterback">
          The most recent starter has a passing-EPA rating with 100 plays of league-average prior weight and offseason regression. Only information through the previous week is used. That rating enters both score equations, so it can move either team’s points, the margin, and the total. If that starter is out or doubtful before an upcoming game, the separate availability override docks the team 3.5 points. Historical backtests do not use week-level injury rows because nflverse does not provide a reliable pre-kickoff timestamp for this feed.
        </Section>
        <Section title="Where the score lands">
          A smooth curve treats a 3-point game like a 4-point game. NFL finals do not. Field goals are worth 3 and a touchdown with the extra point is worth 7, so margins of 3, 7, 6, 10, 14, and 4 carry more games than the numbers beside them. Yardline keeps the two team means from the score model, then weights finals from earlier seasons by how close their margin and total were to this forecast. Those finals stay whole scores, so a three-point game is not rounded into a four. The likely final and the likely margin come from that same cloud. The calibrated win probability is unchanged. The cloud is not a price, and it is not a suggestion to bet a number.
        </Section>
        <Section title="Win probability">
          A regularized logistic calibration learns how often each fitted margin became a home win in completed prior seasons. Its training margins are out-of-season home-score minus away-score predictions, not in-sample fitted values. Home win, away win, and tie always sum to 100%. If the rounded score is level, the card flags likely overtime instead of inventing an exact overtime score. About six percent of regular-season overtimes still end tied.
        </Section>
        <Section title="Player lines">
          Quarterback attempts and running back carries use the last eight games, with a three-game half-life so last week counts twice as much as a game from three weeks ago, then shrink toward a typical week. Yards are that volume times a shrunk per-play rate, multiplied by how many yards per play the opponent has allowed relative to the league. The bar around the median is the 80th percentile of earlier misses, fit before the season, not a fixed eight attempts or 70 yards. The previous line, last four games at equal weight and a fixed bar, is scored on the record beside this one. If the leader is out or doubtful, the line moves to the next player with enough recent work. Only an unavailable quarterback changes the team score, by 3.5 points. It is not a sportsbook prop and not a full player simulation.
        </Section>
        <Section title="What does not move the score">
          Raw team EPA, weather, roof, and travel across time zones are context in this version. Team EPA is worth zero points because adding it did not improve the held-out margin and win metrics; the separately tested quarterback-form feature does use passing EPA. An early East Coast body-clock spot, or wind at 20 mph or more, can show up as an X-factor, also worth zero, until that idea earns a backtest. If it is on the card and it is not in the adjustment list, it did not change the number.
        </Section>
        <Section title="The posted line">
          Spread, total, and the no-vig price from nflverse are stored beside the forecast so the record can be compared. They are not model inputs. They are not a live sportsbook. On the{" "}
          <Link href="/accuracy" className="text-forecast underline-offset-4 hover:underline">
            record
          </Link>{" "}
          win Brier, margin error, and total error all use exact paired cohorts. The posted line remains sharper on the current record. Yardline does not claim to beat the market.
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
