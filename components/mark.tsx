export function Mark({ className = "h-4 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 16" className={className} aria-hidden>
      <path d="M1 8h26" stroke="currentColor" strokeWidth="1.6" />
      <path d="M14 1.5v13" stroke="currentColor" strokeWidth="1.6" />
      <path d="M7 4v8M21 4v8" stroke="currentColor" strokeWidth="1.2" opacity="0.75" />
    </svg>
  )
}
