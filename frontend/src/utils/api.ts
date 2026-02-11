import type { LandObject, Overrides, ProFormaResult } from '../types'

const BASE = '/api'

async function json<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, opts)
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function fetchParcel(id: number): Promise<LandObject> {
  return json(`${BASE}/parcel/${id}`, { method: 'POST' })
}

export async function locateParcel(query: string): Promise<{ parcel_id: number; land_object: LandObject }> {
  return json(`${BASE}/locate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
}

export async function fetchProforma(
  id: number,
  overrides: Overrides = {},
): Promise<{ land_object: LandObject; proforma: ProFormaResult }> {
  return json(`${BASE}/proforma`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parcel_id: id, overrides }),
  })
}

export async function fetchScenarios(
  id: number,
  baseOverrides: Overrides,
  scenarios: { name: string; overrides: Overrides }[],
): Promise<{ land_object: LandObject; scenarios: { name: string; proforma: ProFormaResult }[] }> {
  return json(`${BASE}/proforma/scenario`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parcel_id: id, base_overrides: baseOverrides, scenarios }),
  })
}

export async function fetchAdvice(
  id: number,
  proforma: ProFormaResult | null,
  question: string,
): Promise<{ response: string }> {
  return json(`${BASE}/advisor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parcel_id: id, proforma, question }),
  })
}

export function getExcelUrl(id: number, params: Record<string, number>): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v != null) qs.set(k, String(v))
  }
  return `${BASE}/excel/${id}?${qs.toString()}`
}
