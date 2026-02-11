import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Overrides, Labels } from '../types'

interface Props {
  overrides: Overrides
  onChange: (o: Overrides) => void
  labels: Labels
}

interface SliderRow {
  key: keyof Overrides
  label: string
  min: number
  max: number
  step: number
  defaultVal: number
  format: (n: number) => string
}

export default function AssumptionsPanel({ overrides, onChange, labels }: Props) {
  const [open, setOpen] = useState(true)

  const rows: SliderRow[] = [
    { key: 'land_price_per_sqm', label: labels.landPrice, min: 500, max: 20000, step: 100, defaultVal: 5000, format: n => `${n.toLocaleString()} ر.س` },
    { key: 'sale_price_per_sqm', label: labels.salePrice, min: 2000, max: 25000, step: 100, defaultVal: 8000, format: n => `${n.toLocaleString()} ر.س` },
    { key: 'infrastructure_cost_per_sqm', label: labels.constructionCost, min: 500, max: 6000, step: 100, defaultVal: 3000, format: n => `${n.toLocaleString()} ر.س` },
    { key: 'fund_period_years', label: labels.fundPeriod, min: 2, max: 5, step: 1, defaultVal: 3, format: n => `${n} ${labels.year}` },
    { key: 'bank_ltv_pct', label: labels.bankLtv, min: 0, max: 0.8, step: 0.05, defaultVal: 0.667, format: n => `${(n * 100).toFixed(0)}%` },
  ]

  const update = (key: string, val: number) => {
    // For construction cost, split into infra (500) + super (rest)
    if (key === 'infrastructure_cost_per_sqm') {
      onChange({ ...overrides, infrastructure_cost_per_sqm: 500, superstructure_cost_per_sqm: val - 500 })
    } else {
      onChange({ ...overrides, [key]: val })
    }
  }

  const reset = () => {
    const defaults: Overrides = {}
    rows.forEach(r => { defaults[r.key as string] = r.defaultVal })
    defaults.infrastructure_cost_per_sqm = 500
    defaults.superstructure_cost_per_sqm = 2500
    onChange(defaults)
  }

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-[var(--color-bg)] transition-colors rounded-t-xl"
      >
        <h3 className="font-bold text-lg">{labels.assumptions}</h3>
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
            <div className="p-4 pt-0 space-y-4">
              {rows.map((r) => {
                const val = (overrides[r.key] as number) ?? r.defaultVal
                return (
                  <div key={r.key as string}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-[var(--color-text-dim)]">{r.label}</span>
                      <span className="font-semibold" style={{ color: 'var(--color-gold)' }}>
                        {r.format(val)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={r.min}
                      max={r.max}
                      step={r.step}
                      value={val}
                      onChange={e => update(r.key as string, parseFloat(e.target.value))}
                      className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                      style={{ background: `linear-gradient(to right, var(--color-gold) ${((val - r.min) / (r.max - r.min)) * 100}%, var(--color-border) 0%)` }}
                    />
                  </div>
                )
              })}
              <button
                onClick={reset}
                className="w-full py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-dim)] hover:border-[var(--color-gold)] transition-colors"
              >
                {labels.reset}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
