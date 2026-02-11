import { motion } from 'framer-motion'
import type { KPIs, Labels } from '../types'
import { formatSAR, formatPct2, irrColor } from '../utils/formatters'

interface Props {
  kpis: KPIs
  fundSize: number
  equity: number
  labels: Labels
}

export default function FinancialSummary({ kpis, fundSize, equity, labels }: Props) {
  const cards = [
    { label: labels.fundSize, value: formatSAR(fundSize), color: 'var(--color-text)' },
    { label: labels.equity, value: formatSAR(equity), color: 'var(--color-text)' },
    { label: labels.irr, value: formatPct2(kpis.irr), color: '', className: irrColor(kpis.irr) },
    { label: labels.roe, value: formatPct2(kpis.roe_total), color: kpis.roe_total >= 0 ? 'var(--color-positive)' : 'var(--color-negative)' },
    { label: labels.netProfit, value: formatSAR(kpis.equity_net_profit), color: kpis.equity_net_profit >= 0 ? 'var(--color-positive)' : 'var(--color-negative)' },
    { label: labels.yieldOnCost, value: `${kpis.yield_on_cost.toFixed(2)}x`, color: kpis.yield_on_cost >= 1 ? 'var(--color-positive)' : 'var(--color-negative)' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-4">{labels.financialSummary}</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {cards.map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.05 * i }}
            className="p-4 rounded-lg bg-[var(--color-bg)] text-center"
          >
            <div className="text-xs text-[var(--color-text-dim)] mb-2">{c.label}</div>
            <div
              className={`text-xl font-bold ${c.className || ''}`}
              style={c.color ? { color: c.color } : undefined}
            >
              {c.value}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}
