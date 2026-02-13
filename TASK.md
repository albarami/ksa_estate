# Market Intelligence Layer

## Completed

- [x] Add `_fetch_srem_district()` to `backend/srem_client.py` with city/district filtering and fallback
- [x] Enhance Land Object with `district_data` in market section (`data_fetch_http.py`)
- [x] Add `deal_score`, `break_even_price`, `land_cost_per_gba`, `risk_flags` to `computation_engine.py` output
- [x] Show SREM district data on IntakeFlow confirmation screen + pre-fill sale price
- [x] Create `MarketIntelligence.tsx` dashboard card with deal score, comps, risks
- [x] Create `DistrictCard.tsx` with plan info, demographics, index sparkline, data sources
- [x] Multi-source fallbacks for all critical parcel fields (Query -> Identify)
- [x] Extract SREM logic into `backend/srem_client.py` (keep `data_fetch_http.py` under 500 lines)
- [x] Parse Geoportal Layer 3 (plan status/use/type/date) with scale-dependent retry
- [x] Parse Geoportal Layer 4 (district population/area/name) with wider extent retry
- [x] Add `data_sources` tracker to Land Object for transparency
- [x] Update `types.ts` with `PlanInfo`, `DistrictDemographics`, `DistrictMarket`, KPI intelligence fields
- [x] Test with Al-Malqa parcel (3710897) — all 7 sources active, 100% health

## Pending

- [ ] Test with Al-Aarid (العارض) parcel
- [ ] End-to-end browser test of IntakeFlow with .docx upload showing market context

## Discovered During Work

- Geoportal Layer 4 (districts) requires separate identify call with 0.1-degree extent — doesn't return in same call as Layer 2/2222
- SREM trending districts only shows top ~5 nationally — most districts fall back to Riyadh city average
- Identify layer 2222 field names are Arabic (`رقم القطعة`) vs Query layer 2 English (`PARCELNO`) — both needed for cross-source fallback
