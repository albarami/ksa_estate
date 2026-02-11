import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { MapMarker } from '../types'

interface Props {
  rings: number[][][] | undefined
  markers?: MapMarker[]
}

export default function MapCard({ rings, markers }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [46.68, 24.71],
      zoom: 10,
      attributionControl: false,
    })
    mapRef.current = map

    map.on('load', () => {
      // Add parcel polygon
      if (rings && rings.length > 0) {
        map.addSource('parcel', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: { type: 'Polygon', coordinates: rings },
          },
        })

        map.addLayer({
          id: 'parcel-fill',
          type: 'fill',
          source: 'parcel',
          paint: { 'fill-color': '#D4A843', 'fill-opacity': 0.3 },
        })

        map.addLayer({
          id: 'parcel-border',
          type: 'line',
          source: 'parcel',
          paint: { 'line-color': '#D4A843', 'line-width': 2 },
        })

        // Fit bounds
        const coords = rings[0]
        const lngs = coords.map(c => c[0])
        const lats = coords.map(c => c[1])
        map.fitBounds(
          [[Math.min(...lngs) - 0.002, Math.min(...lats) - 0.002],
           [Math.max(...lngs) + 0.002, Math.max(...lats) + 0.002]],
          { padding: 60, duration: 1000 }
        )
      }
    })

    return () => { map.remove(); mapRef.current = null }
  }, [rings])

  // v2: Add transaction markers when provided
  useEffect(() => {
    const map = mapRef.current
    if (!map || !markers || markers.length === 0) return

    const onLoad = () => {
      if (map.getSource('markers')) {
        (map.getSource('markers') as maplibregl.GeoJSONSource).setData({
          type: 'FeatureCollection',
          features: markers.map(m => ({
            type: 'Feature' as const,
            properties: { label: m.label, value: m.value },
            geometry: { type: 'Point' as const, coordinates: [m.lng, m.lat] },
          })),
        })
      } else {
        map.addSource('markers', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: markers.map(m => ({
              type: 'Feature' as const,
              properties: { label: m.label, value: m.value },
              geometry: { type: 'Point' as const, coordinates: [m.lng, m.lat] },
            })),
          },
        })
        map.addLayer({
          id: 'marker-dots',
          type: 'circle',
          source: 'markers',
          paint: { 'circle-radius': 5, 'circle-color': '#D4A843', 'circle-stroke-width': 1, 'circle-stroke-color': '#fff' },
        })
      }
    }

    if (map.loaded()) onLoad()
    else map.on('load', onLoad)
  }, [markers])

  return (
    <div className="rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)]">
      <div ref={containerRef} className="w-full h-[320px]" />
    </div>
  )
}
