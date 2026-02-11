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
    { id: 'parking_area_sqm', label: 'مواقف (م²)', min: 0, max: 30000, step: 1000, format: n => `${n.toLocaleString()} م²` },
    { id: 'far', label: 'معامل البناء (FAR)', min: 0.5, max: 3.0, step: 0.1, format: n => n.toFixed(1) },
    { id: 'fund_period_years', label: labels.fundPeriod, min: 2, max: 5, step: 1, format: n => `${n} ${labels.year}` },
    { id: 'bank_ltv_pct', label: labels.bankLtv, min: 0, max: 0.80, step: 0.01, format: n => `${(n * 100).toFixed(0)}%` },
  ]

  const getValue = (id: string): number => {
    if (id === '_construction_total') return totalConstCost
    if (id === 'far') return (overrides.far as number) ?? 1.5
    const defaults: Record<string, number> = {
      land_price_per_sqm: 7000,
      sale_price_per_sqm: 12500,
      parking_area_sqm: 15000,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
    }
    return (overrides[id] as number) ?? defaults[id] ?? 0
  }

  const handleChange = (id: string, val: number) => {
    if (id === '_construction_total') {
      const newInfra = 500
      const newSuper = Math.max(val - newInfra, 0)
      onChange({ ...overrides, infrastructure_cost_per_sqm: newInfra, superstructure_cost_per_sqm: newSuper })
    } else if (id === 'far') {
      onChange({ ...overrides, far: val })
    } else {
      onChange({ ...overrides, [id]: val })
    }
  }

  const reset = () => {
    onChange({
      land_price_per_sqm: 7000,
      sale_price_per_sqm: 12500,
      infrastructure_cost_per_sqm: 500,
      superstructure_cost_per_sqm: 2500,
      parking_area_sqm: 15000,
      parking_cost_per_sqm: 2000,
      far: 1.5,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
      interest_rate_pct: 0.08,
      efficiency_ratio: 1.0,
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
