import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchProforma } from '../utils/api'
import type { Overrides } from '../types'

export function useProforma(parcelId: number | null, overrides: Overrides) {
  const [debouncedOverrides, setDebouncedOverrides] = useState(overrides)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Debounce override changes by 500ms
  const serialized = JSON.stringify(overrides)
  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebouncedOverrides(JSON.parse(serialized)), 500)
    return () => clearTimeout(timer.current)
  }, [serialized])

  const debouncedKey = JSON.stringify(debouncedOverrides)

  return useQuery({
    queryKey: ['proforma', parcelId, debouncedKey],
    queryFn: () => fetchProforma(parcelId!, debouncedOverrides),
    enabled: !!parcelId,
    staleTime: 30_000,
    refetchOnMount: false,
  })
}
