import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchProforma } from '../utils/api'
import type { Overrides } from '../types'

export function useProforma(parcelId: number | null, overrides: Overrides) {
  const [debouncedOverrides, setDebouncedOverrides] = useState(overrides)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebouncedOverrides(overrides), 500)
    return () => clearTimeout(timer.current)
  }, [overrides])

  return useQuery({
    queryKey: ['proforma', parcelId, debouncedOverrides],
    queryFn: () => fetchProforma(parcelId!, debouncedOverrides),
    enabled: !!parcelId,
    staleTime: 60_000,
  })
}
