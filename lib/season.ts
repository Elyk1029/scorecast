import { formatSigned } from "@/lib/format"
import data from "@/lib/season-data"
import type { Game, SeasonFile, Week } from "@/lib/types"

export function getSeason(): SeasonFile {
  return data
}

export function findWeek(file: SeasonFile, season: number, week: number) {
  return file.weeks.find((item) => item.season === season && item.week === week)
}

export function findGame(file: SeasonFile, id: string) {
  for (const week of file.weeks) {
    const game = week.games.find((item) => item.id === id)
    if (game) return game
  }
  return undefined
}

export function adjacentWeeks(file: SeasonFile, season: number, week: number) {
  const index = file.weeks.findIndex(
    (item) => item.season === season && item.week === week,
  )
  return {
    prev: index > 0 ? file.weeks[index - 1] : null,
    next: index >= 0 && index < file.weeks.length - 1 ? file.weeks[index + 1] : null,
  }
}

export function previousWeek(file: SeasonFile): Week | null {
  const index = file.weeks.findIndex(
    (item) => item.season === file.current.season && item.week === file.current.week,
  )
  if (index <= 0) return null
  return file.weeks[index - 1]
}

export function gamesByDate(games: Game[]) {
  const groups: { key: string; games: Game[] }[] = []
  for (const game of games) {
    const key = game.date ?? game.weekday ?? "tbd"
    const last = groups.at(-1)
    if (!last || last.key !== key) groups.push({ key, games: [game] })
    else last.games.push(game)
  }
  return groups
}

export function contextLine(game: Game) {
  if (game.context[0]) return game.context[0]
  const field = game.adjustments.find((item) => item.label === "Home field")
  if (field) return `Home field ${formatSigned(field.points)}.`
  return game.adjustments[0]?.detail ?? "Built from games already played."
}

export function sideResult(game: Game): "hit" | "miss" | "tie" | null {
  if (!game.actual) return null
  if (game.actual.margin === 0) return "tie"
  const pickedHome = game.prediction.homeWinProb >= 0.5
  const homeWon = game.actual.margin > 0
  return pickedHome === homeWon ? "hit" : "miss"
}

export function marginMiss(game: Game) {
  if (!game.actual) return null
  const predicted = game.prediction.homeScore - game.prediction.awayScore
  return Math.abs(game.actual.margin - predicted)
}

export function totalMiss(game: Game) {
  if (!game.actual) return null
  return Math.round(Math.abs(game.actual.total - game.prediction.total) * 10) / 10
}

export function teamName(file: SeasonFile, abbr: string) {
  const team = file.teams[abbr]
  if (!team) return abbr
  return `${team.city} ${team.name}`
}

export function spreadText(game: Game) {
  const line = game.prediction.spreadHome
  if (line === 0) return "Pick"
  const homeFavored = line < 0
  const abbr = homeFavored ? game.home : game.away
  const magnitude = Math.abs(line)
  const shown = Number.isInteger(magnitude) ? magnitude.toFixed(0) : magnitude.toFixed(1)
  return `${abbr} −${shown}`
}

export function favoriteSide(game: Game) {
  const margin = game.prediction.homeScore - game.prediction.awayScore
  const even = Math.abs(game.prediction.homeWinProb - 0.5) < 0.0005
  const home = even ? margin >= 0 : game.prediction.homeWinProb >= 0.5
  return {
    abbr: home ? game.home : game.away,
    prob: home ? game.prediction.homeWinProb : 1 - game.prediction.homeWinProb,
  }
}
