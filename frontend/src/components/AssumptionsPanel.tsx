import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Overrides, Labels } from '../types'

interface Props {
  overrides: Overrides
  onChange: (o: Overrides) => void
  labels: Labels
}

interface SliderDef {
  id: string
  label: string
  min: number
  max: number
  step: number
  format: (n: number) => string
}

export default function AssumptionsPanel({ overrides, onChange, labels }: Props) {
  const [open, setOpen] = useState(true)

  // Derive combined construction cost for display
  const infra = (overrides.infrastructure_cost_per_sqm as number) ?? 500
  const super_ = (overrides.superstructure_cost_per_sqm as number) ?? 2500
  const totalConstCost = infra + super_

  const sliders: SliderDef[] = [
    { id: 'land_price_per_sqm', label: labels.landPrice, min: 500, max: 20000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    { id: 'sale_price_per_sqm', label: labels.salePrice, min: 2000, max: 25000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    { id: '_construction_total', label: labels.constructionCost, min: 1500, max: 6000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    { id: 'fund_period_years', label: labels.fundPeriod, min: 2, max: 5, step: 1, format: n => `${n} ${labels.year}` },
    { id: 'bank_ltv_pct', label: labels.bankLtv, min: 0, max: 0.80, step: 0.01, format: n => `${(n * 100).toFixed(0)}%` },
  ]

  const getValue = (id: string): number => {
    if (id === '_construction_total') return totalConstCost
    return (overrides[id] as number) ?? {
      land_price_per_sqm: 5000,
      sale_price_per_sqm: 8000,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
    }[id] ?? 0
  }

  const handleChange = (id: string, val: number) => {
    if (id === '_construction_total') {
      // Split: infrastructure stays at 500, superstructure gets the rest
      const newInfra = 500
      const newSuper = Math.max(val - newInfra, 0)
      onChange({ ...overrides, infrastructure_cost_per_sqm: newInfra, superstructure_cost_per_sqm: newSuper })
    } else {
      onChange({ ...overrides, [id]: val })
    }
  }

  const reset = () => {
    onChange({
      land_price_per_sqm: 5000,
      sale_price_per_sqm: 8000,
      infrastructure_cost_per_sqm: 500,
      superstructure_cost_per_sqm: 2500,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
    })
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
            <div className="p-4 pt-0 space-y-5">
              {sliders.map((s) => {
                const val = getValue(s.id)
                const pct = ((val - s.min) / (s.max - s.min)) * 100
                return (
                  <div key={s.id}>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-[var(--color-text-dim)]">{s.label}</span>
                      <span className="font-semibold" style={{ color: 'var(--color-gold)' }}>
                        {s.format(val)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={s.min}
                      max={s.max}
                      step={s.step}
                      value={val}
                      onChange={e => handleChange(s.id, parseFloat(e.target.value))}
                      className="w-full h-2 rounded-full appearance-none cursor-pointer"
                      style={{
                        background: `linear-gradient(to right, var(--color-gold) ${pct}%, var(--color-border) ${pct}%)`,
                      }}
                    />
                  </div>
                )
              })}
              <button
                onClick={reset}
                className="w-full py-2.5 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-dim)] hover:border-[var(--color-gold)] hover:text-[var(--color-gold)] transition-colors"
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
