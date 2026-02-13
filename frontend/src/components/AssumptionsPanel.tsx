import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Overrides, Labels } from '../types'

interface Props {
  overrides: Overrides
  onChange: (o: Overrides) => void
  labels: Labels
  /** Defaults from the actual land object / market data — used for reset */
  landDefaults?: Partial<Overrides>
}

interface SliderDef {
  id: string
  label: string
  min: number
  max: number
  step: number
  format: (n: number) => string
}

export default function AssumptionsPanel({ overrides, onChange, labels, landDefaults }: Props) {
  const [open, setOpen] = useState(true)

  // No combined construction cost — separate sliders now

  const sliders: SliderDef[] = [
    // Land & Revenue
    { id: 'land_price_per_sqm', label: labels.landPrice || 'Land Price / m²', min: 500, max: 25000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    { id: 'sale_price_per_sqm', label: labels.salePrice || 'Sale Price / m²', min: 2000, max: 30000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    // Construction
    { id: 'infrastructure_cost_per_sqm', label: labels.constructionCost ? 'بنية تحتية / م²' : 'Infrastructure / m²', min: 100, max: 2000, step: 50, format: n => `${n.toLocaleString()} ر.س` },
    { id: 'superstructure_cost_per_sqm', label: 'بنية علوية / م²', min: 1000, max: 5000, step: 100, format: n => `${n.toLocaleString()} ر.س` },
    { id: 'parking_area_sqm', label: 'مواقف (م²)', min: 0, max: 30000, step: 1000, format: n => `${n.toLocaleString()} م²` },
    // Zoning
    { id: 'far', label: 'معامل البناء (FAR)', min: 0.5, max: 4.0, step: 0.1, format: n => n.toFixed(1) },
    // Deal structure
    { id: 'in_kind_pct', label: 'مساهمة عينية (أرض) %', min: 0, max: 1.0, step: 0.05, format: n => `${(n * 100).toFixed(0)}%` },
    { id: 'bank_ltv_pct', label: labels.bankLtv || 'Bank LTV', min: 0, max: 0.80, step: 0.01, format: n => `${(n * 100).toFixed(0)}%` },
    // Fund
    { id: 'fund_period_years', label: labels.fundPeriod || 'Fund Period', min: 2, max: 7, step: 1, format: n => `${n} ${labels.year || 'Year'}` },
    { id: 'interest_rate_pct', label: 'معدل الفائدة %', min: 0, max: 0.15, step: 0.005, format: n => `${(n * 100).toFixed(1)}%` },
  ]

  const getValue = (id: string): number => {
    // Fallback defaults — only used if no override AND no landDefault
    const fallbacks: Record<string, number> = {
      land_price_per_sqm: 5000,
      sale_price_per_sqm: 8000,
      infrastructure_cost_per_sqm: 500,
      superstructure_cost_per_sqm: 2500,
      parking_area_sqm: 0,
      far: 1.0,
      in_kind_pct: 0,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
      interest_rate_pct: 0.08,
    }
    return (overrides[id] as number) ?? (landDefaults?.[id] as number) ?? fallbacks[id] ?? 0
  }

  const handleChange = (id: string, val: number) => {
    onChange({ ...overrides, [id]: val })
  }

  const reset = () => {
    // Reset to land-sourced defaults, keeping FAR from land regulations
    const currentFar = (landDefaults?.far as number) ?? (overrides.far as number) ?? 1.0
    onChange({
      land_price_per_sqm: (landDefaults?.land_price_per_sqm as number) ?? 5000,
      sale_price_per_sqm: (landDefaults?.sale_price_per_sqm as number) ?? 8000,
      infrastructure_cost_per_sqm: (landDefaults?.infrastructure_cost_per_sqm as number) ?? 500,
      superstructure_cost_per_sqm: (landDefaults?.superstructure_cost_per_sqm as number) ?? 2500,
      parking_area_sqm: (landDefaults?.parking_area_sqm as number) ?? 0,
      parking_cost_per_sqm: 2000,
      far: currentFar,
      in_kind_pct: 0,
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
