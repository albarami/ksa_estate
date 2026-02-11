"""Decode Riyadh building regulation codes.

Two-part script:
  Part 1 — Scrape the TRC building permits guide (trc.alriyadh.gov.sa)
           to find the lookup tables that translate codes like "م 111"
           into actual building regulations (floors, FAR, setbacks).
  Part 2 — Query the Geoportal parcel API for multiple parcel IDs
           to catalog what range of building codes actually exist.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import (
    BrowserContext,
    Page,
    Response,
    async_playwright,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRC_URLS = [
    "https://trc.alriyadh.gov.sa/",
    "https://trc.alriyadh.gov.sa/eindex.html",
]

# Geoportal parcel query (discovered from capture session)
PARCEL_API_BASE = (
    "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN/Handler/proxy.ashx?"
    "https://maps.alriyadh.gov.sa/gprtl/rest/services/WebMercator/"
    "WMParcelsLayerOne/MapServer/2/query"
)
PARCEL_FIELDS = (
    "PARCELID,PARCELNO,PLANNO,FLGBLDCODE,BUILDINGUSECODE,"
    "PARCELSUBTYPE,LANDUSEAGROUP,LANDUSEADETAILED,"
    "DISTRICT,SUBMUNICIPALITY,SHAPE.AREA"
)

SAMPLE_PARCEL_IDS = [
    3710897, 3710898, 3710899, 3710900,
    3700000, 3800000, 3900000,
    4000000, 4100000, 4200000,
]

OUTPUT_DIR = Path("decode_output")
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("decode")


# ---------------------------------------------------------------------------
# Part 1: Scrape TRC building guide
# ---------------------------------------------------------------------------

async def scrape_trc(page: Page) -> dict:
    """Scrape the TRC building permits guide for regulation tables."""
    trc_data: dict = {
        "pages": [],
        "captured_requests": [],
    }

    async def on_response(response: Response) -> None:
        """Capture XHR/fetch from TRC."""
        req = response.request
        if req.resource_type in ("xhr", "fetch", "document"):
            entry = {
                "url": req.url,
                "method": req.method,
                "status": response.status,
                "content_type": (await response.all_headers()).get(
                    "content-type", "",
                ),
            }
            try:
                ct = entry["content_type"]
                if any(t in ct for t in ("json", "xml", "text", "html")):
                    entry["body"] = await response.text()
            except Exception:
                entry["body"] = None
            trc_data["captured_requests"].append(entry)

    page.on("response", on_response)

    for url in TRC_URLS:
        log.info("Scraping TRC page: %s", url)
        try:
            await page.goto(url, wait_until="networkidle", timeout=60_000)
        except Exception as exc:
            log.warning("TRC navigation issue for %s: %s", url, exc)

        await page.wait_for_timeout(3_000)

        # Screenshot the landing page
        slug = url.split("/")[-1] or "index"
        ss_path = SCREENSHOT_DIR / f"trc_{slug}.png"
        await page.screenshot(path=str(ss_path), full_page=True)
        log.info("Screenshot: %s", ss_path)

        # Get full page HTML
        html = await page.content()
        page_entry = {
            "url": page.url,
            "title": await page.title(),
            "html_length": len(html),
        }

        # Save raw HTML
        html_path = OUTPUT_DIR / f"trc_{slug}.html"
        html_path.write_text(html, encoding="utf-8")
        log.info("Saved HTML (%d chars): %s", len(html), html_path)

        # Try to find and click on links that might contain building codes
        # Look for links/buttons with relevant Arabic/English keywords
        link_keywords = [
            "نظام", "بناء", "شروط", "أنظمة", "building",
            "code", "regulation", "system", "guide",
            "ارتداد", "أدوار", "floor", "setback", "FAR",
        ]

        links = await page.query_selector_all("a, button, .nav-link, [role='tab']")
        visited_hrefs: set[str] = set()

        for link in links:
            try:
                text = (await link.inner_text()).strip().lower()
                href = await link.get_attribute("href") or ""

                if not any(kw in text or kw in href.lower() for kw in link_keywords):
                    continue
                if href in visited_hrefs or href.startswith("javascript:void"):
                    continue
                visited_hrefs.add(href)

                log.info("  Clicking link: '%s' -> %s", text[:60], href[:80])
                try:
                    await link.click(timeout=5_000)
                    await page.wait_for_timeout(2_000)
                except Exception:
                    pass

                # Screenshot sub-page
                sub_slug = href.replace("/", "_").replace("?", "_")[:40] or text[:20]
                sub_ss = SCREENSHOT_DIR / f"trc_sub_{sub_slug}.png"
                await page.screenshot(path=str(sub_ss), full_page=True)

                # Capture sub-page HTML
                sub_html = await page.content()
                sub_path = OUTPUT_DIR / f"trc_sub_{sub_slug}.html"
                sub_path.write_text(sub_html, encoding="utf-8")

                page_entry_sub = {
                    "url": page.url,
                    "link_text": text[:100],
                    "html_length": len(sub_html),
                }
                trc_data["pages"].append(page_entry_sub)

            except Exception as exc:
                log.warning("  Error processing link: %s", exc)

        trc_data["pages"].append(page_entry)

        # Try to extract all tables from the page (regulation lookup tables)
        tables = await _extract_tables(page)
        if tables:
            log.info("  Found %d tables on %s", len(tables), url)
            page_entry["tables"] = tables

    page.remove_listener("response", on_response)
    return trc_data


async def _extract_tables(page: Page) -> list[dict]:
    """Extract all HTML tables as structured data."""
    try:
        return await page.evaluate("""
            () => {
                const tables = document.querySelectorAll('table');
                return Array.from(tables).map((table, idx) => {
                    const headers = Array.from(
                        table.querySelectorAll('thead th, tr:first-child th, tr:first-child td')
                    ).map(th => th.innerText.trim());

                    const rows = Array.from(table.querySelectorAll('tbody tr, tr'))
                        .slice(headers.length > 0 ? 0 : 1)
                        .map(tr =>
                            Array.from(tr.querySelectorAll('td'))
                                .map(td => td.innerText.trim())
                        )
                        .filter(row => row.length > 0);

                    return {
                        index: idx,
                        headers: headers,
                        row_count: rows.length,
                        rows: rows.slice(0, 50),  // cap at 50 rows
                    };
                });
            }
        """)
    except Exception as exc:
        log.warning("Table extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Part 2: Query multiple parcels via the Geoportal API
# ---------------------------------------------------------------------------

async def query_parcels(context: BrowserContext) -> list[dict]:
    """Query the parcel API for a sample of parcel IDs.

    Uses two strategies:
      1. Playwright's API request context with proper Referer header
      2. Direct ArcGIS MapServer call (bypassing the proxy)
    """
    results: list[dict] = []

    # The proxy URL requires Referer from geoportal
    proxy_headers = {
        "Referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap",
        "Origin": "https://mapservice.alriyadh.gov.sa",
    }

    # Direct ArcGIS endpoint (bypasses the proxy entirely)
    direct_api = (
        "https://maps.alriyadh.gov.sa/gprtl/rest/services/WebMercator/"
        "WMParcelsLayerOne/MapServer/2/query"
    )

    for parcel_id in SAMPLE_PARCEL_IDS:
        log.info("Querying parcel %d...", parcel_id)
        params = (
            f"?where=PARCELID%3D{parcel_id}"
            f"&returnGeometry=false"
            f"&outFields={PARCEL_FIELDS}"
            f"&f=json"
        )

        response_text: str | None = None

        # Strategy 1: Proxy with Referer header
        proxy_url = PARCEL_API_BASE + params
        try:
            resp = await context.request.get(
                proxy_url,
                headers=proxy_headers,
                timeout=15_000,
            )
            response_text = await resp.text()
            log.info("  Proxy response: %d (%d chars)", resp.status, len(response_text))
        except Exception as exc:
            log.warning("  Proxy request failed: %s", exc)

        # Check if proxy gave an error, try direct
        if not response_text or '"error"' in response_text[:200]:
            log.info("  Trying direct ArcGIS endpoint...")
            direct_url = direct_api + params
            try:
                resp = await context.request.get(direct_url, timeout=15_000)
                response_text = await resp.text()
                log.info("  Direct response: %d (%d chars)", resp.status, len(response_text))
            except Exception as exc:
                log.warning("  Direct request also failed: %s", exc)

        if response_text:
            parsed = _parse_parcel_response(parcel_id, response_text)
            results.append(parsed)
            if parsed.get("found"):
                log.info(
                    "  Found: FLGBLDCODE=%s  BUILDINGUSECODE=%s  "
                    "PARCELSUBTYPE=%s  LANDUSEADETAILED=%s  AREA=%s",
                    parsed.get("FLGBLDCODE"),
                    parsed.get("BUILDINGUSECODE"),
                    parsed.get("PARCELSUBTYPE"),
                    parsed.get("LANDUSEADETAILED"),
                    parsed.get("SHAPE.AREA"),
                )
            elif parsed.get("error"):
                log.warning("  Error: %s", parsed["error"])
            else:
                log.info("  No features returned (parcel may not exist).")
        else:
            results.append({
                "parcel_id": parcel_id,
                "found": False,
                "error": "no response from either endpoint",
            })

        # Small delay between requests
        await asyncio.sleep(0.8)

    return results


def _parse_parcel_response(parcel_id: int, text: str) -> dict:
    """Parse an ArcGIS query response (JSON or JSONP)."""
    text = text.strip()

    # Strip JSONP callback wrapper if present
    if text.startswith("window.") or text.startswith("callback"):
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            text = text[start:end]
        except ValueError:
            pass

    # Strip trailing HTML garbage that the proxy sometimes appends
    brace_depth = 0
    json_end = 0
    for i, ch in enumerate(text):
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                json_end = i + 1
                break
    if json_end > 0:
        text = text[:json_end]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "error": f"JSON parse: {exc}",
            "raw": text[:500],
        }

    # Check for ArcGIS error response
    if "error" in data:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "error": data["error"].get("message", str(data["error"])),
        }

    features = data.get("features", [])
    if features:
        attrs = features[0].get("attributes", {})
        return {"parcel_id": parcel_id, "found": True, **attrs}

    return {"parcel_id": parcel_id, "found": False}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run() -> None:
    """Execute both parts of the decode workflow."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )

        try:
            # === Part 1: Scrape TRC =======================================
            log.info("=" * 60)
            log.info("PART 1: Scraping TRC Building Permits Guide")
            log.info("=" * 60)

            trc_page = await context.new_page()
            trc_data = await scrape_trc(trc_page)
            await trc_page.close()

            trc_output = OUTPUT_DIR / "trc_scraped_data.json"
            trc_output.write_text(
                json.dumps(trc_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("TRC data saved: %s", trc_output)

            # === Part 2: Query multiple parcels ===========================
            log.info("=" * 60)
            log.info("PART 2: Querying multiple parcels for code sampling")
            log.info("=" * 60)

            parcel_results = await query_parcels(context)

            # Save parcel results
            parcel_output = OUTPUT_DIR / "building_codes_sample.json"
            payload = {
                "meta": {
                    "queried_at": datetime.now(timezone.utc).isoformat(),
                    "api_base": PARCEL_API_BASE,
                    "fields_requested": PARCEL_FIELDS,
                    "total_queried": len(SAMPLE_PARCEL_IDS),
                    "total_found": sum(
                        1 for r in parcel_results if r.get("found")
                    ),
                },
                "parcels": parcel_results,
            }
            parcel_output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Parcel codes saved: %s", parcel_output)

            # === Summary ==================================================
            log.info("=" * 60)
            log.info("SUMMARY")
            log.info("=" * 60)

            found = [r for r in parcel_results if r.get("found")]
            codes_seen: dict[str, set[str]] = {
                "FLGBLDCODE": set(),
                "BUILDINGUSECODE": set(),
                "PARCELSUBTYPE": set(),
                "LANDUSEAGROUP": set(),
                "LANDUSEADETAILED": set(),
            }
            for r in found:
                for field in codes_seen:
                    val = r.get(field)
                    if val is not None:
                        codes_seen[field].add(str(val))

            log.info("Parcels found: %d / %d", len(found), len(SAMPLE_PARCEL_IDS))
            log.info("Unique codes discovered:")
            for field, vals in codes_seen.items():
                log.info("  %s: %s", field, sorted(vals) if vals else "(none)")

            log.info("TRC pages scraped: %d", len(trc_data.get("pages", [])))
            log.info(
                "TRC network requests captured: %d",
                len(trc_data.get("captured_requests", [])),
            )

        except Exception as exc:
            log.error("Fatal error: %s", exc, exc_info=True)

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
