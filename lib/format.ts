export function formatDate(date: string | null, weekday: string | null) {
  if (!date) return weekday ?? "Date TBD"
  const [year, month, day] = date.split("-").map(Number)
  if (!year || !month || !day) return weekday ?? date
  const stamp = new Date(Date.UTC(year, month - 1, day))
  const monthName = new Intl.DateTimeFormat("en-US", {
    month: "short",
    timeZone: "UTC",
  }).format(stamp)
  return `${weekday ? `${weekday} ` : ""}${monthName} ${day}`
}

export function formatTime(time: string | null) {
  if (!time) return "Time TBD"
  const [hourText, minuteText] = time.split(":")
  const hour = Number(hourText)
  const minute = Number(minuteText)
  if (Number.isNaN(hour) || Number.isNaN(minute)) return time
  const suffix = hour >= 12 ? "PM" : "AM"
  const hour12 = hour % 12 || 12
  return `${hour12}:${String(minute).padStart(2, "0")} ${suffix} ET`
}

export function formatGenerated(iso: string) {
  const stamp = new Date(iso)
  if (Number.isNaN(stamp.getTime())) return iso
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(stamp)
}

export function formatPoints(value: number) {
  const rounded = Math.round(value * 10) / 10
  return Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)
}

export function formatSigned(value: number, digits = 1) {
  const absolute = Math.abs(value).toFixed(digits)
  if (value > 0) return `+${absolute}`
  if (value < 0) return `−${absolute}`
  return Number(0).toFixed(digits)
}

export function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function formatRate(value: number) {
  return `${(value * 100).toFixed(1)}%`
}
