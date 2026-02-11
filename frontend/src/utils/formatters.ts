const sarFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const numFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const pctFmt = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const pct2Fmt = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function formatSAR(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${sarFmt.format(n)} ر.س`
}

export function formatNum(n: number | null | undefined): string {
  if (n == null) return '—'
  return numFmt.format(n)
}

export function formatPct(n: number | null | undefined): string {
  if (n == null) return '—'
  return pctFmt.format(n)
}

export function formatPct2(n: number | null | undefined): string {
  if (n == null) return '—'
  return pct2Fmt.format(n)
}

export function formatArea(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${numFmt.format(n)} م²`
}

export function irrColor(irr: number | null): string {
  if (irr == null) return 'text-[var(--color-text-dim)]'
  if (irr >= 0.10) return 'text-[var(--color-positive)]'
  if (irr >= 0.05) return 'text-[var(--color-warning)]'
  return 'text-[var(--color-negative)]'
}
