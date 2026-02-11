"""Hit the Balady Umaps_Click identify endpoint with the ArcGIS token."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

PROXY = "https://umaps.balady.gov.sa/newProxyUDP/proxy.ashx"
UMAPI = "https://umaps.balady.gov.sa/UMAPI"
IDENTIFY_SERVER = (
    "https://umapsudp.momrah.gov.sa/server/rest/services/Umaps/Umaps_Click/MapServer"
)

# Parcel 3710897 centroid
LNG, LAT = 46.61328, 24.81573

OUT = Path("balady_identify_result.json")


async def main():
    results: dict = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)
        headers = {
            "Referer": "https://umaps.balady.gov.sa/",
            "Origin": "https://umaps.balady.gov.sa",
        }

        # Step 1: Get session token
        print("Getting session token...")
        r = await ctx.request.post(
            f"{UMAPI}/api/Identity/CreateToken", headers=headers, timeout=15_000,
        )
        session = json.loads(await r.text())
        print(f"  Session: {json.dumps(session)[:200]}")
        results["session_token"] = session

        # Step 2: Get ArcGIS token (needs session token in header)
        print("Getting ArcGIS token...")
        session_token = session.get("token", "")
        auth_headers = {
            **headers,
            "Authorization": f"Bearer {session_token}",
        }
        r = await ctx.request.get(
            f"{UMAPI}/api/Identity/GenerateArcGISTokenResponse",
            headers=auth_headers, timeout=15_000,
        )
        resp_text = await r.text()
        print(f"  Raw response ({r.status}): {resp_text[:300]}")
        if resp_text.strip():
            token_resp = json.loads(resp_text)
        else:
            token_resp = {"error": "empty response"}
        arcgis_token = token_resp.get("token", "")
        print(f"  ArcGIS token: {arcgis_token[:60]}...")
        results["arcgis_token"] = token_resp

        # Step 3: Identify — try multiple approaches
        base_params = (
            f"?geometry={LNG},{LAT}"
            f"&geometryType=esriGeometryPoint"
            f"&sr=4326"
            f"&tolerance=10"
            f"&mapExtent={LNG - 0.002},{LAT - 0.002},{LNG + 0.002},{LAT + 0.002}"
            f"&imageDisplay=1440,900,96"
            f"&layers=all"
            f"&returnGeometry=false"
            f"&f=json"
        )

        attempts = [
            ("proxy_no_token", f"{PROXY}?{IDENTIFY_SERVER}/identify{base_params}", headers),
            ("proxy_with_token", f"{PROXY}?{IDENTIFY_SERVER}/identify{base_params}&token={arcgis_token}", headers),
            ("proxy_auth_header", f"{PROXY}?{IDENTIFY_SERVER}/identify{base_params}", auth_headers),
        ]

        for label, url, hdrs in attempts:
            print(f"\nIdentify [{label}]...")
            try:
                r = await ctx.request.get(url, headers=hdrs, timeout=30_000)
                text = await r.text()
                print(f"  Status: {r.status}, Length: {len(text)}")
                try:
                    data = json.loads(text)
                    results[f"identify_{label}"] = data
                    n = len(data.get("results", []))
                    print(f"  Results: {n}")
                    if n > 0:
                        print(f"  *** GOT DATA ***")
                except json.JSONDecodeError:
                    results[f"identify_{label}_raw"] = text[:3000]
                    print(f"  Not JSON: {text[:200]}")
            except Exception as exc:
                print(f"  Failed: {exc}")

        # Step 4: MapServer info (no token — proxy handles auth)
        print(f"\nGetting MapServer info...")
        info_url = f"{PROXY}?{IDENTIFY_SERVER}?f=json"
        r = await ctx.request.get(info_url, headers=headers, timeout=15_000)
        try:
            info = json.loads(await r.text())
            results["mapserver_info"] = info
            layers = info.get("layers", [])
            print(f"  Layers: {len(layers)}")
            for lyr in layers:
                print(f"    [{lyr.get('id')}] {lyr.get('name')}")
        except Exception:
            pass

        # Step 5: Also try a different identify service — the full parcels layer
        # from service-Config we found: Umaps/UMaps_AdministrativeData/MapServer
        admin_server = "https://umapsudp.momrah.gov.sa/server/rest/services/Umaps/UMaps_AdministrativeData/MapServer"
        admin_url = f"{PROXY}?{admin_server}/identify{base_params}"
        print(f"\nIdentify on AdministrativeData...")
        try:
            r = await ctx.request.get(admin_url, headers=headers, timeout=30_000)
            text = await r.text()
            print(f"  Status: {r.status}, Length: {len(text)}")
            data = json.loads(text)
            results["identify_admin"] = data
            n = len(data.get("results", []))
            print(f"  Results: {n}")
        except Exception as exc:
            print(f"  Failed: {exc}")

        await browser.close()

    # Print detailed results
    for key in ["identify_proxy", "identify_direct"]:
        data = results.get(key, {})
        identify_results = data.get("results", [])
        print(f"\n{'='*60}")
        print(f"{key}: {len(identify_results)} results")
        print(f"{'='*60}")
        for i, res in enumerate(identify_results):
            layer_name = res.get("layerName", "?")
            layer_id = res.get("layerId", "?")
            attrs = res.get("attributes", {})
            print(f"\n  Layer [{layer_id}] {layer_name} ({len(attrs)} fields):")
            for field, val in attrs.items():
                print(f"    {field}: {val}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {OUT}")


asyncio.run(main())
