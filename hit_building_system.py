"""Hit the three newly discovered building system endpoints."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

API_BASE = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN"
PROXY = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN/Handler/proxy.ashx"
API_KEY = "pG5Zbm/s7HxZw0tUTEk71CyqUPRpjQ+1bwK2mbcodH/ume0CYgMZNLzdODAclzfFUT8cf7+ngea7co1U4uCaWSCPuJXEqapZGCoO3Ep3AEg="
AUTH = {
    "appid": "1",
    "username": "kduwGS/eGGSXMz5NkcS/qDFqAZZemcyEL9u7mEcifV2WAFVocT4ezes5ckYEGdxJ",
    "password": "ZhENHqcK6xSu3tZgbAL2kDgeG0Jd6jxGmHtOvZPJOwXsayGvxI/z0rIqUZrbrz8B",
}
HEADERS = {
    "Referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap",
    "Origin": "https://mapservice.alriyadh.gov.sa",
    "apikey": API_KEY,
}
PARCEL_ID = 3710897
LNG, LAT = 46.61328, 24.81573
OUT = Path("building_system_results.json")


async def main():
    results: dict = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)

        # Auth for JWT (needed for some endpoints)
        r = await ctx.request.post(
            f"{API_BASE}/api/login/authenticate",
            headers={**HEADERS, "Content-Type": "application/json"},
            data=json.dumps(AUTH),
        )
        auth = json.loads(await r.text())
        jwt = auth.get("TOKEN", "")
        auth_headers = {**HEADERS, "Authorization": f"Bearer {jwt}"}

        # === 1. BuildingSystem PDF report ===
        pdf_url = f"https://mapservice.alriyadh.gov.sa/BuildingSystem/building-code-report-experimental?parcelId={PARCEL_ID}"
        print(f"1. Building code report PDF: {pdf_url}")
        for label, hdrs in [("no_auth", HEADERS), ("with_jwt", auth_headers)]:
            try:
                r = await ctx.request.get(pdf_url, headers=hdrs, timeout=30_000)
                body = await r.body()
                ct = dict(await r.headers_array()).get("content-type", "unknown")
                print(f"   [{label}] Status: {r.status}, Size: {len(body)}, Type: {ct}")
                results[f"pdf_report_{label}"] = {
                    "status": r.status,
                    "size": len(body),
                    "content_type": ct,
                }
                if r.status == 200 and len(body) > 1000:
                    fname = f"building_code_report_{PARCEL_ID}_{label}.pdf"
                    Path(fname).write_bytes(body)
                    print(f"   SAVED: {fname}")
                    results[f"pdf_report_{label}"]["saved_as"] = fname
                elif len(body) < 2000:
                    text = body.decode("utf-8", errors="replace")
                    print(f"   Body: {text[:500]}")
                    results[f"pdf_report_{label}"]["body_text"] = text[:2000]
            except Exception as exc:
                print(f"   [{label}] Failed: {exc}")

        # === 2. BuildingGuide API ===
        guide_url = f"{API_BASE}/api/Public/BuildingGuide?parcelid={PARCEL_ID}&url=https://mapservice.alriyadh.gov.sa/"
        print(f"\n2. BuildingGuide API: {guide_url}")
        for label, hdrs in [("no_auth", HEADERS), ("with_jwt", auth_headers)]:
            try:
                r = await ctx.request.get(guide_url, headers=hdrs, timeout=15_000)
                text = await r.text()
                print(f"   [{label}] Status: {r.status}, Length: {len(text)}")
                print(f"   Response: {text[:500]}")
                results[f"building_guide_{label}"] = {
                    "status": r.status,
                    "response": text[:3000],
                }
            except Exception as exc:
                print(f"   [{label}] Failed: {exc}")

        # === 3. PBuildingSystem MapServer ===
        bld_server = "https://maps.alriyadh.gov.sa/geomap_ex_p/rest/services/GeoPortal/PBuildingSystem/MapServer"
        print(f"\n3. PBuildingSystem MapServer info")

        # Info
        info_url = f"{PROXY}?{bld_server}?f=json"
        try:
            r = await ctx.request.get(info_url, headers=HEADERS, timeout=15_000)
            text = await r.text()
            print(f"   Info status: {r.status}, Length: {len(text)}")
            data = json.loads(text)
            results["pbuildingsystem_info"] = data
            layers = data.get("layers", [])
            print(f"   Layers: {len(layers)}")
            for lyr in layers:
                print(f"     [{lyr.get('id')}] {lyr.get('name')}")
        except Exception as exc:
            print(f"   Info failed: {exc}")

        # Identify on PBuildingSystem
        identify_url = (
            f"{PROXY}?{bld_server}/identify"
            f"?geometry={LNG},{LAT}"
            f"&geometryType=esriGeometryPoint"
            f"&sr=4326&tolerance=10"
            f"&mapExtent={LNG-0.002},{LAT-0.002},{LNG+0.002},{LAT+0.002}"
            f"&imageDisplay=1440,900,96"
            f"&layers=all&returnGeometry=false&f=json"
        )
        print(f"\n   Identify on PBuildingSystem...")
        try:
            r = await ctx.request.get(identify_url, headers=HEADERS, timeout=15_000)
            text = await r.text()
            print(f"   Status: {r.status}, Length: {len(text)}")
            data = json.loads(text)
            results["pbuildingsystem_identify"] = data
            for res in data.get("results", []):
                layer = res.get("layerName", "?")
                attrs = res.get("attributes", {})
                print(f"   Layer: {layer} ({len(attrs)} fields)")
                for k, v in attrs.items():
                    print(f"     {k}: {v}")
        except Exception as exc:
            print(f"   Identify failed: {exc}")

        # Query layer 0 on PBuildingSystem for parcel
        for layer_id in [0, 1, 2]:
            q_url = (
                f"{PROXY}?{bld_server}/{layer_id}/query"
                f"?where=1=1"
                f"&geometry={LNG},{LAT}"
                f"&geometryType=esriGeometryPoint"
                f"&spatialRel=esriSpatialRelIntersects"
                f"&outFields=*&returnGeometry=false&f=json"
            )
            print(f"\n   Query PBuildingSystem layer {layer_id}...")
            try:
                r = await ctx.request.get(q_url, headers=HEADERS, timeout=15_000)
                text = await r.text()
                print(f"   Status: {r.status}, Length: {len(text)}")
                if r.status == 200 and len(text) > 100:
                    data = json.loads(text)
                    results[f"pbuildingsystem_query_layer{layer_id}"] = data
                    for feat in data.get("features", []):
                        attrs = feat.get("attributes", {})
                        print(f"   Feature ({len(attrs)} fields):")
                        for k, v in attrs.items():
                            print(f"     {k}: {v}")
            except Exception as exc:
                print(f"   Query failed: {exc}")

        await browser.close()

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {OUT}")


asyncio.run(main())
