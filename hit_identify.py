"""Try every approach to hit the MapServer identify endpoint."""

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

# Parcel 3710897 centroid
LNG = 46.61328
LAT = 24.81573

# ArcGIS servers discovered in captured data
ARCGIS_SERVERS = [
    "https://maps.alriyadh.gov.sa/gprtl/rest/services/WebMercator/WMParcelsLayerOne/MapServer",
    "https://maps.alriyadh.gov.sa/geomap_ex_p/rest/services/Riyadh/Riyadh2023/MapServer",
]

OUT = Path("arcgis_token_investigation.json")


async def main():
    results = {"attempts": [], "token_generation": [], "layer_info": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)

        # Authenticate to get JWT
        r = await ctx.request.post(
            f"{API_BASE}/api/login/authenticate",
            headers={**HEADERS, "Content-Type": "application/json"},
            data=json.dumps(AUTH),
        )
        auth_data = json.loads(await r.text())
        jwt = auth_data.get("TOKEN", "")
        print(f"JWT acquired: {jwt[:40]}...")

        # --- Attempt 1: Identify through proxy (how the app does it) ---
        for server in ARCGIS_SERVERS:
            identify_params = (
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

            proxy_url = f"{PROXY}?{server}/identify{identify_params}"
            print(f"\nAttempt: PROXY identify on {server.split('/')[-1]}")
            try:
                resp = await ctx.request.get(proxy_url, headers=HEADERS, timeout=15_000)
                text = await resp.text()
                print(f"  Status: {resp.status}, Length: {len(text)}")
                print(f"  Preview: {text[:500]}")
                results["attempts"].append({
                    "method": "proxy_identify",
                    "server": server,
                    "url": proxy_url[:300],
                    "status": resp.status,
                    "length": len(text),
                    "response": text[:5000],
                })
            except Exception as exc:
                print(f"  Failed: {exc}")

        # --- Attempt 2: Query with more fields (we know query works) ---
        query_url = (
            f"{PROXY}?{ARCGIS_SERVERS[0]}/2/query"
            f"?where=PARCELID=3710897"
            f"&returnGeometry=true"
            f"&outFields=*"
            f"&outSR=4326"
            f"&f=json"
        )
        print("\nAttempt: Full query with outFields=*")
        try:
            resp = await ctx.request.get(query_url, headers=HEADERS, timeout=15_000)
            text = await resp.text()
            # Strip JSONP if present
            if text.startswith("window.") or text.startswith("callback"):
                start = text.index("{")
                end = text.rindex("}") + 1
                text = text[start:end]
            print(f"  Status: {resp.status}, Length: {len(text)}")
            data = json.loads(text)
            if data.get("features"):
                attrs = data["features"][0].get("attributes", {})
                print(f"  Fields returned ({len(attrs)}):")
                for k, v in attrs.items():
                    print(f"    {k}: {v}")
            results["attempts"].append({
                "method": "query_all_fields",
                "status": resp.status,
                "response": text[:5000],
            })
        except Exception as exc:
            print(f"  Failed: {exc}")

        # --- Attempt 3: Check for other layers on the MapServer ---
        for server in ARCGIS_SERVERS:
            info_url = f"{PROXY}?{server}?f=json"
            print(f"\nAttempt: MapServer info for {server.split('/')[-1]}")
            try:
                resp = await ctx.request.get(info_url, headers=HEADERS, timeout=15_000)
                text = await resp.text()
                print(f"  Status: {resp.status}, Length: {len(text)}")
                try:
                    info = json.loads(text)
                    layers = info.get("layers", [])
                    print(f"  Layers ({len(layers)}):")
                    for layer in layers:
                        print(f"    [{layer.get('id')}] {layer.get('name')}")
                    results["layer_info"].append({
                        "server": server,
                        "layers": layers,
                        "full_response": text[:3000],
                    })
                except json.JSONDecodeError:
                    print(f"  Not JSON: {text[:300]}")
            except Exception as exc:
                print(f"  Failed: {exc}")

        # --- Attempt 4: Try ArcGIS token generation endpoints ---
        token_endpoints = [
            f"https://maps.alriyadh.gov.sa/gprtl/tokens/generateToken",
            f"https://maps.alriyadh.gov.sa/gprtl/rest/generateToken",
            f"https://maps.alriyadh.gov.sa/portal/sharing/rest/generateToken",
            f"https://maps.alriyadh.gov.sa/gprtl/sharing/rest/generateToken",
        ]
        for te in token_endpoints:
            print(f"\nAttempt: Generate token at {te}")
            try:
                resp = await ctx.request.post(
                    te,
                    headers=HEADERS,
                    form={
                        "username": "public",
                        "password": "public",
                        "client": "referer",
                        "referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap",
                        "f": "json",
                    },
                    timeout=10_000,
                )
                text = await resp.text()
                print(f"  Status: {resp.status}, Length: {len(text)}")
                print(f"  Response: {text[:500]}")
                results["token_generation"].append({
                    "url": te,
                    "status": resp.status,
                    "response": text[:2000],
                })
            except Exception as exc:
                print(f"  Failed: {exc}")

        # --- Attempt 5: Try MapServer info endpoint on gprtl ---
        # Check the full service directory
        svc_url = f"{PROXY}?https://maps.alriyadh.gov.sa/gprtl/rest/services?f=json"
        print(f"\nAttempt: Service directory")
        try:
            resp = await ctx.request.get(svc_url, headers=HEADERS, timeout=15_000)
            text = await resp.text()
            print(f"  Status: {resp.status}, Length: {len(text)}")
            print(f"  Preview: {text[:1000]}")
            results["attempts"].append({
                "method": "service_directory",
                "status": resp.status,
                "response": text[:5000],
            })
        except Exception as exc:
            print(f"  Failed: {exc}")

        await browser.close()

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {OUT}")


asyncio.run(main())
