import type { LandObject } from '../types'
import type { Labels, Lang } from '../utils/i18n'

interface Props {
  land: LandObject
  labels: Labels
  lang: Lang
  onLangToggle: () => void
  onNewSearch: () => void
}

export default function TopBar({ land, labels, lang, onLangToggle, onNewSearch }: Props) {
  const health = land.data_health?.score_pct ?? 0
  const healthColor = health >= 80 ? 'var(--color-positive)' : health >= 50 ? 'var(--color-warning)' : 'var(--color-negative)'

  return (
    <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--color-border)] bg-[var(--color-card)]">
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-[var(--color-text-dim)] text-sm">{labels.parcelId}:</span>
        <span className="font-bold text-lg">{land.parcel_id.toLocaleString()}</span>
        <span className="text-[var(--color-text-dim)]">|</span>
        <span>{land.district_name}</span>
        <span className="text-[var(--color-text-dim)]">|</span>
        <span className="text-sm text-[var(--color-text-dim)]">{land.municipality}</span>
        {land.building_code_label && (
          <span
            className="px-3 py-1 rounded-full text-sm font-bold"
            style={{ background: 'var(--color-saudi-green)', color: '#fff' }}
          >
            {land.building_code_label}
          </span>
        )}
        <span
          className="w-3 h-3 rounded-full inline-block"
          style={{ background: healthColor }}
          title={`${labels.dataHealth}: ${health}%`}
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={onLangToggle}
          className="px-3 py-1 rounded border border-[var(--color-border)] text-sm hover:border-[var(--color-gold)] transition-colors"
        >
          {lang === 'ar' ? 'EN' : 'AR'}
        </button>
        <button
          onClick={onNewSearch}
          className="px-4 py-1.5 rounded-lg border border-[var(--color-gold)] text-[var(--color-gold)] text-sm hover:bg-[var(--color-gold)]/10 transition-colors"
        >
          {labels.newSearch}
        </button>
      </div>
    </div>
  )
}
