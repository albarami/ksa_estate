import { motion } from 'framer-motion'
import type { Sensitivity, Labels } from '../types'

interface Props {
  sensitivity: Sensitivity
  labels: Labels
}

function cellColor(irr: number | null): string {
  if (irr == null) return 'transparent'
  if (irr >= 0.15) return 'rgba(34,197,94,0.4)'
  if (irr >= 0.10) return 'rgba(34,197,94,0.25)'
  if (irr >= 0.05) return 'rgba(245,158,11,0.25)'
  if (irr >= 0) return 'rgba(245,158,11,0.15)'
  if (irr >= -0.10) return 'rgba(239,68,68,0.2)'
  return 'rgba(239,68,68,0.35)'
}

export default function SensitivityHeatmap({ sensitivity, labels }: Props) {
  const { sale_price_range, construction_cost_range, irr_matrix } = sensitivity

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-4">{labels.sensitivity}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="p-2 text-xs text-[var(--color-text-dim)]">
                {labels.salePrice} ↓ \ {labels.constructionCost} →
              </th>
              {construction_cost_range.map((c) => (
                <th key={c} className="p-2 text-center text-xs text-[var(--color-text-dim)]">
                  {c.toLocaleString()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sale_price_range.map((sp, ri) => (
              <tr key={sp}>
                <td className="p-2 text-xs font-medium">{sp.toLocaleString()}</td>
                {irr_matrix[ri].map((irr, ci) => (
                  <td
                    key={ci}
                    className="p-2 text-center text-xs font-medium rounded"
                    style={{ background: cellColor(irr) }}
                    title={irr != null ? `IRR: ${(irr * 100).toFixed(1)}%` : 'N/A'}
                  >
                    {irr != null ? `${(irr * 100).toFixed(1)}%` : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
