import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GameDetail } from "@/components/game-detail";
import { findGame, getSeason } from "@/lib/season";

export function generateStaticParams() {
  return getSeason().weeks.flatMap((week) => week.games.map((game) => ({ id: game.id })));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const game = findGame(getSeason(), id);
  if (!game) return { title: "Game" };
  return { title: `${game.away} at ${game.home}` };
}

export default async function GamePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const file = getSeason();
  const game = findGame(file, id);
  if (!game) notFound();
  return <GameDetail game={game} file={file} />;
}
