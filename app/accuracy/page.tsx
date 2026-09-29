import type { Metadata } from "next";
import { AccuracyView } from "@/components/accuracy-view";
import { PageHeader } from "@/components/page-header";
import { getSeason } from "@/lib/season";

export const metadata: Metadata = {
  title: "Record",
};

export default function AccuracyPage() {
  const file = getSeason();
  const overall = file.accuracy.overall;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Record"
        title="Checked, then updated"
        lede={`Each game was scored with ratings from games already played. ${overall.games} finished games are in the record, including 2023 as the warm-up season. The board itself starts in 2024. Straight-up ${(overall.straightUp * 100).toFixed(1)}%, margin MAE ${overall.marginMae.toFixed(2)}, Brier ${overall.brier.toFixed(3)}.`}
      />
      <AccuracyView overall={file.accuracy.overall} bySeason={file.accuracy.bySeason} />
      <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
        A coin flip on this Brier is 0.250. The posted-line number, when the file has a price, is the no-vig nflverse moneyline. It has been sharper than Yardline. That comparison is here so the record stays honest. It is not a claim that the model beats the market.
      </p>
    </div>
  );
}
