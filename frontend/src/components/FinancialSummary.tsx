import { motion } from 'framer-motion'
import type { KPIs, Labels } from '../types'
import { formatSAR, formatPct, formatPct2, irrColor } from '../utils/formatters'

interface FundSize {
  total_fund_size: number
  equity_amount: number
  in_kind_contribution: number
  bank_loan: number
  equity_pct: number
  debt_pct: number
}

interface Props {
  kpis: KPIs
  fundSize: FundSize
  labels: Labels
}

export default function FinancialSummary({ kpis, fundSize, labels }: Props) {
  const inKind = fundSize.in_kind_contribution || 0
  const inKindPct = fundSize.total_fund_size > 0 ? inKind / fundSize.total_fund_size : 0

  const kpiCards = [
    { label: labels.irr || 'IRR', value: formatPct2(kpis.irr), color: '', className: irrColor(kpis.irr) },
    { label: labels.roe || 'ROE', value: formatPct2(kpis.roe_total), color: kpis.roe_total >= 0 ? 'var(--color-positive)' : 'var(--color-negative)' },
    { label: labels.netProfit || 'Net Profit', value: formatSAR(kpis.equity_net_profit), color: kpis.equity_net_profit >= 0 ? 'var(--color-positive)' : 'var(--color-negative)' },
    { label: labels.yieldOnCost || 'Yield on Cost', value: `${kpis.yield_on_cost.toFixed(2)}x`, color: kpis.yield_on_cost >= 1 ? 'var(--color-positive)' : 'var(--color-negative)' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-4">{labels.financialSummary || 'Financial Summary'}</h3>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {kpiCards.map((c, i) => (
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

      {/* Capital structure bar */}
      <div className="p-4 rounded-lg bg-[var(--color-bg)]">
        <div className="text-xs text-[var(--color-text-dim)] mb-2">{labels.fundSize || 'Fund Size'}: {formatSAR(fundSize.total_fund_size)}</div>
        <div className="flex rounded-full overflow-hidden h-6 mb-3">
          {fundSize.equity_pct > 0 && (
            <div
              className="flex items-center justify-center text-xs font-bold"
              style={{ width: `${fundSize.equity_pct * 100}%`, background: 'var(--color-gold)', color: '#0A0A0F' }}
            >
              {formatPct(fundSize.equity_pct)}
            </div>
          )}
          {inKindPct > 0 && (
            <div
              className="flex items-center justify-center text-xs font-bold"
              style={{ width: `${inKindPct * 100}%`, background: 'var(--color-saudi-green)', color: '#fff' }}
            >
              {formatPct(inKindPct)}
            </div>
          )}
          {fundSize.debt_pct > 0 && (
            <div
              className="flex items-center justify-center text-xs font-bold"
              style={{ width: `${fundSize.debt_pct * 100}%`, background: '#4B5563', color: '#fff' }}
            >
              {formatPct(fundSize.debt_pct)}
            </div>
          )}
        </div>
        <div className="flex justify-between text-xs text-[var(--color-text-dim)]">
          <span style={{ color: 'var(--color-gold)' }}>{labels.equity || 'Equity'}: {formatSAR(fundSize.equity_amount)}</span>
          {inKind > 0 && <span style={{ color: 'var(--color-saudi-green)' }}>عيني: {formatSAR(inKind)}</span>}
          <span>تمويل: {formatSAR(fundSize.bank_loan)}</span>
        </div>
      </div>
    </motion.div>
  )
}
