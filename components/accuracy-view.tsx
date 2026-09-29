"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatRate } from "@/lib/format"
import type { AccuracySlice } from "@/lib/types"

export function AccuracyView({
  overall,
  bySeason,
}: {
  overall: AccuracySlice
  bySeason: Record<string, AccuracySlice>
}) {
  const seasons = Object.keys(bySeason).sort()

  return (
    <Tabs defaultValue="overall">
      <div className="overflow-x-auto pb-1">
        <TabsList>
          <TabsTrigger value="overall">Overall</TabsTrigger>
          {seasons.map((season) => (
            <TabsTrigger key={season} value={season}>
              {season}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      <TabsContent value="overall" className="mt-4">
        <SliceView slice={overall} />
      </TabsContent>
      {seasons.map((season) => (
        <TabsContent key={season} value={season} className="mt-4">
          <SliceView slice={bySeason[season]} seasonLabel={season} />
        </TabsContent>
      ))}
    </Tabs>
  )
}

function SliceView({ slice, seasonLabel }: { slice: AccuracySlice; seasonLabel?: string }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Stat
          label="Straight-up"
          value={formatRate(slice.straightUp)}
          hint="Higher win-probability side. Ties count half."
        />
        <Stat
          label="Margin MAE"
          value={slice.marginMae.toFixed(2)}
          hint="Average absolute miss on the home margin, in points."
        />
        <Stat
          label="Total MAE"
          value={slice.totalMae.toFixed(2)}
          hint="Average absolute miss on the combined score."
        />
        <Stat
          label="Home score MAE"
          value={slice.homeScoreMae.toFixed(2)}
          hint="Average absolute miss on the home team’s points."
        />
        <Stat
          label="Away score MAE"
          value={slice.awayScoreMae.toFixed(2)}
          hint="Average absolute miss on the away team’s points."
        />
        <Stat
          label="Brier"
          value={slice.brier.toFixed(3)}
          hint="Squared error of the home win probability. A coin flip is 0.250."
        />
        <Stat
          label="Range coverage"
          value={formatRate(slice.withinRange)}
          hint="Both scores landed within 18 points of the forecast."
        />
        <Stat
          label="Games"
          value={String(slice.games)}
          hint={seasonLabel ? `${seasonLabel} regular season, walk-forward.` : "Every finished game in the record."}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Against the posted line</CardTitle>
          <CardDescription>{honesty(slice)}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-6 gap-y-2 text-sm">
            <span />
            <span className="text-xs text-muted-foreground">Market</span>
            <span className="text-xs text-muted-foreground">Yardline</span>
            <ComparisonRow
              label="Win Brier"
              market={slice.marketBrier}
              yardline={slice.pairedBrier}
              digits={3}
            />
            <ComparisonRow
              label="Margin MAE"
              market={slice.marketMarginMae}
              yardline={slice.pairedMarginMae}
              digits={2}
            />
            <ComparisonRow
              label="Total MAE"
              market={slice.marketTotalMae}
              yardline={slice.pairedTotalMae}
              digits={2}
            />
            <ComparisonRow
              label="Home score MAE"
              market={slice.marketHomeScoreMae}
              yardline={slice.pairedHomeScoreMae}
              digits={2}
            />
            <ComparisonRow
              label="Away score MAE"
              market={slice.marketAwayScoreMae}
              yardline={slice.pairedAwayScoreMae}
              digits={2}
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            nflverse moneyline, spread, and total with vig removed from the moneyline. Each row uses identical games: win {slice.marketGames}, spread {slice.spreadGames}, total {slice.totalGames}, team scores {slice.scoreGames}. Lower is sharper.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function honesty(slice: AccuracySlice) {
  const coin =
    slice.brier <= 0.25
      ? `Yardline’s Brier on this slice is ${slice.brier.toFixed(3)}, inside a coin flip at 0.250.`
      : `Yardline’s Brier on this slice is ${slice.brier.toFixed(3)}, the wrong side of a coin flip at 0.250.`
  if (slice.marketBrier == null || slice.pairedBrier == null) {
    return `${coin} No posted-line prices were available to compare.`
  }
  return `${coin} On the identical priced-game cohort, Yardline is ${slice.pairedBrier.toFixed(3)} and the posted line is ${slice.marketBrier.toFixed(3)}. Yardline does not claim to beat the market.`
}

function ComparisonRow({
  label,
  market,
  yardline,
  digits,
}: {
  label: string
  market: number | null
  yardline: number | null
  digits: number
}) {
  const format = (value: number | null) =>
    value == null ? "—" : value.toFixed(digits)
  return (
    <>
      <span>{label}</span>
      <span className="font-display text-2xl tabular-nums text-uncertainty">{format(market)}</span>
      <span className="font-display text-2xl tabular-nums text-forecast">{format(yardline)}</span>
    </>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="font-display text-3xl tracking-tight text-forecast">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  )
}
