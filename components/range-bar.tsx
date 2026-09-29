function formatStat(value: number, digits: number) {
  if (digits === 0) return String(Math.round(value))
  return value.toFixed(1)
}

export function RangeBar({
  label,
  low,
  high,
  median,
  actual,
  digits = 0,
}: {
  label: string
  low: number
  high: number
  median: number
  actual?: number | null
  digits?: number
}) {
  const points = [low, high, median]
  if (actual != null) points.push(actual)
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const pad = span * 0.08
  const start = min - pad
  const end = max + pad
  const pos = (value: number) => ((value - start) / (end - start)) * 100
  const bandLeft = pos(Math.min(low, high))
  const bandWidth = Math.max(Math.abs(pos(high) - pos(low)), 2)

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="font-display text-lg leading-none tabular-nums text-forecast">
          {formatStat(median, digits)}
        </span>
      </div>
      <div className="relative h-8" role="img" aria-label={ariaLabel(label, low, high, median, actual, digits)}>
        <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-white/10" />
        <div
          className="absolute top-3 h-2 rounded-full bg-uncertainty/80"
          style={{ left: `${bandLeft}%`, width: `${bandWidth}%` }}
        />
        <span
          className="absolute top-1 h-6 w-0.5 -translate-x-1/2 rounded-full bg-forecast"
          style={{ left: `${pos(median)}%` }}
        />
        {actual != null ? (
          <span
            className="absolute top-0 h-8 w-1 -translate-x-1/2 rounded-full bg-actual shadow-[0_0_0_2px_var(--background)]"
            style={{ left: `${pos(actual)}%` }}
          />
        ) : null}
      </div>
      <div className="mt-1 flex justify-between text-[11px] tabular-nums text-uncertainty">
        <span>{formatStat(low, digits)}</span>
        <span>{formatStat(high, digits)}</span>
      </div>
      {actual != null ? (
        <p className="mt-1 text-[11px] text-actual">Actual {formatStat(actual, digits === 0 ? 0 : digits)}</p>
      ) : null}
    </div>
  )
}

function ariaLabel(
  label: string,
  low: number,
  high: number,
  median: number,
  actual: number | null | undefined,
  digits: number,
) {
  const base = `${label} low ${formatStat(low, digits)}, median ${formatStat(median, digits)}, high ${formatStat(high, digits)}`
  if (actual == null) return base
  return `${base}, actual ${formatStat(actual, digits === 0 ? 0 : digits)}`
}

export function RangeLegend() {
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
      <span className="text-uncertainty">Slate band · usual miss window</span>
      <span className="text-forecast">Amber tick · median</span>
      <span className="text-actual">Ice tick · actual</span>
    </p>
  )
}
