import { motion } from 'framer-motion'
import type { KPIs, Labels } from '../types'

interface Props {
  kpis: KPIs
  salePricePerSqm: number
  labels: Labels
}

const numFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

const RISK_LABELS: Record<string, { ar: string; icon: string }> = {
  fund_overhead_high: { ar: 'رسوم الصندوق مرتفعة (>5%)', icon: '💸' },
  high_inkind_exposure: { ar: 'تعرض عيني مرتفع (>50%)', icon: '🤝' },
  negative_returns: { ar: 'عوائد سلبية', icon: '📉' },
  unknown_zoning: { ar: 'تنظيم غير محدد', icon: '❓' },
  high_leverage: { ar: 'رافعة مالية عالية (>50%)', icon: '🏦' },
}

function ScoreGauge({ score }: { score: number }) {
  const clampedScore = Math.max(0, Math.min(100, score))
  const color = clampedScore >= 70 ? 'var(--color-positive)' : clampedScore >= 40 ? 'var(--color-warning)' : 'var(--color-negative)'
  const label = clampedScore >= 70 ? 'فرصة جيدة' : clampedScore >= 40 ? 'مقبولة' : 'ضعيفة'

  return (
    <div className="text-center">
      <div className="relative w-24 h-24 mx-auto">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="var(--color-border)" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="42" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={`${clampedScore * 2.64} 264`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-black" style={{ color }}>{clampedScore}</span>
        </div>
      </div>
      <div className="text-xs mt-1 font-bold" style={{ color }}>{label}</div>
      <div className="text-[10px] text-[var(--color-text-dim)]">Deal Score</div>
    </div>
  )
}

export default function MarketIntelligence({ kpis, salePricePerSqm, labels: _labels }: Props) {
  const breakEven = kpis.break_even_price_sqm ?? 0
  const landPerGba = kpis.land_cost_per_gba ?? 0
  const revMultiple = kpis.revenue_multiple ?? 0
  const overhead = kpis.fund_overhead_ratio ?? 0
  const dealScore = kpis.deal_score ?? 0
  const risks = kpis.risk_flags ?? []

  // How much margin above break-even
  const margin = salePricePerSqm > 0 && breakEven > 0
    ? ((salePricePerSqm - breakEven) / breakEven) * 100
    : 0
  const marginColor = margin > 20 ? 'var(--color-positive)' : margin > 0 ? 'var(--color-warning)' : 'var(--color-negative)'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
        <span>🎯</span> تحليل الصفقة
      </h3>

      <div className="flex gap-4">
        {/* Deal Score Gauge */}
        <ScoreGauge score={dealScore} />

        {/* Metrics Grid */}
        <div className="flex-1 grid grid-cols-2 gap-2">
          {/* Break-even */}
          <div className="p-2 rounded-lg bg-[var(--color-bg)]">
            <div className="text-[10px] text-[var(--color-text-dim)]">نقطة التعادل</div>
            <div className="text-sm font-bold">{numFmt.format(breakEven)} ر.س/م²</div>
            {margin !== 0 && (
              <div className="text-[10px] font-bold" style={{ color: marginColor }}>
                {margin > 0 ? '+' : ''}{margin.toFixed(0)}% هامش
              </div>
            )}
          </div>

          {/* Land cost per GBA */}
          <div className="p-2 rounded-lg bg-[var(--color-bg)]">
            <div className="text-[10px] text-[var(--color-text-dim)]">تكلفة الأرض/م² مبني</div>
            <div className="text-sm font-bold">{numFmt.format(landPerGba)} ر.س</div>
          </div>

          {/* Revenue multiple */}
          <div className="p-2 rounded-lg bg-[var(--color-bg)]">
            <div className="text-[10px] text-[var(--color-text-dim)]">مضاعف العائد</div>
            <div className="text-sm font-bold" style={{ color: revMultiple >= 1.2 ? 'var(--color-positive)' : revMultiple >= 1 ? 'var(--color-warning)' : 'var(--color-negative)' }}>
              {revMultiple.toFixed(2)}x
            </div>
          </div>

          {/* Fund overhead */}
          <div className="p-2 rounded-lg bg-[var(--color-bg)]">
            <div className="text-[10px] text-[var(--color-text-dim)]">نسبة رسوم الصندوق</div>
            <div className="text-sm font-bold" style={{ color: overhead > 0.05 ? 'var(--color-negative)' : 'var(--color-positive)' }}>
              {(overhead * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Risk Flags */}
      {risks.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-dim)] mb-2">مخاطر:</div>
          <div className="flex flex-wrap gap-1.5">
            {risks.map(flag => {
              const info = RISK_LABELS[flag] || { ar: flag, icon: '⚠️' }
              return (
                <span
                  key={flag}
                  className="px-2 py-1 rounded-full text-[10px] font-bold border"
                  style={{ borderColor: 'var(--color-negative)', color: 'var(--color-negative)' }}
                >
                  {info.icon} {info.ar}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {risks.length === 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <span className="text-xs text-[var(--color-positive)] font-bold">✓ لا توجد مخاطر مرتفعة</span>
        </div>
      )}
    </motion.div>
  )
}
