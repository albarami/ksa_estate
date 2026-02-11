import { motion } from 'framer-motion'
import type { LandObject, ProFormaResult, Overrides, Labels, Lang } from '../types'
import TopBar from './TopBar'
import MapCard from './MapCard'
import ZoningCard from './ZoningCard'
import FinancialSummary from './FinancialSummary'
import AssumptionsPanel from './AssumptionsPanel'
import CashFlowChart from './CashFlowChart'
import SensitivityHeatmap from './SensitivityHeatmap'
import ScenarioComparison from './ScenarioComparison'
import AdvisorPanel from './AdvisorPanel'
import DownloadBar from './DownloadBar'

interface Props {
  land: LandObject
  proforma: ProFormaResult
  overrides: Overrides
  onOverridesChange: (o: Overrides) => void
  labels: Labels
  lang: Lang
  onLangToggle: () => void
  onNewSearch: () => void
  isRecalculating: boolean
}

export default function Dashboard({
  land, proforma, overrides, onOverridesChange,
  labels, lang, onLangToggle, onNewSearch, isRecalculating,
}: Props) {
  return (
    <div className="min-h-screen pb-20">
      <TopBar
        land={land}
        labels={labels}
        lang={lang}
        onLangToggle={onLangToggle}
        onNewSearch={onNewSearch}
      />

      {isRecalculating && (
        <div className="h-0.5 bg-[var(--color-gold)] animate-pulse" />
      )}

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-5 gap-4"
      >
        {/* Left column */}
        <div className="lg:col-span-2 space-y-4">
          <MapCard rings={land.geometry?.rings} />
          <ZoningCard
            regulations={land.regulations}
            buildingCode={land.building_code_label}
            areaSqm={land.area_sqm}
            labels={labels}
          />
        </div>

        {/* Right column */}
        <div className="lg:col-span-3 space-y-4">
          <FinancialSummary
            kpis={proforma.kpis}
            fundSize={proforma.fund_size.total_fund_size}
            equity={proforma.fund_size.equity_amount}
            labels={labels}
          />

          <AssumptionsPanel
            overrides={overrides}
            onChange={onOverridesChange}
            labels={labels}
          />

          <CashFlowChart cashFlows={proforma.cash_flows} labels={labels} />

          {proforma.sensitivity && (
            <SensitivityHeatmap sensitivity={proforma.sensitivity} labels={labels} />
          )}

          <ScenarioComparison
            parcelId={land.parcel_id}
            baseOverrides={overrides}
            labels={labels}
          />

          <AdvisorPanel
            parcelId={land.parcel_id}
            proforma={proforma}
            labels={labels}
          />
        </div>
      </motion.div>

      <DownloadBar parcelId={land.parcel_id} overrides={overrides} labels={labels} />
    </div>
  )
}
