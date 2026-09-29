"use client"

import { BookOpen, CalendarCheck, CalendarDays, ChartColumn, Sparkles } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "cn"

const items = [
  { href: "/", label: "This week", icon: CalendarDays, key: "current" },
  { href: "/last", label: "Last week", icon: CalendarCheck, key: "last" },
  { href: "/learned", label: "Learned", icon: Sparkles, key: "learned" },
  { href: "/accuracy", label: "Record", icon: ChartColumn, key: "record" },
  { href: "/method", label: "Method", icon: BookOpen, key: "method" },
] as const

export function BottomNav({
  currentPath,
  lastPath,
}: {
  currentPath: string
  lastPath: string | null
}) {
  const pathname = usePathname()

  function active(key: (typeof items)[number]["key"], href: string) {
    if (key === "current") return pathname === "/" || pathname === currentPath
    if (key === "last") return pathname === "/last" || (lastPath != null && pathname === lastPath)
    return pathname === href
  }

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-forecast/20 bg-background/95 backdrop-blur">
      <p className="px-3 pt-2 text-center text-xs leading-4 text-muted-foreground">
        Research only. 21+ where wagering is legal. Not a bet recommendation.
      </p>
      <nav aria-label="Sections" className="mx-auto grid max-w-xl grid-cols-5 px-1 pb-[max(0.25rem,env(safe-area-inset-bottom))]">
        {items.map((item) => {
          const on = active(item.key, item.href)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex flex-col items-center gap-1 px-1 py-2 text-[11px] font-medium tracking-wide",
                on ? "text-forecast" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
