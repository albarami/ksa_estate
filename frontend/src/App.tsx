import { useState, useCallback } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ParcelInput from './components/ParcelInput'
import LoadingProgress from './components/LoadingProgress'
import Dashboard from './components/Dashboard'
import { useProforma } from './hooks/useProforma'
import { getLabels } from './utils/i18n'
import type { LandObject, ProFormaResult, Overrides } from './types'
import type { Lang } from './utils/i18n'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

type Screen = 'input' | 'loading' | 'dashboard'

function AppInner() {
  const [screen, setScreen] = useState<Screen>('input')
  const [lang, setLang] = useState<Lang>('ar')
  const [parcelId, setParcelId] = useState<number | null>(null)
  const [land, setLand] = useState<LandObject | null>(null)
  const [proforma, setProforma] = useState<ProFormaResult | null>(null)
  const [overrides, setOverrides] = useState<Overrides>({
    land_price_per_sqm: 5000,
    sale_price_per_sqm: 8000,
    infrastructure_cost_per_sqm: 500,
    superstructure_cost_per_sqm: 2500,
    fund_period_years: 3,
    bank_ltv_pct: 0.667,
  })

  const labels = getLabels(lang)

  // Live recalculation when overrides change
  const proformaQuery = useProforma(
    screen === 'dashboard' ? parcelId : null,
    overrides,
  )

  // Use fresh proforma from query if available
  const liveProforma = proformaQuery.data?.proforma ?? proforma

  const [inputQuery, setInputQuery] = useState<string>('')

  const handleSubmit = useCallback((query: string) => {
    setInputQuery(query)
    // If it's a plain number, use it directly as parcel ID
    const asNum = parseInt(query)
    if (!isNaN(asNum) && String(asNum) === query.trim()) {
      setParcelId(asNum)
      setScreen('loading')
    } else {
      // It's a URL or coordinates — use the locate endpoint
      setScreen('loading')
      setParcelId(null)  // will be resolved by LoadingProgress
    }
  }, [])

  const handleLoadComplete = useCallback((l: LandObject, pf: ProFormaResult) => {
    setLand(l)
    setProforma(pf)
    setScreen('dashboard')
  }, [])

  const handleError = useCallback((msg: string) => {
    alert(`Error: ${msg}`)
    setScreen('input')
  }, [])

  const handleNewSearch = useCallback(() => {
    setScreen('input')
    setParcelId(null)
    setLand(null)
    setProforma(null)
  }, [])

  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  return (
    <div dir={dir} className="min-h-screen">
      {/* Language toggle on input screen */}
      {screen === 'input' && (
        <button
          onClick={() => setLang(l => l === 'ar' ? 'en' : 'ar')}
          className="fixed top-4 left-4 z-50 px-3 py-1 rounded border border-[var(--color-border)] text-sm hover:border-[var(--color-gold)] transition-colors"
        >
          {lang === 'ar' ? 'EN' : 'AR'}
        </button>
      )}

      {screen === 'input' && (
        <ParcelInput labels={labels} onSubmit={handleSubmit} />
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
