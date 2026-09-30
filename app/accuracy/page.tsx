import type { Metadata } from "next";
import { AccuracyView, PlayerLineComparisonCard } from "@/components/accuracy-view";
import { PriceRecordCard } from "@/components/price-check";
import { PageHeader } from "@/components/page-header";
import { getSeason } from "@/lib/season";

export const metadata: Metadata = {
  title: "Record",
};

export default function AccuracyPage() {
  const file = getSeason();
  const overall = file.accuracy.overall;
  const backtestGames = file.weeks.flatMap((week) => week.games).filter(
    (game) => game.status === "final" && game.recordKind === "backtest",
  ).length;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Record"
        title="Checked, then updated"
        lede={`Each game was scored with ratings from earlier weeks and coefficients from earlier seasons. ${overall.games} finished games are in the inspectable record, beginning in 2024; earlier seasons train and warm up the model but are not counted. Straight-up ${(overall.straightUp * 100).toFixed(1)}%, margin MAE ${overall.marginMae.toFixed(2)}, Brier ${overall.brier.toFixed(3)}.`}
      />
      <AccuracyView overall={file.accuracy.overall} bySeason={file.accuracy.bySeason} />
      <PlayerLineComparisonCard lines={file.playerLines} />
      <PriceRecordCard file={file} />
      <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
        A coin flip on this Brier is 0.250. The posted-line number, when the file has a price, is the no-vig nflverse moneyline. It has been sharper than Yardline. That comparison is here so the record stays honest. It is not a claim that the model beats the market.
        {backtestGames > 0
          ? ` ${backtestGames} games are labeled walk-forward backtests rather than live-published forecasts.`
          : ""}
      </p>
    </div>
  );
}
