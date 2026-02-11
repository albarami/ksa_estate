import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchScenarios } from '../utils/api'
import { formatSAR, formatPct2 } from '../utils/formatters'
import type { Overrides, ProFormaResult, Labels } from '../types'

interface Props {
  parcelId: number
  baseOverrides: Overrides
  labels: Labels
}

interface ScenarioResult {
  name: string
  proforma: ProFormaResult
}

export default function ScenarioComparison({ parcelId, baseOverrides, labels }: Props) {
  const [open, setOpen] = useState(false)
  const [scenarios, setScenarios] = useState<ScenarioResult[]>([])
  const [loading, setLoading] = useState(false)

  const saleBase = (baseOverrides.sale_price_per_sqm as number) || 8000

  useEffect(() => {
    if (!open || scenarios.length > 0) return
    setLoading(true)
    fetchScenarios(parcelId, baseOverrides, [
      { name: labels.conservative, overrides: { sale_price_per_sqm: saleBase * 0.8 } },
      { name: labels.base, overrides: { sale_price_per_sqm: saleBase } },
      { name: labels.aggressive, overrides: { sale_price_per_sqm: saleBase * 1.3 } },
    ])
      .then(r => setScenarios(r.scenarios))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-[var(--color-bg)] transition-colors"
      >
        <h3 className="font-bold text-lg">{labels.scenarios}</h3>
        <span className="text-[var(--color-text-dim)]">{open ? '▲' : '▼'}</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0">
              {loading ? (
                <div className="text-center py-6 text-[var(--color-text-dim)]">جاري التحليل...</div>
              ) : scenarios.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className="text-start p-2 text-[var(--color-text-dim)]"></th>
                      {scenarios.map(s => (
                        <th key={s.name} className="p-2 text-center font-semibold">{s.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: labels.irr, key: 'irr', fmt: formatPct2 },
                      { label: labels.roe, key: 'roe_total', fmt: formatPct2 },
                      { label: labels.netProfit, key: 'equity_net_profit', fmt: formatSAR },
                      { label: labels.fundSize, key: 'total_fund_size', fmt: formatSAR },
                    ].map(row => (
                      <tr key={row.label} className="border-t border-[var(--color-border)]">
                        <td className="p-2 text-[var(--color-text-dim)]">{row.label}</td>
                        {scenarios.map(s => {
                          const val = row.key === 'total_fund_size'
                            ? s.proforma.fund_size.total_fund_size
                            : (s.proforma.kpis as unknown as Record<string, number | null>)[row.key]
                          return (
                            <td key={s.name} className="p-2 text-center font-medium">
                              {row.fmt(val as number)}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
