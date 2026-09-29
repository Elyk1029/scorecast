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
          <p className="font-display text-3xl tabular-nums text-uncertainty">
            {slice.marketBrier == null ? "No price" : slice.marketBrier.toFixed(3)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Posted-line Brier from the nflverse moneyline, vig removed. Lower is sharper. This is a comparison, not a claim.
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
  if (slice.marketBrier == null) {
    return `${coin} No posted-line prices were available to compare.`
  }
  return `${coin} The nflverse posted line is ${slice.marketBrier.toFixed(3)}. Yardline does not claim to beat the market.`
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
