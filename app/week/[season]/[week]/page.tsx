import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WeekBoard } from "@/components/week-board";
import { findWeek, getSeason } from "@/lib/season";

export function generateStaticParams() {
  return getSeason().weeks.map((week) => ({
    season: String(week.season),
    week: String(week.week),
  }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ season: string; week: string }>;
}): Promise<Metadata> {
  const { season, week } = await params;
  return { title: `${season} week ${week}` };
}

export default async function WeekPage({
  params,
}: {
  params: Promise<{ season: string; week: string }>;
}) {
  const { season, week } = await params;
  const file = getSeason();
  const slate = findWeek(file, Number(season), Number(week));
  if (!slate) notFound();

  const current = slate.season === file.current.season && slate.week === file.current.week;

  return (
    <WeekBoard
      week={slate}
      eyebrow={current ? "This week" : `${slate.season} archive`}
      lede={
        current
          ? "The current slate. Amber is still the forecast until the game is final."
          : slate.games.every((game) => game.recordKind === "backtest")
            ? "A walk-forward reconstruction: each game used only earlier weeks, but this number was not published live."
            : "An archived week. Locked forecasts stay unchanged after publication."
      }
    />
  );
}
