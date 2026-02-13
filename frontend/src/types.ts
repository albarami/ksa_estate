export interface LandObject {
  parcel_id: number
  fetched_at: string
  parcel_number: string
  plan_number: string
  block_number: string
  object_id: number
  district_name: string
  municipality: string
  centroid: { lng: number; lat: number }
  geometry: { rings: number[][][] } | null
  area_sqm: number
  building_use_code: number
  building_code_label: string
  primary_use_code: number
  primary_use_label: string
  secondary_use_code: number
  detailed_use_code: number
  detailed_use_label: string
  reviewed_bld_code: number
  regulations: Regulations
  market: MarketData
  plan_info?: PlanInfo
  district_demographics?: DistrictDemographics
  data_sources?: Record<string, boolean>
  data_health: { fields_checked: number; fields_populated: number; score_pct: number }
}

export interface PlanInfo {
  plan_date_hijri?: string
  plan_year?: number
  plan_status?: string
  plan_use?: string
  plan_type?: string
}

export interface DistrictDemographics {
  population?: number
  population_density?: number
  area_m2?: number
  district_name_ar?: string
  district_name_en?: string
  district_code?: string
}

export interface Regulations {
  max_floors: number | null
  far: number | null
  coverage_ratio: number | null
  allowed_uses: string[]
  setbacks_raw?: string
  setback_values_m?: number[]
  notes?: string[]
}

export interface MarketData {
  srem_market_index: number | null
  srem_index_change: number | null
  daily_total_transactions: number | null
  daily_total_value_sar: number | null
  daily_avg_price_sqm: number | null
  trending_districts: { name: string; city: string; deals: number; total_sar: number }[]
  district?: DistrictMarket
}

export interface DistrictMarket {
  district_name?: string
  avg_price_sqm?: number | null
  total_deals?: number
  total_value?: number
  period?: string
  found?: boolean
  note?: string
  city_avg_price_sqm?: number
  index_history?: { date: string; index: number; change: number }[]
}

export interface ProFormaResult {
  inputs_used: Record<string, { value: unknown; source: string }>
  land_costs: Record<string, number>
  construction_costs: Record<string, number>
  revenue: { sellable_area_sqm: number; sale_price_per_sqm: number; gross_revenue: number; net_revenue: number }
  financing: Record<string, number | number[]>
  fund_fees: Record<string, number>
  fund_size: { total_fund_size: number; equity_amount: number; in_kind_contribution: number; bank_loan: number; equity_pct: number; debt_pct: number }
  cash_flows: CashFlows
  kpis: KPIs
  sensitivity: Sensitivity | null
  data_health: { auto: number; user: number; default: number; missing: number; total_params: number; confidence_pct: number; missing_fields: string[] }
}

export interface CashFlows {
  years: number[]
  inflows_sales: number[]
  outflows_land: number[]
  outflows_direct: number[]
  outflows_indirect: number[]
  outflows_interest: number[]
  outflows_fees: number[]
  outflows_total: number[]
  net_cash_flow: number[]
  cumulative: number[]
}

export interface KPIs {
  irr: number | null
  equity_net_profit: number
  roe_total: number
  roe_annualized: number
  profit_margin: number
  cost_to_revenue_ratio: number
  yield_on_cost: number
  // Intelligence metrics
  break_even_price_sqm?: number
  land_cost_per_gba?: number
  revenue_multiple?: number
  fund_overhead_ratio?: number
  deal_score?: number
  risk_flags?: string[]
}

export interface Sensitivity {
  sale_price_range: number[]
  construction_cost_range: number[]
  irr_matrix: (number | null)[][]
}

export interface Overrides {
  land_price_per_sqm?: number
  sale_price_per_sqm?: number
  infrastructure_cost_per_sqm?: number
  superstructure_cost_per_sqm?: number
  parking_area_sqm?: number
  fund_period_years?: number
  bank_ltv_pct?: number
  efficiency_ratio?: number
  [key: string]: unknown
}

// Re-export i18n types for convenience
export type { Labels, Lang } from './utils/i18n'

export interface MapMarker {
  lng: number
  lat: number
  label: string
  value: number
}
