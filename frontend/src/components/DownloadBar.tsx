import { getExcelUrl } from '../utils/api'
import type { Overrides, Labels, Lang } from '../types'

interface Props {
  parcelId: number
  overrides: Overrides
  labels: Labels
  lang: Lang
}

export default function DownloadBar({ parcelId, overrides, labels, lang }: Props) {
  const params: Record<string, number | string> = { lang }
  if (overrides.land_price_per_sqm) params.land_price_per_sqm = overrides.land_price_per_sqm as number
  if (overrides.sale_price_per_sqm) params.sale_price_per_sqm = overrides.sale_price_per_sqm as number
  if (overrides.fund_period_years) params.fund_period_years = overrides.fund_period_years as number

  return (
    <div className="fixed bottom-0 inset-x-0 bg-[var(--color-card)] border-t border-[var(--color-border)] px-6 py-3 flex items-center justify-between z-50">
      <div className="text-sm text-[var(--color-text-dim)]">
        Parcel {parcelId.toLocaleString()}
      </div>
      <div className="flex gap-3">
        <button
          onClick={() => {
            navigator.clipboard.writeText(window.location.href)
          }}
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm hover:border-[var(--color-gold)] transition-colors"
        >
          {labels.share}
        </button>
        <a
          href={getExcelUrl(parcelId, params as Record<string, number>)}
          download
          className="px-6 py-2 rounded-lg text-sm font-semibold transition-all hover:scale-105 active:scale-95"
          style={{ background: 'var(--color-gold)', color: '#0A0A0F' }}
        >
          {labels.downloadExcel}
        </a>
      </div>
    </div>
  )
}
