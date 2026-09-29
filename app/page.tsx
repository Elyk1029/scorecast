import type { Metadata } from "next";
import { WeekBoard } from "@/components/week-board";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { findWeek, getSeason } from "@/lib/season";

export const metadata: Metadata = {
  title: "This week",
};

export default function HomePage() {
  const file = getSeason();
  const week = findWeek(file, file.current.season, file.current.week);
  if (!week) {
    return (
      <>
        <PageHeader
          eyebrow="This week"
          title="No current slate"
          lede="The forecast file does not have a current week yet."
        />
        <Card>
          <CardHeader>
            <CardTitle>Empty board</CardTitle>
            <CardDescription>Run the model to write data/season.json, then reload.</CardDescription>
          </CardHeader>
        </Card>
      </>
    );
  }

  return (
    <WeekBoard
      week={week}
      eyebrow="This week"
      lede="The weekly forecast, left where you can check it against the scoreboard. Amber is the model. Ice blue is the result, once the game is final."
    />
  );
}
