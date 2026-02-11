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
  const sourceAdded = useRef(false)

  // Initialize map once
  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [46.68, 24.71],
      zoom: 10,
      attributionControl: false,
    })
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      sourceAdded.current = false
    }
  }, [])

  // Add/update polygon when rings change or map loads
  useEffect(() => {
    const map = mapRef.current
    if (!map || !rings || rings.length === 0) return

    const addPolygon = () => {
      const geojson: GeoJSON.Feature = {
        type: 'Feature',
        properties: {},
        geometry: { type: 'Polygon', coordinates: rings },
      }

      if (sourceAdded.current) {
        const src = map.getSource('parcel') as maplibregl.GeoJSONSource
        if (src) src.setData(geojson)
      } else {
        map.addSource('parcel', { type: 'geojson', data: geojson })
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
          paint: { 'line-color': '#D4A843', 'line-width': 2.5 },
        })
        sourceAdded.current = true
      }

      // Fit bounds to polygon
      const coords = rings[0]
      const lngs = coords.map(c => c[0])
      const lats = coords.map(c => c[1])
      map.fitBounds(
        [[Math.min(...lngs) - 0.001, Math.min(...lats) - 0.001],
         [Math.max(...lngs) + 0.001, Math.max(...lats) + 0.001]],
        { padding: 80, duration: 1200 }
      )
    }

    if (map.isStyleLoaded()) {
      addPolygon()
    } else {
      map.on('load', addPolygon)
    }
  }, [rings])

  // v2: markers
  useEffect(() => {
    const map = mapRef.current
    if (!map || !markers || markers.length === 0) return

    const add = () => {
      const data: GeoJSON.FeatureCollection = {
        type: 'FeatureCollection',
        features: markers.map(m => ({
          type: 'Feature' as const,
          properties: { label: m.label, value: m.value },
          geometry: { type: 'Point' as const, coordinates: [m.lng, m.lat] },
        })),
      }

      if (map.getSource('markers')) {
        (map.getSource('markers') as maplibregl.GeoJSONSource).setData(data)
      } else {
        map.addSource('markers', { type: 'geojson', data })
        map.addLayer({
          id: 'marker-dots',
          type: 'circle',
          source: 'markers',
          paint: { 'circle-radius': 5, 'circle-color': '#D4A843', 'circle-stroke-width': 1, 'circle-stroke-color': '#fff' },
        })
      }
    }

    if (map.isStyleLoaded()) add()
    else map.on('load', add)
  }, [markers])

  return (
    <div className="rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)]">
      <div ref={containerRef} className="w-full h-[320px]" />
    </div>
  )
}
