import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { WeekBoard } from "@/components/week-board";
import { getSeason, previousWeek } from "@/lib/season";

export const metadata: Metadata = {
  title: "Last week",
};

export default function LastPage() {
  const file = getSeason();
  const week = previousWeek(file);
  if (!week) {
    return (
      <>
        <PageHeader
          eyebrow="Last week"
          title="Nothing behind this week"
          lede="The board starts on the current slate, so there is no prior week to check yet."
        />
        <Card>
          <CardHeader>
            <CardTitle>No previous week</CardTitle>
            <CardDescription>
              When a week finishes, it stays here with the forecast that was made before the games.
            </CardDescription>
          </CardHeader>
        </Card>
      </>
    );
  }

  return (
    <WeekBoard
      week={week}
      eyebrow="Last week"
      lede="The forecast from the previous week, still sitting next to the scoreboard. Use it to see the miss, not to rewrite the number."
    />
  );
}
