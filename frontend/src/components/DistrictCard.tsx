import { motion } from 'framer-motion'
import type { PlanInfo, DistrictDemographics, DistrictMarket, Labels } from '../types'

interface Props {
  districtName: string
  planInfo?: PlanInfo
  demographics?: DistrictDemographics
  districtMarket?: DistrictMarket
  dataSources?: Record<string, boolean>
  labels: Labels
}

const numFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

function Stat({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="p-3 rounded-lg bg-[var(--color-bg)] text-center">
      <div className="text-xs text-[var(--color-text-dim)] mb-1">{label}</div>
      <div className="text-lg font-bold" style={color ? { color } : undefined}>{value}</div>
      {sub && <div className="text-[10px] text-[var(--color-text-dim)] mt-0.5">{sub}</div>}
    </div>
  )
}

function SourceDot({ active }: { active: boolean }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full"
      style={{ background: active ? 'var(--color-positive)' : 'var(--color-text-dim)' }}
      title={active ? 'Active' : 'Inactive'}
    />
  )
}

export default function DistrictCard({
  districtName, planInfo, demographics, districtMarket, dataSources, labels: _labels,
}: Props) {
  const hasDemo = demographics?.population || demographics?.area_m2
  const hasPlan = planInfo?.plan_status
  // Only show market price if it's a real per-m² price (>500), not a junk aggregate
  const avgPrice = districtMarket?.avg_price_sqm
  const hasMarket = avgPrice && avgPrice > 500
  const indexHistory = districtMarket?.index_history || []

  if (!hasDemo && !hasPlan && !hasMarket) return null

  // Mini sparkline for index history
  const renderSparkline = () => {
    if (indexHistory.length < 2) return null
    const values = indexHistory.map(p => p.index)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1
    const w = 120
    const h = 32
    const points = values.map((v, i) => {
      const x = (i / (values.length - 1)) * w
      const y = h - ((v - min) / range) * h
      return `${x},${y}`
    }).join(' ')
    const lastChange = indexHistory[indexHistory.length - 1]?.change ?? 0
    const color = lastChange >= 0 ? 'var(--color-positive)' : 'var(--color-negative)'

    return (
      <svg width={w} height={h} className="mx-auto mt-1">
        <polyline points={points} fill="none" stroke={color} strokeWidth="2" />
      </svg>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg flex items-center gap-2">
          <span>🏘️</span>
          {districtName}
          {demographics?.district_name_en && (
            <span className="text-xs text-[var(--color-text-dim)] font-normal">
              ({demographics.district_name_en})
            </span>
          )}
        </h3>
      </div>

      {/* Plan Status Row */}
      {hasPlan && (
        <div className="flex flex-wrap gap-2 mb-3">
          <span
            className="px-3 py-1 rounded-full text-xs font-bold"
            style={{
              background: planInfo?.plan_status === 'نهائي' ? 'var(--color-positive)' : 'var(--color-warning)',
              color: '#fff',
            }}
          >
            {planInfo?.plan_status}
          </span>
          {planInfo?.plan_use && (
            <span className="px-3 py-1 rounded-full text-xs border border-[var(--color-border)] text-[var(--color-text-dim)]">
              {planInfo.plan_use}
            </span>
          )}
          {planInfo?.plan_type && (
            <span className="px-3 py-1 rounded-full text-xs border border-[var(--color-border)] text-[var(--color-text-dim)]">
              {planInfo.plan_type}
            </span>
          )}
          {planInfo?.plan_date_hijri && (
            <span className="px-3 py-1 rounded-full text-xs border border-[var(--color-border)] text-[var(--color-text-dim)]">
              {planInfo.plan_date_hijri}
            </span>
          )}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        {demographics?.population && (
          <Stat label="السكان" value={numFmt.format(demographics.population)} />
        )}
        {demographics?.area_m2 && (
          <Stat
            label="مساحة الحي"
            value={`${(demographics.area_m2 / 1_000_000).toFixed(1)} كم²`}
          />
        )}
        {hasMarket && (
          <div className="p-3 rounded-lg bg-[var(--color-bg)] text-center">
            <div className="text-xs text-[var(--color-text-dim)] mb-1">سعر الأرض (صفقات)</div>
            <div className="text-lg font-bold" style={{ color: 'var(--color-gold)' }}>{numFmt.format(avgPrice!)} ر.س/م²</div>
            <div className="text-[10px] text-[var(--color-text-dim)] mt-0.5">
              {districtMarket!.period === 'riyadh_average' ? 'متوسط الرياض' : 'متوسط الحي'}
            </div>
            {districtMarket?.confidence && (
              <span
                className="inline-block mt-1 px-2 py-0.5 rounded-full text-[9px] font-bold"
                style={{
                  background: districtMarket.confidence.color === 'green' ? 'var(--color-positive)'
                    : districtMarket.confidence.color === 'yellow' ? 'var(--color-warning)'
                    : 'var(--color-negative)',
                  color: '#fff',
                }}
              >
                الثقة: {districtMarket.confidence.score}% — {districtMarket.confidence.label}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Index Trend */}
      {indexHistory.length > 1 && (
        <div className="p-3 rounded-lg bg-[var(--color-bg)]">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-[var(--color-text-dim)]">مؤشر السوق (أسبوعي)</span>
            {indexHistory.length > 0 && (() => {
              const latest = indexHistory[indexHistory.length - 1]
              const isUp = latest.change >= 0
              return (
                <span className={`text-xs font-bold ${isUp ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
                  {numFmt.format(latest.index)} ({isUp ? '+' : ''}{latest.change.toFixed(1)})
                </span>
              )
            })()}
          </div>
          {renderSparkline()}
        </div>
      )}

      {/* Data sources row */}
      {dataSources && (
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--color-border)]">
          <span className="text-[10px] text-[var(--color-text-dim)]">مصادر البيانات:</span>
          <div className="flex gap-2">
            {Object.entries(dataSources).map(([src, active]) => (
              <div key={src} className="flex items-center gap-1">
                <SourceDot active={active} />
                <span className="text-[9px] text-[var(--color-text-dim)]">
                  {src.replace(/_/g, ' ').replace('identify ', '').replace('layer ', 'L')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}
