import { useState, useCallback } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ParcelInput from './components/ParcelInput'
import LoadingProgress from './components/LoadingProgress'
import IntakeFlow from './components/IntakeFlow'
import Dashboard from './components/Dashboard'
import { useProforma } from './hooks/useProforma'
import { getLabels } from './utils/i18n'
import type { LandObject, ProFormaResult, Overrides } from './types'
import type { Lang } from './utils/i18n'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

// Defaults — financial assumptions only. Zoning (FAR) comes from parcel.
const DEFAULT_OVERRIDES: Overrides = {
  land_price_per_sqm: 7000,
  sale_price_per_sqm: 12500,
  infrastructure_cost_per_sqm: 500,
  superstructure_cost_per_sqm: 2500,
  parking_area_sqm: 0,
  parking_cost_per_sqm: 2000,
  in_kind_pct: 0,
  fund_period_years: 3,
  bank_ltv_pct: 0.667,
  interest_rate_pct: 0.08,
  efficiency_ratio: 1.0,
}

type Screen = 'input' | 'loading' | 'intake' | 'dashboard'

function AppInner() {
  const [screen, setScreen] = useState<Screen>('input')
  const [lang, setLang] = useState<Lang>('ar')
  const [parcelId, setParcelId] = useState<number | null>(null)
  const [land, setLand] = useState<LandObject | null>(null)
  const [initialProforma, setInitialProforma] = useState<ProFormaResult | null>(null)
  const [overrides, setOverrides] = useState<Overrides>({ ...DEFAULT_OVERRIDES })
  const [inputQuery, setInputQuery] = useState<string>('')

  const labels = getLabels(lang)

  // Live recalculation: fires whenever overrides change AND we have a parcelId
  const proformaQuery = useProforma(
    screen === 'dashboard' && parcelId ? parcelId : null,
    overrides,
  )

  // Use live proforma if available, otherwise initial from loading step
  const liveProforma = proformaQuery.data?.proforma ?? initialProforma

  const handleSubmit = useCallback((query: string) => {
    setInputQuery(query)
    const asNum = parseInt(query)
    if (!isNaN(asNum) && String(asNum) === query.trim()) {
      setParcelId(asNum)
    } else {
      setParcelId(null) // will be resolved by LoadingProgress
    }
    setScreen('loading')
  }, [])

  const handleLoadComplete = useCallback((l: LandObject, pf: ProFormaResult) => {
    setLand(l)
    setInitialProforma(pf)
    setParcelId(l.parcel_id)
    // Seed overrides from actual parcel data — no hardcoding
    const districtAvg = l.market?.district?.avg_price_sqm
    setOverrides(prev => ({
      ...prev,
      far: l.regulations?.far ?? prev.far,
      // Only use district price if it's a real per-m² price (>500 = real residential land)
      sale_price_per_sqm: districtAvg && districtAvg > 500 ? districtAvg : prev.sale_price_per_sqm,
    }))
    setScreen('dashboard')
  }, [])

  const handleError = useCallback((msg: string) => {
    alert(msg)
    setScreen('input')
  }, [])

  const handleNewSearch = useCallback(() => {
    setScreen('input')
    setParcelId(null)
    setLand(null)
    setInitialProforma(null)
    setOverrides({ ...DEFAULT_OVERRIDES })
  }, [])

  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  return (
    <div dir={dir} className="min-h-screen">
      {screen === 'input' && (
        <button
          onClick={() => setLang(l => l === 'ar' ? 'en' : 'ar')}
          className="fixed top-4 left-4 z-50 px-3 py-1 rounded border border-[var(--color-border)] text-sm hover:border-[var(--color-gold)] transition-colors"
        >
          {lang === 'ar' ? 'EN' : 'AR'}
        </button>
      )}

      {screen === 'input' && (
        <ParcelInput
          labels={labels}
          onSubmit={handleSubmit}
          onUpload={() => setScreen('intake')}
        />
      )}

      {screen === 'intake' && (
        <IntakeFlow
          labels={labels}
          onComplete={(l, pf, ov) => {
            setLand(l)
            setInitialProforma(pf)
            setParcelId(l.parcel_id || null)
            setOverrides(ov)
            setScreen('dashboard')
          }}
          onCancel={() => setScreen('input')}
        />
      )}

      {screen === 'loading' && (
        <LoadingProgress
          parcelId={parcelId}
          query={parcelId ? undefined : inputQuery}
          overrides={overrides}
          labels={labels}
          onComplete={handleLoadComplete}
          onError={handleError}
        />
      )}

      {screen === 'dashboard' && land && liveProforma && (
        <Dashboard
          land={land}
          proforma={liveProforma}
          overrides={overrides}
          onOverridesChange={setOverrides}
          labels={labels}
          lang={lang}
          onLangToggle={() => setLang(l => l === 'ar' ? 'en' : 'ar')}
          onNewSearch={handleNewSearch}
          isRecalculating={proformaQuery.isFetching}
        />
      )}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  )
}
