export function PageHeader({
  eyebrow,
  title,
  lede,
}: {
  eyebrow?: string
  title: string
  lede?: string
}) {
  return (
    <header className="mb-6 space-y-2">
      {eyebrow ? (
        <p className="text-xs font-medium tracking-[0.18em] text-forecast uppercase">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="font-display text-4xl leading-none tracking-tight sm:text-5xl">{title}</h1>
      {lede ? (
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">{lede}</p>
      ) : null}
    </header>
  )
}
