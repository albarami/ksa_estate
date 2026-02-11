import { motion } from 'framer-motion'
import type { Regulations, Labels } from '../types'
import { formatPct, formatArea } from '../utils/formatters'

interface Props {
  regulations: Regulations
  buildingCode: string
  areaSqm: number | null
  labels: Labels
}

export default function ZoningCard({ regulations, buildingCode, areaSqm, labels }: Props) {
  const far = regulations.far ?? 1
  const gba = areaSqm ? areaSqm * far : null

  const areaItems = [
    { label: 'مساحة الأرض', value: formatArea(areaSqm), icon: '📏' },
    { label: 'المساحة الإجمالية (GBA)', value: formatArea(gba), icon: '🏗️' },
  ]

  const regItems = [
    { label: labels.maxFloors, value: String(regulations.max_floors ?? '—'), icon: '🏢' },
    { label: labels.far, value: String(regulations.far ?? '—'), icon: '📐' },
    { label: labels.coverage, value: regulations.coverage_ratio ? formatPct(regulations.coverage_ratio) : '—', icon: '📊' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg">{labels.zoning}</h3>
        <span
          className="px-3 py-1 rounded-full text-sm font-bold"
          style={{ background: 'var(--color-saudi-green)', color: '#fff' }}
        >
          {buildingCode}
        </span>
      </div>

      {/* Area row — prominent */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {areaItems.map((item) => (
          <div key={item.label} className="text-center p-3 rounded-lg" style={{ background: 'var(--color-gold)', color: '#0A0A0F' }}>
            <div className="text-lg mb-0.5">{item.icon}</div>
            <div className="text-lg font-bold">{item.value}</div>
            <div className="text-xs font-medium opacity-80">{item.label}</div>
          </div>
        ))}
      </div>

      {/* Regulation values */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {regItems.map((item) => (
          <div key={item.label} className="text-center p-3 rounded-lg bg-[var(--color-bg)]">
            <div className="text-xl mb-1">{item.icon}</div>
            <div className="text-xl font-bold" style={{ color: 'var(--color-gold)' }}>{item.value}</div>
            <div className="text-xs text-[var(--color-text-dim)] mt-1">{item.label}</div>
          </div>
        ))}
      </div>

      {regulations.allowed_uses?.length > 0 && (
        <div className="mb-3">
          <span className="text-xs text-[var(--color-text-dim)]">{labels.allowedUses}:</span>
          <div className="flex gap-1.5 mt-1 flex-wrap">
            {regulations.allowed_uses.map((u) => (
              <span key={u} className="px-2 py-0.5 rounded text-xs border border-[var(--color-border)] text-[var(--color-text-dim)]">
                {(labels as Record<string, string>)[u] || u}
              </span>
            ))}
          </div>
        </div>
      )}

      {regulations.setback_values_m && (
        <div>
          <span className="text-xs text-[var(--color-text-dim)]">{labels.setbacks}:</span>
          <span className="text-sm ms-2">{regulations.setback_values_m.map(v => `${v}م`).join(' / ')}</span>
        </div>
      )}
    </motion.div>
  )
}
