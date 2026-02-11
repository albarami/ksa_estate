import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchProforma } from '../utils/api'
import type { Overrides } from '../types'

export function useProforma(parcelId: number | null, overrides: Overrides) {
  // Serialize for stable comparison
  const serialized = JSON.stringify(overrides)
  const [debouncedKey, setDebouncedKey] = useState(serialized)
  const [debouncedOverrides, setDebouncedOverrides] = useState(overrides)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    // If same serialized value, skip
    if (serialized === debouncedKey) return

    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      setDebouncedKey(serialized)
      setDebouncedOverrides(JSON.parse(serialized))
    }, 400)

    return () => clearTimeout(timer.current)
  }, [serialized, debouncedKey])

  return useQuery({
    queryKey: ['proforma', parcelId, debouncedKey],
    queryFn: () => fetchProforma(parcelId!, debouncedOverrides),
    enabled: parcelId != null && parcelId > 0,
    staleTime: 10_000,
  })
}
