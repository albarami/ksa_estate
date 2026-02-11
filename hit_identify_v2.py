"""Focused: hit identify + explore layers, write everything to file."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

PROXY = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN/Handler/proxy.ashx"
API_BASE = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN"
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
LNG, LAT = 46.61328, 24.81573
PARCELS_SERVER = "https://maps.alriyadh.gov.sa/gprtl/rest/services/WebMercator/WMParcelsLayerOne/MapServer"
OUT = Path("arcgis_token_investigation.json")


async def main():
    results: dict = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)

        # NOTE: Do NOT add JWT Authorization header — the proxy passes it
        # to ArcGIS which rejects it as "Invalid Token". The proxy handles
        # auth server-side based on the Referer header alone.

        # 1. MapServer layer listing
        info_url = f"{PROXY}?{PARCELS_SERVER}?f=json"
        resp = await ctx.request.get(info_url, headers=HEADERS, timeout=15_000)
        results["parcels_mapserver_info"] = json.loads(await resp.text())

        # 2. Identify on WMParcelsLayerOne
        identify_url = (
            f"{PROXY}?{PARCELS_SERVER}/identify"
            f"?geometry={LNG},{LAT}"
            f"&geometryType=esriGeometryPoint"
            f"&sr=4326"
            f"&tolerance=10"
            f"&mapExtent={LNG-0.002},{LAT-0.002},{LNG+0.002},{LAT+0.002}"
            f"&imageDisplay=1440,900,96"
            f"&layers=all"
            f"&returnGeometry=true"
            f"&f=json"
        )
        resp = await ctx.request.get(identify_url, headers=HEADERS, timeout=15_000)
        results["identify_all_layers"] = json.loads(await resp.text())

        # 3. Also try identify on specific layers (0, 1, 2)
        for layer_id in [0, 1, 2, 3, 4, 5]:
            url = (
                f"{PROXY}?{PARCELS_SERVER}/identify"
                f"?geometry={LNG},{LAT}"
                f"&geometryType=esriGeometryPoint"
                f"&sr=4326"
                f"&tolerance=10"
                f"&mapExtent={LNG-0.002},{LAT-0.002},{LNG+0.002},{LAT+0.002}"
                f"&imageDisplay=1440,900,96"
                f"&layers=all:{layer_id}"
                f"&returnGeometry=false"
                f"&f=json"
            )
            resp = await ctx.request.get(url, headers=HEADERS, timeout=15_000)
            results[f"identify_layer_{layer_id}"] = json.loads(await resp.text())

        # 4. Query each layer for field names
        for layer_id in range(15):
            url = (
                f"{PROXY}?{PARCELS_SERVER}/{layer_id}"
                f"?f=json"
            )
            try:
                resp = await ctx.request.get(url, headers=HEADERS, timeout=10_000)
                text = await resp.text()
                if resp.status == 200 and text.startswith("{"):
                    layer_info = json.loads(text)
                    results[f"layer_{layer_id}_info"] = {
                        "name": layer_info.get("name"),
                        "type": layer_info.get("type"),
                        "fields": [
                            {"name": f["name"], "alias": f.get("alias"), "type": f.get("type")}
                            for f in layer_info.get("fields", [])
                        ],
                    }
            except Exception:
                pass

        # 5. Explore the service directory folders
        for folder in ["WebMercator", "GeoPortal", "geoprtl"]:
            url = f"{PROXY}?https://maps.alriyadh.gov.sa/gprtl/rest/services/{folder}?f=json"
            try:
                resp = await ctx.request.get(url, headers=HEADERS, timeout=10_000)
                text = await resp.text()
                if resp.status == 200:
                    results[f"folder_{folder}"] = json.loads(text)
            except Exception:
                pass

        await browser.close()

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {OUT}")
    # Print summary safely
    identify = results.get("identify_all_layers", {})
    n_results = len(identify.get("results", []))
    print(f"Identify all layers: {n_results} results")
    for i, res in enumerate(identify.get("results", [])):
        layer = res.get("layerName", "?")
        attrs = res.get("attributes", {})
        print(f"  Result {i}: layer={layer}, fields={len(attrs)}")

    info = results.get("parcels_mapserver_info", {})
    layers = info.get("layers", [])
    print(f"MapServer layers: {len(layers)}")
    for lyr in layers:
        print(f"  [{lyr.get('id')}] {lyr.get('name')}")


asyncio.run(main())
