import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { formatPoints, formatTime, percent } from "@/lib/format"
import {
  contextLine,
  favoriteSide,
  marginMiss,
  sideResult,
  spreadText,
} from "@/lib/season"
import type { Game, Team } from "@/lib/types"
import { cn } from "cn"

export function GameCard({ game, teams }: { game: Game; teams: Record<string, Team> }) {
  const final = game.status === "final" && game.actual != null
  const pick = favoriteSide(game)
  const miss = marginMiss(game)
  const result = sideResult(game)

  return (
    <Link
      href={`/game/${game.id}`}
      className="group block rounded-xl focus-visible:ring-2 focus-visible:ring-forecast focus-visible:outline-none"
    >
      <Card className="h-full transition group-hover:ring-forecast/50">
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-xs tracking-wide text-muted-foreground uppercase">
              {formatTime(game.time)}
            </p>
            <div className="flex shrink-0 gap-1.5">
              {game.neutral ? <Badge variant="outline">Neutral</Badge> : null}
              <Badge
                variant="outline"
                className={
                  final
                    ? "border-actual/40 text-actual"
                    : "border-uncertainty/50 text-uncertainty"
                }
              >
                {final ? "Final" : "Upcoming"}
              </Badge>
            </div>
          </div>

          <div className="space-y-1.5">
            <TeamLine game={game} teams={teams} side="away" />
            <p className="pl-0.5 font-display text-sm tracking-[0.22em] text-forecast/80">@</p>
            <TeamLine game={game} teams={teams} side="home" />
          </div>

          <dl className="grid grid-cols-3 gap-2 border-t border-white/10 pt-3 text-center">
            <div>
              <dt className="text-[11px] tracking-wide text-uncertainty uppercase">Chance</dt>
              <dd className="font-display text-base tabular-nums text-forecast">
                {percent(pick.prob)} {pick.abbr}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] tracking-wide text-uncertainty uppercase">Spread</dt>
              <dd className="font-display text-base tabular-nums text-forecast">{spreadText(game)}</dd>
            </div>
            <div>
              <dt className="text-[11px] tracking-wide text-uncertainty uppercase">Total</dt>
              <dd className="font-display text-base tabular-nums text-forecast">
                {formatPoints(game.prediction.total)}
              </dd>
            </div>
          </dl>

          {final && miss != null ? (
            <p className="text-sm text-actual">
              {miss === 0
                ? "Margin landed on the forecast."
                : `Margin miss ${miss} ${miss === 1 ? "point" : "points"}.`}
              {result === "hit" ? " Side hit." : null}
              {result === "miss" ? " Side miss." : null}
              {result === "tie" ? " Game tied." : null}
            </p>
          ) : null}

          <p className="line-clamp-2 text-sm leading-5 text-muted-foreground">{contextLine(game)}</p>
        </CardContent>
      </Card>
    </Link>
  )
}

function TeamLine({
  game,
  teams,
  side,
}: {
  game: Game
  teams: Record<string, Team>
  side: "home" | "away"
}) {
  const abbr = side === "home" ? game.home : game.away
  const team = teams[abbr]
  const predicted = side === "home" ? game.prediction.homeScore : game.prediction.awayScore
  const actualScore = game.actual
    ? side === "home"
      ? game.actual.homeScore
      : game.actual.awayScore
    : null
  const won =
    game.actual != null &&
    actualScore != null &&
    (side === "home" ? game.actual.margin > 0 : game.actual.margin < 0)

  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-2xl tracking-wide">{abbr}</span>
          <span className="truncate text-sm text-muted-foreground">{team?.name ?? abbr}</span>
        </div>
      </div>
      {actualScore != null ? (
        <div className="text-right">
          <p
            className={cn(
              "font-display text-4xl leading-none tabular-nums",
              won || game.actual?.margin === 0 ? "text-actual" : "text-actual/55",
            )}
          >
            {actualScore}
          </p>
          <p className="mt-1 text-xs tabular-nums text-forecast">model {predicted}</p>
        </div>
      ) : (
        <p className="font-display text-4xl leading-none tabular-nums text-forecast">{predicted}</p>
      )}
    </div>
  )
}
