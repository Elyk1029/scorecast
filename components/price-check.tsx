import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { formatRate, percent } from "@/lib/format"
import {
  disagreementRecord,
  largestDisagreement,
  priceDisagreement,
  type DisagreementRecord,
} from "@/lib/price-check"
import { teamName } from "@/lib/season"
import type { Game, SeasonFile } from "@/lib/types"

function finishedGames(file: SeasonFile) {
  return file.weeks.flatMap((week) => week.games).filter((game) => game.actual != null)
}

function recordSentence(record: DisagreementRecord, minGap: number) {
  return `A gap of at least ${Math.round(minGap * 100)} points, ${record.games.toLocaleString()} games: that side happened ${formatRate(record.hitRate)} of the time, and the price said ${formatRate(record.priceRate)}.`
}

export function SlatePriceCheck({ week, file }: { week: { games: Game[] }; file: SeasonFile }) {
  const largest = largestDisagreement(week.games)
  if (largest == null) return null
  const finished = finishedGames(file)
  const modest = disagreementRecord(finished, 0.03)
  const large = disagreementRecord(finished, 0.08)
  const name = teamName(file, largest.abbr)

  return (
    <Card>
      <CardHeader>
        <CardTitle>No recommended play</CardTitle>
        <CardDescription>
          The research rule flags the side this model rates above the no-vig price. On the finished games that rule does not clear the posted price, so nothing here is marked as a better chance than the odds.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-6">
        <p>
          Largest gap this week:{" "}
          <Link href={`/game/${largest.gameId}`} className="text-forecast underline-offset-4 hover:underline">
            {name}
          </Link>
          . Model {percent(largest.model)}. Posted price {percent(largest.price)}.
        </p>
        <p className="text-muted-foreground">
          {recordSentence(modest, 0.03)} {recordSentence(large, 0.08)} The bigger disagreements are the worse ones. The posted price stays the sharper number for what is more likely to happen.
        </p>
      </CardContent>
    </Card>
  )
}

export function GamePriceLine({ game, file }: { game: Game; file: SeasonFile }) {
  const side = priceDisagreement(game)
  if (side == null) return null
  const name = teamName(file, side.abbr)
  const finished = finishedGames(file)
  const bucket = side.gap >= 0.08 ? 0.08 : 0.03
  const record = disagreementRecord(finished, bucket)
  const ahead = record.hitRate > record.priceRate

  return (
    <p className="text-muted-foreground">
      Model rates {name} at {percent(side.model)}. The no-vig price is {percent(side.price)}.{" "}
      {side.gap < 0.03
        ? "The two are within 3 points."
        : `${recordSentence(record, bucket)} ${ahead ? "The difference is inside the game-to-game noise." : "That side has landed less often than the price."}`}{" "}
      Not a recommended play.
    </p>
  )
}

export function PriceRecordCard({ file }: { file: SeasonFile }) {
  const finished = finishedGames(file)
  const modest = disagreementRecord(finished, 0.03)
  const large = disagreementRecord(finished, 0.08)
  if (modest.games === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Against the posted price</CardTitle>
        <CardDescription>
          Taking the side Yardline rates above the no-vig moneyline. A tie counts half. This is the research comparison, and it is not a recommended play.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm leading-6 text-muted-foreground">
        <p>{recordSentence(modest, 0.03)}</p>
        <p>{recordSentence(large, 0.08)}</p>
        <p>
          Spread and total sides taken from the score cloud were also checked. Covers landed about half the time, totals under half. A −110 price needs about 52.4% to break even. Those rules are not on the card.
        </p>
      </CardContent>
    </Card>
  )
}
