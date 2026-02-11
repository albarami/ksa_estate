import { motion } from 'framer-motion'
import type { Regulations, Labels } from '../types'
import { formatPct } from '../utils/formatters'

interface Props {
  regulations: Regulations
  buildingCode: string
  labels: Labels
}

export default function ZoningCard({ regulations, buildingCode, labels }: Props) {
  const items = [
    { label: labels.maxFloors, value: regulations.max_floors ?? '—', icon: '🏢' },
    { label: labels.far, value: regulations.far ?? '—', icon: '📐' },
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

      <div className="grid grid-cols-3 gap-3 mb-4">
        {items.map((item) => (
          <div key={item.label} className="text-center p-3 rounded-lg bg-[var(--color-bg)]">
            <div className="text-2xl mb-1">{item.icon}</div>
            <div className="text-xl font-bold" style={{ color: 'var(--color-gold)' }}>{String(item.value)}</div>
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
