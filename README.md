# KSA Estate — Riyadh Geoportal Network Capture

Playwright script that reverse-engineers the backend API of the Riyadh Municipality
geoportal map by intercepting all network traffic when a user clicks on a parcel
and when loading a direct parcel-ID URL.

## Prerequisites

- Python 3.11+
- Network access to `mapservice.alriyadh.gov.sa`

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python capture_map_requests.py
```

The script runs two capture approaches:

**Approach A — Map Click:**
1. Opens the geoportal map at `https://mapservice.alriyadh.gov.sa/geoportal/geomap`
2. Auto-detects the map framework (ArcGIS, Leaflet, OpenLayers, Angular, or iframe)
3. Zooms to target coordinates (24.8256, 46.6526 — Al-Hada district)
4. Clicks the map canvas at that location
5. Captures all API calls that fire after the click

**Approach B — Direct Parcel URL:**
6. Navigates to `https://mapservice.alriyadh.gov.sa/geoportal/?parcelid=3710897`
7. Captures all API calls that fire when loading a known parcel ID

## Output Files

| File | Description |
|---|---|
| `geoportal_captured.json` | All network traffic, tagged by phase |
| `screenshots/` | Timestamped screenshots at each stage |

## Analyzing Results

Search for responses containing Arabic parcel field names:

```bash
python -c "
import json
data = json.load(open('geoportal_captured.json', encoding='utf-8'))
for r in data['requests']:
    if r.get('contains_arabic_fields'):
        print(f\"Phase: {r['phase']}\")
        print(f\"URL: {r['url'][:150]}\")
        print(f\"Fields: {r['contains_arabic_fields']}\")
        print('---')
"
```

The script automatically scans for these Arabic field names:
نظام البناء، شروط البناء، استعمال الأرض، رقم المخطط، رقم القطعة،
الارتداد، عدد الأدوار، نسبة البناء، الاستعمال

## Configuration

| Constant | Default | Description |
|---|---|---|
| `TARGET_URL` | `https://mapservice.alriyadh.gov.sa/geoportal/geomap` | Map portal URL |
| `PARCEL_URL` | `https://.../?parcelid=3710897` | Direct parcel lookup URL |
| `TARGET_LAT` | `24.8256` | Latitude (Al-Hada district) |
| `TARGET_LNG` | `46.6526` | Longitude |
| `POST_CLICK_WAIT_S` | `10` | Seconds to wait for API responses |
| `MAP_LOAD_TIMEOUT_MS` | `90000` | Max wait for map readiness (ms) |
