import type { Game } from "@/lib/types"

/** Home-win chance used in the Brier score: a final tie counts half. */
export function homeEquivalent(game: Game) {
  return game.prediction.homeWinProb + 0.5 * game.prediction.tieProb
}

export type PriceSide = {
  gameId: string
  abbr: string
  model: number
  price: number
  gap: number
}

/**
 * The side this model rates above the stored no-vig moneyline.
 * The posted price is a comparison, not a model input.
 */
export function priceDisagreement(game: Game): PriceSide | null {
  if (game.postedHomeWinProb == null) return null
  const home = homeEquivalent(game)
  const edge = home - game.postedHomeWinProb
  if (edge >= 0) {
    return {
      gameId: game.id,
      abbr: game.home,
      model: home,
      price: game.postedHomeWinProb,
      gap: edge,
    }
  }
  return {
    gameId: game.id,
    abbr: game.away,
    model: 1 - home,
    price: 1 - game.postedHomeWinProb,
    gap: -edge,
  }
}

export type DisagreementRecord = {
  games: number
  hitRate: number
  priceRate: number
}

/**
 * How often the side rated above the no-vig price actually won.
 * A tie counts half, matching the price comparison.
 */
export function disagreementRecord(games: Game[], minGap: number): DisagreementRecord {
  let count = 0
  let hits = 0
  let prices = 0
  for (const game of games) {
    if (game.actual == null) continue
    const side = priceDisagreement(game)
    if (side == null || side.gap < minGap) continue
    const outcome = game.actual.margin > 0 ? 1 : game.actual.margin < 0 ? 0 : 0.5
    const hit = side.abbr === game.home ? outcome : 1 - outcome
    count += 1
    hits += hit
    prices += side.price
  }
  return {
    games: count,
    hitRate: count === 0 ? 0 : hits / count,
    priceRate: count === 0 ? 0 : prices / count,
  }
}

export function largestDisagreement(games: Game[]): PriceSide | null {
  let best: PriceSide | null = null
  for (const game of games) {
    const side = priceDisagreement(game)
    if (side == null) continue
    if (best == null || side.gap > best.gap) best = side
  }
  return best
}
