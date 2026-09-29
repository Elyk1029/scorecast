import Link from "next/link"
import { RangeBar, RangeLegend } from "@/components/range-bar"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatGenerated, formatPoints, formatSigned, formatTime, percent } from "@/lib/format"
import { marginMiss, sideResult, spreadText, teamName, totalMiss } from "@/lib/season"
import type { ActualSide, Game, QuarterbackLine, RusherLine, SeasonFile, SidePlayers } from "@/lib/types"
import { cn } from "cn"

export function GameDetail({ game, file }: { game: Game; file: SeasonFile }) {
  const final = game.status === "final" && game.actual != null
  const miss = marginMiss(game)
  const total = totalMiss(game)
  const result = sideResult(game)
  const away = teamName(file, game.away)
  const home = teamName(file, game.home)

  return (
    <article className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/week/${game.season}/${game.week}`}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          {game.season} week {game.week}
        </Link>
        <div className="flex gap-1.5">
          {game.neutral ? <Badge variant="outline">Neutral site</Badge> : null}
          <Badge variant="outline" className="border-forecast/40 text-forecast">
            {game.recordKind === "backtest"
              ? "Walk-forward backtest"
              : game.locked
                ? "Locked forecast"
                : "Provisional"}
          </Badge>
          <Badge
            variant="outline"
            className={final ? "border-actual/40 text-actual" : "border-uncertainty/50 text-uncertainty"}
          >
            {final ? "Final" : "Upcoming"}
          </Badge>
        </div>
      </div>

      <header className="space-y-2">
        <p className="text-xs font-medium tracking-[0.18em] text-forecast uppercase">
          {game.weekday} · {formatTime(game.time)}
        </p>
        <h1 className="font-display text-4xl leading-none tracking-tight sm:text-5xl">
          {file.teams[game.away]?.name ?? game.away} at {file.teams[game.home]?.name ?? game.home}
        </h1>
        <p className="text-sm text-muted-foreground">
          {away} @ {home}
          {game.stadium ? ` · ${game.stadium}` : ""}
        </p>
        <p className="text-xs tracking-wide text-uncertainty uppercase">
          {game.recordKind === "backtest"
            ? "Walk-forward backtest"
            : game.locked
              ? "Published forecast"
              : "Provisional forecast"}{" "}
          · {game.forecastModelVersion}
          {game.forecastedAt ? ` · locked ${formatGenerated(game.forecastedAt)}` : ""}
        </p>
      </header>

      <Card>
        <CardContent className="grid gap-6 sm:grid-cols-2">
          <ScoreBlock
            abbr={game.away}
            name={away}
            predicted={game.prediction.awayScore}
            actual={game.actual?.awayScore ?? null}
            won={game.actual != null && game.actual.margin < 0}
            tied={game.actual?.margin === 0}
          />
          <ScoreBlock
            abbr={game.home}
            name={home}
            predicted={game.prediction.homeScore}
            actual={game.actual?.homeScore ?? null}
            won={game.actual != null && game.actual.margin > 0}
            tied={game.actual?.margin === 0}
          />
        </CardContent>
      </Card>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Calibrated chance" value={`${percent(favoriteProb(game))} ${favoriteAbbr(game)}`} />
        <Metric label="Model spread" value={spreadText(game)} />
        <Metric label="Model total" value={formatPoints(game.prediction.total)} />
        <Metric
          label="Score band"
          value={`${game.prediction.awayRange[0]}–${game.prediction.awayRange[1]} @ ${game.prediction.homeRange[0]}–${game.prediction.homeRange[1]}`}
        />
      </dl>

      <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
        {percent(game.prediction.homeWinProb)} is the calibrated chance {home} wins;{" "}
        {percent(awayWinProb(game))} is the chance {away} wins
        {game.prediction.tieProb > 0
          ? `; ${percent(game.prediction.tieProb)} is the final-tie chance`
          : ""}.
        {game.prediction.overtime
          ? " The rounded score is level, so overtime is likely; the probabilities already account for it."
          : ""}{" "}
        The spread uses the unrounded expected margin. Probability is pulled toward 50%
        because raw margins have been too sharp in the backtest.
      </p>

      {final && miss != null ? (
        <p className="text-sm text-actual">
          {miss === 0 ? "The margin landed on the forecast." : `Margin miss ${miss} points.`}
          {total != null ? ` Total miss ${formatPoints(total)}.` : ""}
          {result === "hit" ? " The higher-probability side won." : null}
          {result === "miss" ? " The higher-probability side lost." : null}
          {result === "tie" ? " The game tied." : null}
        </p>
      ) : (
        <p className="text-sm text-uncertainty">
          Upcoming. The ice-blue score and the actual tick on each player bar show up after the game is final.
        </p>
      )}

      <div className="md:hidden">
        <Tabs defaultValue="sheet">
          <TabsList className="w-full">
            <TabsTrigger value="sheet">Sheet</TabsTrigger>
            <TabsTrigger value="players">Players</TabsTrigger>
          </TabsList>
          <TabsContent value="sheet" className="mt-4">
            <ForecastSheet game={game} />
          </TabsContent>
          <TabsContent value="players" className="mt-4">
            <PlayerSheet game={game} file={file} />
          </TabsContent>
        </Tabs>
      </div>

      <div className="hidden gap-6 md:grid md:grid-cols-2">
        <ForecastSheet game={game} />
        <PlayerSheet game={game} file={file} />
      </div>
    </article>
  )
}

function favoriteProb(game: Game) {
  return Math.max(game.prediction.homeWinProb, awayWinProb(game))
}

function favoriteAbbr(game: Game) {
  return game.prediction.homeWinProb >= awayWinProb(game) ? game.home : game.away
}

function awayWinProb(game: Game) {
  return 1 - game.prediction.homeWinProb - game.prediction.tieProb
}

function ScoreBlock({
  abbr,
  name,
  predicted,
  actual,
  won,
  tied,
}: {
  abbr: string
  name: string
  predicted: number
  actual: number | null
  won: boolean
  tied: boolean
}) {
  return (
    <div>
      <p className="font-display text-sm tracking-[0.16em] text-muted-foreground">{abbr}</p>
      <p className="truncate text-sm">{name}</p>
      {actual != null ? (
        <p
          className={cn(
            "mt-2 font-display text-6xl leading-none tabular-nums",
            won || tied ? "text-actual" : "text-actual/55",
          )}
        >
          {actual}
        </p>
      ) : (
        <p className="mt-2 font-display text-6xl leading-none tabular-nums text-forecast">{predicted}</p>
      )}
      <p className="mt-2 text-sm tabular-nums text-forecast">
        {actual != null ? `Model ${predicted}` : "Expected score"}
      </p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-card px-3 py-3 ring-1 ring-foreground/10">
      <dt className="text-[11px] tracking-wide text-uncertainty uppercase">{label}</dt>
      <dd className="mt-1 font-display text-lg leading-tight tabular-nums text-forecast">{value}</dd>
    </div>
  )
}

function ForecastSheet({ game }: { game: Game }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Adjustments</CardTitle>
          <CardDescription>Points added to the home margin before the score is rounded.</CardDescription>
        </CardHeader>
        <CardContent>
          {game.adjustments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No adjustment rows on this game.</p>
          ) : (
            <ul>
              {game.adjustments.map((row, index) => (
                <li key={row.label}>
                  {index > 0 ? <Separator className="my-3" /> : null}
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium">{row.label}</p>
                      <p className="text-sm leading-5 text-muted-foreground">{row.detail}</p>
                    </div>
                    <p className="font-display text-2xl tabular-nums text-forecast">
                      {formatSigned(row.points)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Context</CardTitle>
          <CardDescription>Shown so you can see it. Worth zero points in this version.</CardDescription>
        </CardHeader>
        <CardContent>
          {game.context.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing extra on the sheet. Weather and travel show up here when the file has them, and they do not move the score.
            </p>
          ) : (
            <ul className="space-y-2 text-sm leading-6">
              {game.context.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {game.xfactor ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-3">
              {game.xfactor.label}
              <Badge variant="outline" className="border-uncertainty/50 text-uncertainty">
                0 pts
              </Badge>
            </CardTitle>
            <CardDescription>{game.xfactor.detail}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>nflverse comparison</CardTitle>
          <CardDescription>
            A posted line stored for the record. Not a live sportsbook and not a model input.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {game.postedSpreadHome == null && game.postedTotal == null ? (
            <p className="text-muted-foreground">No posted line in the nflverse file for this game.</p>
          ) : (
            <>
              <p>
                Home spread{" "}
                <span className="font-display text-lg text-uncertainty">
                  {game.postedSpreadHome == null ? "—" : formatSigned(game.postedSpreadHome)}
                </span>
                {" · "}
                Total{" "}
                <span className="font-display text-lg text-uncertainty">
                  {game.postedTotal == null ? "—" : formatPoints(game.postedTotal)}
                </span>
              </p>
              <p className="text-muted-foreground">
                {game.postedHomeWinProb == null
                  ? "No no-vig home price in the file."
                  : `No-vig home price ${percent(game.postedHomeWinProb)}. Negative spread means the home team was favored in that file.`}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function PlayerSheet({ game, file }: { game: Game; file: SeasonFile }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Player lines</CardTitle>
        <CardDescription>
          Volume first. The slate bar is a fixed window around the median, the amber tick is the median, and the ice tick is the actual when the game is final.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <RangeLegend />
        <SideBlock
          title={file.teams[game.away]?.name ?? game.away}
          projected={game.players.away}
          actual={game.actual?.players.away ?? null}
          final={game.status === "final"}
        />
        <Separator />
        <SideBlock
          title={file.teams[game.home]?.name ?? game.home}
          projected={game.players.home}
          actual={game.actual?.players.home ?? null}
          final={game.status === "final"}
        />
      </CardContent>
    </Card>
  )
}

function SideBlock({
  title,
  projected,
  actual,
  final,
}: {
  title: string
  projected: SidePlayers
  actual: ActualSide | null
  final: boolean
}) {
  return (
    <section className="space-y-4">
      <h3 className="font-display text-2xl tracking-wide">{title}</h3>
      {projected.qb ? (
        <QuarterbackBlock
          player={projected.qb}
          actual={actual?.qb ?? null}
          final={final}
        />
      ) : (
        <p className="text-sm text-muted-foreground">
          No quarterback line. Recent pass volume was too thin to publish one.
        </p>
      )}
      {projected.rb ? (
        <RusherBlock player={projected.rb} actual={actual?.rb ?? null} final={final} />
      ) : (
        <p className="text-sm text-muted-foreground">
          No running back line. Recent carry volume was too thin to publish one.
        </p>
      )}
    </section>
  )
}

function QuarterbackBlock({
  player,
  actual,
  final,
}: {
  player: QuarterbackLine
  actual: { attempts: number; yards: number } | null
  final: boolean
}) {
  const low = player.attemptsLow ?? Math.max(0, player.attempts - 8)
  const high = player.attemptsHigh ?? player.attempts + 8
  return (
    <div className="space-y-3">
      <p className="text-sm">
        <span className="font-medium">{player.name}</span>
        <span className="text-muted-foreground"> · quarterback</span>
      </p>
      {final && !actual ? (
        <p className="text-xs text-uncertainty">No final passing line for this player in the file.</p>
      ) : null}
      <RangeBar label="Attempts" low={low} high={high} median={player.attempts} actual={actual?.attempts} digits={1} />
      <RangeBar label="Passing yards" low={player.low} high={player.high} median={player.yards} actual={actual?.yards} />
    </div>
  )
}

function RusherBlock({
  player,
  actual,
  final,
}: {
  player: RusherLine
  actual: { carries: number; yards: number } | null
  final: boolean
}) {
  const low = player.carriesLow ?? Math.max(0, player.carries - 5)
  const high = player.carriesHigh ?? player.carries + 5
  return (
    <div className="space-y-3">
      <p className="text-sm">
        <span className="font-medium">{player.name}</span>
        <span className="text-muted-foreground"> · ball carrier</span>
      </p>
      {final && !actual ? (
        <p className="text-xs text-uncertainty">No final rushing line for this player in the file.</p>
      ) : null}
      <RangeBar label="Carries" low={low} high={high} median={player.carries} actual={actual?.carries} digits={1} />
      <RangeBar label="Rushing yards" low={player.low} high={player.high} median={player.yards} actual={actual?.yards} />
    </div>
  )
}
