"""Explore the Riyadh Geoportal internal API to find building-code decode endpoints.

Three parts:
  Part 1 — Mine the existing captured network traffic for all API endpoints.
  Part 2 — Download Angular JS bundles and search for endpoint names/lookup tables.
  Part 3 — Probe candidate endpoints with parcel ID 3710897.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import (
    BrowserContext,
    Page,
    Response,
    async_playwright,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEOPORTAL_URL = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"
API_BASE = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN"
PROXY_BASE = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN/Handler/proxy.ashx"

# Known auth payload (from captured traffic — encrypted public credentials)
AUTH_PAYLOAD = {
    "appid": "1",
    "username": "kduwGS/eGGSXMz5NkcS/qDFqAZZemcyEL9u7mEcifV2WAFVocT4ezes5ckYEGdxJ",
    "password": "ZhENHqcK6xSu3tZgbAL2kDgeG0Jd6jxGmHtOvZPJOwXsayGvxI/z0rIqUZrbrz8B",
}
API_KEY = "pG5Zbm/s7HxZw0tUTEk71CyqUPRpjQ+1bwK2mbcodH/ume0CYgMZNLzdODAclzfFUT8cf7+ngea7co1U4uCaWSCPuJXEqapZGCoO3Ep3AEg="

# Test parcel
PARCEL_ID = 3710897
# Centroid of parcel 3710897 polygon (from parcel_extract.json)
PARCEL_CENTROID_LNG = 46.61328
PARCEL_CENTROID_LAT = 24.81573

CAPTURED_FILE = Path("geoportal_captured.json")
OUTPUT_DIR = Path("api_exploration")

# JS search patterns
JS_SEARCH_PATTERNS = {
    "api_endpoints": r'["\'](?:api/Public/|APIGEOPORTALN/api/)[^"\']*["\']',
    "flgbldcode": r'FLGBLDCODE|flgbldcode|FLGBldCode',
    "buildingusecode": r'BUILDINGUSECODE|buildingusecode|BuildingUseCode',
    "building_keywords": r'(?:getBuild|getRegulat|getCondition|getDetail|getBld|decodeBld|lookupCode|translateCode)',
    "floors_far": r'(?:floors|عدد.{0,5}أدوار|ارتداد|setback|FAR|floor.?area|نسبة.{0,5}بناء)',
    "lookup_objects": r'\{[^{}]*(?:code|نظام)[^{}]*(?:floor|دور|ارتداد)[^{}]*\}',
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("explore")


# ---------------------------------------------------------------------------
# Part 1: Mine captured data
# ---------------------------------------------------------------------------

def part1_mine_captured() -> dict:
    """Analyze the existing captured traffic for API endpoints."""
    log.info("=" * 60)
    log.info("PART 1: Mining captured geoportal traffic")
    log.info("=" * 60)

    if not CAPTURED_FILE.exists():
        log.error("Captured file not found: %s", CAPTURED_FILE)
        return {}

    data = json.loads(CAPTURED_FILE.read_text(encoding="utf-8"))
    requests = data.get("requests", [])
    log.info("Loaded %d requests from %s", len(requests), CAPTURED_FILE)

    # Filter keywords
    keywords = [
        "/apigeoportaln/",
        "/api/public/",
        "/api/",
        "building", "bld", "code", "regulation", "condition",
        "parcel", "detail", "identify", "query",
    ]

    api_endpoints: dict[str, dict] = {}

    for req in requests:
        url = req.get("url", "")
        url_lower = url.lower()

        if not any(kw in url_lower for kw in keywords):
            continue

        # Skip tile/font/sprite/image requests
        if any(skip in url_lower for skip in (
            "/tile/", "/font/", "/sprite/", "/resources/",
            ".png", ".jpg", ".gif", ".pbf",
            "google-analytics", "googleapis.com", "openweathermap",
            "firebase",
        )):
            continue

        # Parse to get the endpoint path
        parsed = urlparse(url)
        path = parsed.path
        # For proxy URLs, extract the inner URL path
        if "proxy.ashx" in path:
            inner = url.split("proxy.ashx?", 1)[-1] if "proxy.ashx?" in url else ""
            inner_parsed = urlparse(inner)
            path = f"PROXY -> {inner_parsed.path}"

        key = f"{req.get('method', '?')} {path}"
        if key not in api_endpoints:
            api_endpoints[key] = {
                "method": req.get("method"),
                "url": url[:300],
                "full_url": url,
                "resource_type": req.get("resource_type"),
                "status": req.get("status"),
                "post_data": req.get("post_data"),
                "response_body_preview": None,
                "count": 0,
                "phases": [],
            }

        entry = api_endpoints[key]
        entry["count"] += 1
        phase = req.get("phase", "")
        if phase not in entry["phases"]:
            entry["phases"].append(phase)

        # Capture response preview (first occurrence)
        if entry["response_body_preview"] is None:
            body = req.get("response_body", "")
            if body and body != "<binary or unavailable>" and body != "<unavailable>":
                entry["response_body_preview"] = body[:2000]

    log.info("Found %d unique API endpoints", len(api_endpoints))
    for key, info in sorted(api_endpoints.items()):
        log.info(
            "  [%dx] %s -> %d  (%s)",
            info["count"], key[:100], info["status"] or 0,
            ", ".join(info["phases"]),
        )

    return api_endpoints


# ---------------------------------------------------------------------------
# Part 2: Download and search Angular JS bundles
# ---------------------------------------------------------------------------

async def part2_search_bundles(context: BrowserContext) -> dict:
    """Load the geoportal, download JS bundles, search for endpoints."""
    log.info("=" * 60)
    log.info("PART 2: Searching Angular JS bundles")
    log.info("=" * 60)

    js_urls: list[str] = []

    page = await context.new_page()

    def capture_js(response: Response) -> None:
        url = response.request.url
        if url.endswith(".js") and "mapservice.alriyadh.gov.sa" in url:
            js_urls.append(url)

    page.on("response", capture_js)

    log.info("Loading geoportal to discover JS bundles...")
    try:
        await page.goto(GEOPORTAL_URL, wait_until="networkidle", timeout=60_000)
    except Exception:
        try:
            await page.goto(GEOPORTAL_URL, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(10_000)
        except Exception as exc:
            log.warning("Navigation: %s", exc)

    page.remove_listener("response", capture_js)
    await page.close()

    # Deduplicate
    js_urls = sorted(set(js_urls))
    log.info("Discovered %d JS bundle URLs", len(js_urls))

    bundle_dir = OUTPUT_DIR / "js_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    all_findings: dict = {
        "bundle_count": len(js_urls),
        "bundles": [],
        "all_discovered_endpoints": [],
        "all_code_snippets": [],
    }
    seen_endpoints: set[str] = set()

    for i, url in enumerate(js_urls):
        fname = url.split("/")[-1].split("?")[0]
        log.info("  [%d/%d] Downloading: %s", i + 1, len(js_urls), fname)

        try:
            resp = await context.request.get(url, timeout=30_000)
            content = await resp.text()
        except Exception as exc:
            log.warning("    Download failed: %s", exc)
            continue

        # Save bundle
        bundle_path = bundle_dir / fname
        bundle_path.write_text(content, encoding="utf-8")

        bundle_info: dict = {
            "url": url,
            "filename": fname,
            "size": len(content),
            "findings": {},
        }

        # Search for each pattern
        for pattern_name, pattern in JS_SEARCH_PATTERNS.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Deduplicate
                unique = sorted(set(matches))
                bundle_info["findings"][pattern_name] = unique[:50]
                log.info(
                    "    %s: %d matches (%s)",
                    pattern_name, len(unique),
                    ", ".join(unique[:3]),
                )

                # Collect endpoints
                if pattern_name == "api_endpoints":
                    for m in unique:
                        clean = m.strip("\"'")
                        if clean not in seen_endpoints:
                            seen_endpoints.add(clean)
                            all_findings["all_discovered_endpoints"].append(clean)

        # Extract code snippets around key matches (with context)
        for keyword in [
            "FLGBLDCODE", "BUILDINGUSECODE", "getBuild", "getRegulat",
            "getCondition", "getDetail", "getBld", "buildingCode",
            "bldCode", "parcelDetail", "ParcelDetail",
        ]:
            idx = 0
            while True:
                idx = content.find(keyword, idx)
                if idx == -1:
                    break
                start = max(0, idx - 200)
                end = min(len(content), idx + 300)
                snippet = content[start:end]
                all_findings["all_code_snippets"].append({
                    "keyword": keyword,
                    "bundle": fname,
                    "position": idx,
                    "snippet": snippet,
                })
                idx += len(keyword)

        all_findings["bundles"].append(bundle_info)

    log.info("Total unique endpoints discovered in JS: %d", len(all_findings["all_discovered_endpoints"]))
    for ep in all_findings["all_discovered_endpoints"]:
        log.info("  %s", ep)

    log.info("Total code snippets found: %d", len(all_findings["all_code_snippets"]))

    return all_findings


# ---------------------------------------------------------------------------
# Part 3: Probe endpoints
# ---------------------------------------------------------------------------

async def part3_probe_endpoints(context: BrowserContext) -> dict:
    """Authenticate and probe candidate parcel-detail endpoints."""
    log.info("=" * 60)
    log.info("PART 3: Probing parcel detail endpoints")
    log.info("=" * 60)

    results: dict = {"auth": None, "probes": [], "identify": None}
    headers = {
        "Referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap",
        "Origin": "https://mapservice.alriyadh.gov.sa",
        "Content-Type": "application/json",
        "apikey": API_KEY,
    }

    # --- Step 1: Authenticate ---
    log.info("Authenticating...")
    try:
        resp = await context.request.post(
            f"{API_BASE}/api/login/authenticate",
            headers=headers,
            data=json.dumps(AUTH_PAYLOAD),
            timeout=15_000,
        )
        auth_text = await resp.text()
        log.info("Auth response (%d): %s", resp.status, auth_text[:300])
        results["auth"] = {
            "status": resp.status,
            "body": auth_text[:2000],
        }

        # Extract token
        try:
            auth_data = json.loads(auth_text)
            token = auth_data.get("TOKEN", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
                log.info("Got JWT token: %s...", token[:50])
        except json.JSONDecodeError:
            log.warning("Could not parse auth response as JSON")

    except Exception as exc:
        log.error("Auth failed: %s", exc)

    # --- Step 2: Probe candidate endpoints ---
    candidate_endpoints = [
        # GET variations
        ("GET", f"{API_BASE}/api/Public/GetParcelDetails?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetParcelInfo?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetBuildingCode?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetBuildingConditions?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetParcelByID?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetParcelDetail?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetBldCode?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GetRegulations?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GET_PARCEL_INFO?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GET_BLD_CODE?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GET_PARCEL_DETAIL?PARCELID={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GET_BUILDING_CONDITIONS?parcelId={PARCEL_ID}"),
        ("GET", f"{API_BASE}/api/Public/GET_PARCEL_BLD_INFO?PARCELID={PARCEL_ID}"),
        # POST variations
        ("POST", f"{API_BASE}/api/Public/GetParcelDetails"),
        ("POST", f"{API_BASE}/api/Public/GetParcelInfo"),
        ("POST", f"{API_BASE}/api/Public/GetBuildingCode"),
        ("POST", f"{API_BASE}/api/Public/GetBuildingConditions"),
        ("POST", f"{API_BASE}/api/Public/GetParcelByID"),
        ("POST", f"{API_BASE}/api/Public/searchNew3"),
        ("POST", f"{API_BASE}/api/Public/GET_PARCEL_INFO"),
        ("POST", f"{API_BASE}/api/Public/GET_PARCEL_BLD_INFO"),
    ]

    # POST bodies to try
    post_bodies = [
        json.dumps({"parcelId": str(PARCEL_ID)}),
        json.dumps({"parcelId": PARCEL_ID}),
        json.dumps({"PARCELID": PARCEL_ID}),
        json.dumps({"id": PARCEL_ID}),
        json.dumps({"searchText": str(PARCEL_ID), "searchType": "parcel"}),
    ]

    for method, url in candidate_endpoints:
        if method == "GET":
            log.info("Probing GET %s", url[len(API_BASE):])
            try:
                resp = await context.request.get(url, headers=headers, timeout=10_000)
                text = await resp.text()
                is_interesting = resp.status == 200 and len(text) > 50 and '"error"' not in text.lower()[:200]
                log.info(
                    "  -> %d (%d chars)%s",
                    resp.status, len(text),
                    " *** INTERESTING ***" if is_interesting else "",
                )
                results["probes"].append({
                    "method": "GET",
                    "url": url,
                    "status": resp.status,
                    "response_length": len(text),
                    "response_preview": text[:2000],
                    "interesting": is_interesting,
                })
            except Exception as exc:
                log.warning("  -> FAILED: %s", exc)
                results["probes"].append({
                    "method": "GET", "url": url,
                    "error": str(exc),
                })

        else:  # POST
            for body in post_bodies[:2]:  # Try first 2 body formats
                log.info("Probing POST %s body=%s", url[len(API_BASE):], body[:60])
                try:
                    resp = await context.request.post(
                        url, headers=headers, data=body, timeout=10_000,
                    )
                    text = await resp.text()
                    is_interesting = resp.status == 200 and len(text) > 50 and '"error"' not in text.lower()[:200]
                    log.info(
                        "  -> %d (%d chars)%s",
                        resp.status, len(text),
                        " *** INTERESTING ***" if is_interesting else "",
                    )
                    results["probes"].append({
                        "method": "POST",
                        "url": url,
                        "body": body,
                        "status": resp.status,
                        "response_length": len(text),
                        "response_preview": text[:2000],
                        "interesting": is_interesting,
                    })
                    # If we got a valid response, no need to try other bodies
                    if is_interesting:
                        break
                except Exception as exc:
                    log.warning("  -> FAILED: %s", exc)

        await asyncio.sleep(0.3)

    # --- Step 3: MapServer identify ---
    log.info("Probing MapServer identify endpoint...")
    identify_url = (
        f"{PROXY_BASE}?https://maps.alriyadh.gov.sa/gprtl/rest/services/"
        f"WebMercator/WMParcelsLayerOne/MapServer/identify"
        f"?geometry={PARCEL_CENTROID_LNG},{PARCEL_CENTROID_LAT}"
        f"&geometryType=esriGeometryPoint"
        f"&sr=4326"
        f"&tolerance=5"
        f"&mapExtent={PARCEL_CENTROID_LNG-0.001},{PARCEL_CENTROID_LAT-0.001},"
        f"{PARCEL_CENTROID_LNG+0.001},{PARCEL_CENTROID_LAT+0.001}"
        f"&imageDisplay=800,600,96"
        f"&layers=all"
        f"&returnGeometry=true"
        f"&f=json"
    )
    try:
        resp = await context.request.get(
            identify_url, headers=headers, timeout=15_000,
        )
        text = await resp.text()
        log.info("Identify response (%d): %d chars", resp.status, len(text))
        log.info("  Preview: %s", text[:500])
        results["identify"] = {
            "url": identify_url,
            "status": resp.status,
            "response_length": len(text),
            "response": text[:5000],
        }
    except Exception as exc:
        log.error("Identify failed: %s", exc)

    # Also try direct (no proxy)
    log.info("Trying direct MapServer identify (no proxy)...")
    direct_url = (
        f"https://maps.alriyadh.gov.sa/gprtl/rest/services/"
        f"WebMercator/WMParcelsLayerOne/MapServer/identify"
        f"?geometry={PARCEL_CENTROID_LNG},{PARCEL_CENTROID_LAT}"
        f"&geometryType=esriGeometryPoint"
        f"&sr=4326"
        f"&tolerance=5"
        f"&mapExtent={PARCEL_CENTROID_LNG-0.001},{PARCEL_CENTROID_LAT-0.001},"
        f"{PARCEL_CENTROID_LNG+0.001},{PARCEL_CENTROID_LAT+0.001}"
        f"&imageDisplay=800,600,96"
        f"&layers=all"
        f"&returnGeometry=true"
        f"&f=json"
    )
    try:
        resp = await context.request.get(direct_url, timeout=15_000)
        text = await resp.text()
        log.info("Direct identify (%d): %d chars", resp.status, len(text))
        log.info("  Preview: %s", text[:500])
        results["identify_direct"] = {
            "url": direct_url,
            "status": resp.status,
            "response_length": len(text),
            "response": text[:5000],
        }
    except Exception as exc:
        log.error("Direct identify failed: %s", exc)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run() -> None:
    """Execute all three parts."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # === PART 1 ===
    api_endpoints = part1_mine_captured()
    p1_file = OUTPUT_DIR / "geoportal_api_analysis.json"
    p1_file.write_text(
        json.dumps(api_endpoints, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Part 1 saved to %s", p1_file)

    # === PARTS 2 & 3 (need browser) ===
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )

        try:
            # === PART 2 ===
            bundle_findings = await part2_search_bundles(context)

            p2_endpoints_file = OUTPUT_DIR / "discovered_endpoints.json"
            p2_endpoints_file.write_text(
                json.dumps(
                    bundle_findings["all_discovered_endpoints"],
                    ensure_ascii=False, indent=2,
                ),
                encoding="utf-8",
            )

            p2_snippets_file = OUTPUT_DIR / "js_code_snippets.txt"
            with p2_snippets_file.open("w", encoding="utf-8") as f:
                for snip in bundle_findings["all_code_snippets"]:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Keyword: {snip['keyword']}\n")
                    f.write(f"Bundle: {snip['bundle']} @ pos {snip['position']}\n")
                    f.write(f"{'='*60}\n")
                    f.write(snip["snippet"])
                    f.write("\n")

            p2_full_file = OUTPUT_DIR / "bundle_search_results.json"
            p2_full_file.write_text(
                json.dumps(bundle_findings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Part 2 saved to %s, %s, %s", p2_endpoints_file, p2_snippets_file, p2_full_file)

            # === PART 3 ===
            probe_results = await part3_probe_endpoints(context)

            p3_file = OUTPUT_DIR / "geoportal_api_exploration.json"
            p3_file.write_text(
                json.dumps(probe_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Part 3 saved to %s", p3_file)

            # === FINAL SUMMARY ===
            log.info("=" * 60)
            log.info("FINAL SUMMARY")
            log.info("=" * 60)
            log.info("Part 1: %d API endpoints found in captured traffic", len(api_endpoints))
            log.info("Part 2: %d endpoints in JS bundles, %d code snippets",
                      len(bundle_findings["all_discovered_endpoints"]),
                      len(bundle_findings["all_code_snippets"]))
            interesting = [p for p in probe_results["probes"] if p.get("interesting")]
            log.info("Part 3: %d interesting responses out of %d probes",
                      len(interesting), len(probe_results["probes"]))
            for p in interesting:
                log.info("  *** %s %s -> %d chars",
                          p["method"], p["url"][len(API_BASE):], p["response_length"])

            if probe_results.get("identify"):
                log.info("MapServer identify: %d chars", probe_results["identify"]["response_length"])
            if probe_results.get("identify_direct"):
                log.info("Direct identify: %d chars", probe_results["identify_direct"]["response_length"])

        except Exception as exc:
            log.error("Fatal: %s", exc, exc_info=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
