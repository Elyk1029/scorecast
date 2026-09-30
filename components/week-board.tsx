import Link from "next/link"
import { GameCard } from "@/components/game-card"
import { SlatePriceCheck } from "@/components/price-check"
import { PageHeader } from "@/components/page-header"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate, formatSigned } from "@/lib/format"
import { adjacentWeeks, gamesByDate, getSeason } from "@/lib/season"
import type { Week } from "@/lib/types"
import { cn } from "cn"

export function WeekBoard({
  week,
  eyebrow,
  lede,
}: {
  week: Week
  eyebrow: string
  lede: string
}) {
  const file = getSeason()
  const { prev, next } = adjacentWeeks(file, week.season, week.week)
  const groups = gamesByDate(week.games)
  const finals = week.games.filter((game) => game.status === "final").length
  const stateLine =
    week.games.length === 0
      ? "No games in the file."
      : finals === 0
        ? "None of these are final. The amber numbers are still the forecast."
        : finals === week.games.length
          ? "Every game is final. Ice blue is the scoreboard. Amber is what Yardline had."
          : `${finals} of ${week.games.length} are final. The rest are still the forecast.`

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={eyebrow} title={`Week ${week.week}`} lede={lede} />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1 text-sm text-muted-foreground">
          <p>
            {week.season} regular season · {week.games.length}{" "}
            {week.games.length === 1 ? "game" : "games"}
          </p>
          <p>{stateLine}</p>
          <p className="text-xs">
            Home field {formatSigned(file.homeField)} ·{" "}
            <span className="text-forecast">amber forecast</span>
            {" · "}
            <span className="text-actual">ice actual</span>
            {" · "}
            <span className="text-uncertainty">slate uncertainty</span>
          </p>
        </div>
        <div className="flex gap-2">
          {prev ? (
            <Link
              href={`/week/${prev.season}/${prev.week}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              {prev.season === week.season ? `Week ${prev.week}` : `${prev.season} W${prev.week}`}
            </Link>
          ) : (
            <span className="self-center text-xs text-muted-foreground">Start of the board</span>
          )}
          {next ? (
            <Link
              href={`/week/${next.season}/${next.week}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              {next.season === week.season ? `Week ${next.week}` : `${next.season} W${next.week}`}
            </Link>
          ) : (
            <span className="self-center text-xs text-muted-foreground">End of the board</span>
          )}
        </div>
      </div>

      <SlatePriceCheck week={week} file={file} />

      {week.games.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No games this week</CardTitle>
            <CardDescription>
              The regular-season file has an empty slate for week {week.week}.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="space-y-8">
          {groups.map((group) => (
            <section key={group.key} className="space-y-3">
              <h2 className="font-display text-2xl tracking-wide">
                {formatDate(group.games[0]?.date ?? null, group.games[0]?.weekday ?? null)}
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {group.games.map((game) => (
                  <GameCard key={game.id} game={game} teams={file.teams} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
