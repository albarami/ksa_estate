import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { uploadIntake, fetchProforma } from '../utils/api'
import { formatArea } from '../utils/formatters'
import type { LandObject, ProFormaResult, Overrides, Labels } from '../types'

interface Props {
  labels: Labels
  onComplete: (land: LandObject, proforma: ProFormaResult, overrides: Overrides) => void
  onCancel: () => void
}

type Step = 'upload' | 'processing' | 'confirm' | 'analyzing'

export default function IntakeFlow({ labels: _labels, onComplete, onCancel }: Props) {
  const [step, setStep] = useState<Step>('upload')
  const [error, setError] = useState('')
  const [extracted, setExtracted] = useState<Record<string, unknown> | null>(null)
  const [merged, setMerged] = useState<Record<string, unknown> | null>(null)
  const [conflicts, setConflicts] = useState<string[]>([])
  const [geoportal, setGeoportal] = useState<LandObject | null>(null)
  const [landPrice, setLandPrice] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setStep('processing')
    setError('')
    try {
      const result = await uploadIntake(file)
      setExtracted(result.extracted)
      setMerged(result.merged)
      setConflicts(result.conflicts)
      setGeoportal(result.geoportal as LandObject | null)
      setStep('confirm')
    } catch (err) {
      setError(String(err))
      setStep('upload')
    }
  }

  const handleAnalyze = async () => {
    if (!landPrice || !extracted) return
    setStep('analyzing')

    // BUG 1 FIX: Document area takes priority over Geoportal (which may hit parent parcel)
    const docArea = extracted.land_area_sqm as number
    const geoArea = geoportal?.area_sqm
    const area = docArea || geoArea || 0

    const price = parseFloat(landPrice)
    const far = (merged?.geoportal_regulations as Record<string, unknown>)?.far as number || 1.2

    // BUG 2 FIX: SREM price is for RAW LAND transactions, NOT finished unit sales.
    // Default sale price = construction cost * 2 (typical developer margin)
    const infraCost = 500
    const superCost = 2500
    const defaultSalePrice = (infraCost + superCost) * 2  // 6,000 SAR/m²

    // Build overrides with document data + user price + smart defaults
    const overrides: Overrides = {
      // BUG 1 FIX: Force document area into computation via override
      land_area_sqm: area,
      land_price_per_sqm: price,
      sale_price_per_sqm: defaultSalePrice,
      infrastructure_cost_per_sqm: infraCost,
      superstructure_cost_per_sqm: superCost,
      parking_area_sqm: 0,
      far: far,
      in_kind_pct: 0,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
      interest_rate_pct: 0.08,
      efficiency_ratio: 1.0,
    }

    try {
      // If we have a geoportal parcel, use it — but override area with document area
      if (geoportal?.parcel_id) {
        const result = await fetchProforma(geoportal.parcel_id, overrides)
        // BUG 1 FIX: Replace Geoportal area with document area in the land object shown to user
        const landObj = { ...result.land_object }
        if (docArea && docArea !== result.land_object.area_sqm) {
          landObj.area_sqm = docArea
          // Store Geoportal area for reference (displayed in conflicts)
          ;(landObj as Record<string, unknown>).geoportal_area_sqm = result.land_object.area_sqm
        }
        onComplete(landObj, result.proforma, overrides)
      } else {
        // No geoportal parcel — build a minimal land object from document
        const fakeLand: LandObject = {
          parcel_id: 0,
          fetched_at: new Date().toISOString(),
          parcel_number: String(extracted.plan_number || ''),
          plan_number: String(extracted.plan_number || ''),
          block_number: '',
          object_id: 0,
          district_name: String(extracted.district || ''),
          municipality: String(extracted.city || ''),
          centroid: { lng: 0, lat: 0 },
          geometry: null,
          area_sqm: area,
          building_use_code: 0,
          building_code_label: String(extracted.building_code || 'غير محدد'),
          primary_use_code: 0,
          primary_use_label: '',
          secondary_use_code: 0,
          detailed_use_code: 0,
          detailed_use_label: '',
          reviewed_bld_code: 0,
          regulations: { max_floors: null, far: far, coverage_ratio: null, allowed_uses: [] },
          market: { srem_market_index: null, srem_index_change: null, daily_total_transactions: null, daily_total_value_sar: null, daily_avg_price_sqm: null, trending_districts: [] },
          data_health: { fields_checked: 0, fields_populated: 0, score_pct: 0 },
        }

        // No geoportal parcel — show dashboard with document data
        // User will need to adjust manually
        onComplete(fakeLand, {} as ProFormaResult, overrides)
      }
    } catch (err) {
      setError(String(err))
      setStep('confirm')
    }
  }

  const district = extracted?.district || merged?.geoportal_district || ''
  const plan = extracted?.plan_number || merged?.geoportal_plan || ''
  const area = (extracted?.land_area_sqm as number) || (geoportal?.area_sqm) || 0
  const status = extracted?.land_status || ''
  const code = merged?.geoportal_building_code || extracted?.building_code || ''

  // Market context from geoportal district data — only show if >500 (real price, not junk aggregate)
  const districtMarket = geoportal?.market?.district
  const rawMarketAvg = districtMarket?.avg_price_sqm
  const marketAvg = (rawMarketAvg && rawMarketAvg > 500) ? rawMarketAvg : null
  const marketPeriod = districtMarket?.period
  const indexHistory = districtMarket?.index_history || []
  const latestIndex = indexHistory.length > 0 ? indexHistory[indexHistory.length - 1] : null

  // Plan info from Geoportal layer 3
  const planInfo = geoportal?.plan_info
  const districtDemo = geoportal?.district_demographics

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-lg"
      >
        {/* Upload step */}
        <AnimatePresence mode="wait">
          {step === 'upload' && (
            <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <h2 className="text-2xl font-bold text-center mb-6" style={{ color: 'var(--color-gold)' }}>
                ارفع عرض الأرض
              </h2>
              <div
                onClick={() => fileRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
                className="border-2 border-dashed border-[var(--color-border)] rounded-xl p-12 text-center cursor-pointer hover:border-[var(--color-gold)] transition-colors"
              >
                <div className="text-4xl mb-4">📄</div>
                <p className="text-[var(--color-text-dim)]">اسحب ملف .docx هنا أو اضغط للاختيار</p>
                <p className="text-xs text-[var(--color-text-dim)] mt-2">Drag & drop .docx or click to browse</p>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".docx"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
              />
              {error && <p className="text-[var(--color-negative)] text-sm mt-3 text-center">{error}</p>}
              <button onClick={onCancel} className="w-full mt-4 text-sm text-[var(--color-text-dim)] hover:text-[var(--color-gold)]">
                العودة للبحث اليدوي
              </button>
            </motion.div>
          )}

          {step === 'processing' && (
            <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center">
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                className="w-12 h-12 border-3 border-[var(--color-gold)] border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-lg">جاري تحليل المستند...</p>
              <p className="text-sm text-[var(--color-text-dim)] mt-2">Extracting data with AI</p>
            </motion.div>
          )}

          {step === 'confirm' && extracted && (
            <motion.div key="confirm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--color-gold)' }}>تم استخراج البيانات</h2>

              {/* Extracted summary card */}
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 mb-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {district && <div><span className="text-[var(--color-text-dim)]">الحي:</span> <span className="font-bold">{String(district)}</span></div>}
                  {plan && <div><span className="text-[var(--color-text-dim)]">المخطط:</span> <span className="font-bold">{String(plan)}</span></div>}
                  {area > 0 && <div><span className="text-[var(--color-text-dim)]">المساحة:</span> <span className="font-bold" style={{ color: 'var(--color-gold)' }}>{formatArea(area)}</span></div>}
                  {status && <div><span className="text-[var(--color-text-dim)]">الحالة:</span> <span className="font-bold">{String(status)}</span></div>}
                  {code && <div><span className="text-[var(--color-text-dim)]">نظام البناء:</span> <span className="font-bold">{String(code)}</span></div>}
                </div>
              </div>

              {/* Market context */}
              {(marketAvg || planInfo?.plan_status || districtDemo?.population) && (
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-4 mb-4">
                  <h4 className="text-sm font-bold mb-3 flex items-center gap-2" style={{ color: 'var(--color-gold)' }}>
                    <span>📊</span> سياق السوق
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {marketAvg && (
                      <div className="p-2 rounded-lg bg-[var(--color-card)]">
                        <div className="text-xs text-[var(--color-text-dim)]">سعر الأرض (صفقات)</div>
                        <div className="font-bold" style={{ color: 'var(--color-gold)' }}>
                          {marketAvg.toLocaleString()} ر.س/م²
                        </div>
                        <div className="text-[10px] text-[var(--color-text-dim)]">
                          {marketPeriod === 'riyadh_average' ? 'متوسط صفقات الرياض' : `صفقات ${districtMarket?.district_name || ''}`}
                        </div>
                      </div>
                    )}
                    {latestIndex && (
                      <div className="p-2 rounded-lg bg-[var(--color-card)]">
                        <div className="text-xs text-[var(--color-text-dim)]">مؤشر السوق</div>
                        <div className="font-bold">{latestIndex.index.toLocaleString()}</div>
                        <div className={`text-[10px] ${latestIndex.change >= 0 ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
                          {latestIndex.change >= 0 ? '+' : ''}{latestIndex.change.toFixed(1)}
                        </div>
                      </div>
                    )}
                    {planInfo?.plan_status && (
                      <div className="p-2 rounded-lg bg-[var(--color-card)]">
                        <div className="text-xs text-[var(--color-text-dim)]">حالة المخطط</div>
                        <div className="font-bold">{planInfo.plan_status}</div>
                        {planInfo.plan_use && <div className="text-[10px] text-[var(--color-text-dim)]">{planInfo.plan_use} / {planInfo.plan_type}</div>}
                      </div>
                    )}
                    {districtDemo?.population && (
                      <div className="p-2 rounded-lg bg-[var(--color-card)]">
                        <div className="text-xs text-[var(--color-text-dim)]">سكان الحي</div>
                        <div className="font-bold">{districtDemo.population.toLocaleString()}</div>
                        {districtDemo.district_name_en && <div className="text-[10px] text-[var(--color-text-dim)]">{districtDemo.district_name_en}</div>}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Conflicts */}
              {conflicts.length > 0 && (
                <div className="rounded-xl border border-[var(--color-warning)] bg-[var(--color-warning)]/10 p-3 mb-4 text-sm">
                  {conflicts.map((c, i) => <p key={i} className="text-[var(--color-warning)]">⚠ {c}</p>)}
                </div>
              )}

              {/* Price input — THE ONE REQUIRED QUESTION */}
              <div className="rounded-xl border border-[var(--color-gold)] bg-[var(--color-card)] p-4 mb-4">
                <label className="block text-sm mb-2 font-semibold">كم سعر المتر المطلوب؟</label>
                {marketAvg && (
                  <p className="text-xs text-[var(--color-text-dim)] mb-2">
                    متوسط صفقات الأراضي: <span className="font-bold" style={{ color: 'var(--color-gold)' }}>{marketAvg.toLocaleString()} ر.س/م²</span>
                    <span className="text-[var(--color-text-dim)]"> (أرض خام، ليس وحدات مبنية)</span>
                  </p>
                )}
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={landPrice}
                    onChange={e => setLandPrice(e.target.value)}
                    placeholder={marketAvg ? `متوسط: ${marketAvg.toLocaleString()}` : 'مثال: 7000'}
                    className="flex-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-4 py-3 text-lg text-center outline-none focus:border-[var(--color-gold)]"
                    dir="ltr"
                  />
                  <span className="flex items-center text-[var(--color-text-dim)]">ر.س/م²</span>
                </div>
              </div>

              {error && <p className="text-[var(--color-negative)] text-sm mb-3">{error}</p>}

              <button
                onClick={handleAnalyze}
                disabled={!landPrice}
                className="w-full py-3 rounded-xl text-lg font-bold transition-all hover:scale-105 active:scale-95 disabled:opacity-40"
                style={{ background: 'var(--color-gold)', color: '#0A0A0F' }}
              >
                حلل الفرصة
              </button>

              <button onClick={onCancel} className="w-full mt-3 text-sm text-[var(--color-text-dim)] hover:text-[var(--color-gold)]">
                إلغاء
              </button>
            </motion.div>
          )}

          {step === 'analyzing' && (
            <motion.div key="analyzing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center">
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                className="w-12 h-12 border-3 border-[var(--color-gold)] border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-lg">جاري حساب الجدوى...</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
