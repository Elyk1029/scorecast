export type Team = {
  abbr: string
  city: string
  name: string
  tz: number
}

export type Adjustment = {
  label: string
  points: number
  detail: string
}

export type XFactor = {
  label: string
  points: number
  detail: string
}

export type QuarterbackLine = {
  id: string
  name: string
  attempts: number
  attemptsLow?: number
  attemptsHigh?: number
  yards: number
  low: number
  high: number
}

export type RusherLine = {
  id: string
  name: string
  carries: number
  carriesLow?: number
  carriesHigh?: number
  yards: number
  low: number
  high: number
  position?: string
}

export type SidePlayers = {
  qb: QuarterbackLine | null
  rb: RusherLine | null
}

export type ActualQb = {
  attempts: number
  yards: number
}

export type ActualRb = {
  carries: number
  yards: number
}

export type ActualSide = {
  qb: ActualQb | null
  rb: ActualRb | null
}

export type Prediction = {
  homeScore: number
  awayScore: number
  homeWinProb: number
  tieProb: number
  overtime: boolean
  spreadHome: number
  total: number
  meanMargin?: number
  meanTotal?: number
  homeRange: [number, number]
  awayRange: [number, number]
  rawMargin: number
}

export type Actual = {
  homeScore: number
  awayScore: number
  margin: number
  total: number
  players: {
    home: ActualSide
    away: ActualSide
  }
}

export type Game = {
  id: string
  season: number
  week: number
  status: "upcoming" | "final" | string
  weekday: string | null
  date: string | null
  time: string | null
  home: string
  away: string
  stadium: string | null
  neutral: boolean
  roof: string | null
  temp: number | null
  wind: number | null
  prediction: Prediction
  players: {
    home: SidePlayers
    away: SidePlayers
  }
  actual: Actual | null
  adjustments: Adjustment[]
  context: string[]
  xfactor: XFactor | null
  postedSpreadHome: number | null
  postedTotal: number | null
  postedHomeWinProb: number | null
  forecastedAt: string | null
  forecastModelVersion: string
  locked: boolean
  recordKind: "published" | "backtest" | "provisional"
}

export type Week = {
  season: number
  week: number
  games: Game[]
}

export type AccuracySlice = {
  games: number
  straightUp: number
  marginMae: number
  totalMae: number
  brier: number
  withinRange: number
  marketBrier: number | null
  pairedBrier: number | null
  marketGames: number
  marketMarginMae: number | null
  pairedMarginMae: number | null
  spreadGames: number
  marketTotalMae: number | null
  pairedTotalMae: number | null
  totalGames: number
  homeScoreMae: number
  awayScoreMae: number
  marketHomeScoreMae: number | null
  pairedHomeScoreMae: number | null
  marketAwayScoreMae: number | null
  pairedAwayScoreMae: number | null
  scoreGames: number
  season?: number
  week?: number
}

export type PlayerLineAccuracy = {
  attemptsMae: number
  passYardsMae: number
  carriesMae: number
  rushYardsMae: number
  attemptsCoverage: number
  passYardsCoverage: number
  carriesCoverage: number
  rushYardsCoverage: number
  quarterbackGames: number
  rusherGames: number
}

export type PlayerLineComparison = {
  previous: PlayerLineAccuracy
  current: PlayerLineAccuracy
}

export type LearnedWeek = {
  season: number
  week: number
  homeField: number
  sentences: string[]
}

export type SeasonFile = {
  generatedAt: string
  modelVersion: string
  current: { season: number; week: number }
  homeField: number
  teams: Record<string, Team>
  weeks: Week[]
  accuracy: {
    overall: AccuracySlice
    bySeason: Record<string, AccuracySlice>
    weekly: AccuracySlice[]
  }
  playerLines: PlayerLineComparison
  learned: LearnedWeek[]
  notes: string[]
}
