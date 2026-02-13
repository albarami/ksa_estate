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

    const area = (extracted.land_area_sqm as number) || (geoportal?.area_sqm) || 0
    const price = parseFloat(landPrice)
    const far = (merged?.geoportal_regulations as Record<string, unknown>)?.far as number || 1.2
    const avgMarketPrice = (geoportal?.market?.daily_avg_price_sqm) || 8000

    // Build overrides with document data + user price + smart defaults
    const overrides: Overrides = {
      land_price_per_sqm: price,
      sale_price_per_sqm: avgMarketPrice > 100 ? avgMarketPrice : 8000,
      infrastructure_cost_per_sqm: 500,
      superstructure_cost_per_sqm: 2500,
      parking_area_sqm: 0,
      far: far,
      in_kind_pct: 0,
      fund_period_years: 3,
      bank_ltv_pct: 0.667,
      interest_rate_pct: 0.08,
      efficiency_ratio: 1.0,
    }

    try {
      // If we have a geoportal parcel, use it
      if (geoportal?.parcel_id) {
        const result = await fetchProforma(geoportal.parcel_id, overrides)
        onComplete(result.land_object, result.proforma, overrides)
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

              {/* Conflicts */}
              {conflicts.length > 0 && (
                <div className="rounded-xl border border-[var(--color-warning)] bg-[var(--color-warning)]/10 p-3 mb-4 text-sm">
                  {conflicts.map((c, i) => <p key={i} className="text-[var(--color-warning)]">⚠ {c}</p>)}
                </div>
              )}

              {/* Price input — THE ONE REQUIRED QUESTION */}
              <div className="rounded-xl border border-[var(--color-gold)] bg-[var(--color-card)] p-4 mb-4">
                <label className="block text-sm mb-2 font-semibold">كم سعر المتر المطلوب؟</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={landPrice}
                    onChange={e => setLandPrice(e.target.value)}
                    placeholder="مثال: 7000"
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
