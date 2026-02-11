"""Click a parcel on the Riyadh Geoportal and capture the popup response.

Opens the geoportal, zooms to parcel 3710897, clicks it,
captures every network request triggered by the click,
and extracts any popup/panel content shown to the public user.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import (
    BrowserContext,
    Page,
    Response,
    async_playwright,
)

TARGET_URL = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"

# Parcel 3710897 centroid (from the polygon we extracted)
TARGET_LNG = 46.61328
TARGET_LAT = 24.81573

OUTPUT_DIR = Path("parcel_click_results")
TEXT_TYPES = ("json", "xml", "text", "html", "javascript", "csv")

REGULATION_KEYWORDS = (
    "building", "bld", "regulation", "condition", "floor", "ادوار",
    "ارتداد", "setback", "نسبة", "FAR", "coverage", "ارتفاع",
    "height", "parking", "مواقف", "نظام", "شروط", "identify",
    "query", "parcel",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("click")


class ClickCapture:
    """Capture only requests that fire after the click."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.active = False

    async def on_response(self, response: Response) -> None:
        if not self.active:
            return
        req = response.request
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "url": req.url,
            "method": req.method,
            "type": req.resource_type,
            "status": response.status,
            "post_data": req.post_data,
            "query_params": parse_qs(urlparse(req.url).query),
            "response_body": None,
            "interesting": False,
        }
        try:
            ct = (await response.all_headers()).get("content-type", "")
            if any(t in ct for t in TEXT_TYPES):
                body = await response.text()
                entry["response_body"] = body[:15000]
                url_lower = req.url.lower() + body.lower()[:2000]
                if any(kw in url_lower for kw in REGULATION_KEYWORDS):
                    entry["interesting"] = True
        except Exception:
            pass

        self.entries.append(entry)
        if req.resource_type in ("xhr", "fetch"):
            flag = " ***" if entry["interesting"] else ""
            log.info("  XHR %s %s -> %d%s", req.method, req.url[:140], response.status, flag)


async def run() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    cap = ClickCapture()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )

        try:
            page: Page = await ctx.new_page()
            page.on("response", cap.on_response)

            # --- Load geoportal ---
            log.info("Loading geoportal...")
            try:
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                log.warning("Nav: %s", exc)

            # Wait for map tiles to load
            log.info("Waiting for map to initialize...")
            await page.wait_for_timeout(8_000)
            await page.screenshot(
                path=str(OUTPUT_DIR / "01_loaded.png"), full_page=False,
            )
            log.info("Page loaded. URL: %s", page.url)

            # --- Zoom to parcel location via URL parameter ---
            # The geoportal supports ?parcelid= which zooms to the parcel
            log.info("Navigating to parcel via URL parameter...")
            try:
                await page.goto(
                    f"{TARGET_URL}?parcelid=3710897",
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            except Exception as exc:
                log.warning("Parcel nav: %s", exc)

            # Wait for zoom animation + tile loading
            log.info("Waiting for parcel zoom + tiles...")
            await page.wait_for_timeout(10_000)
            await page.screenshot(
                path=str(OUTPUT_DIR / "02_zoomed_to_parcel.png"), full_page=False,
            )

            # --- Now click on the parcel ---
            log.info("Activating click capture...")
            cap.active = True

            # The map should be zoomed to the parcel now.
            # Click the center of the map canvas.
            map_el = page.locator(".leaflet-gl-layer, .leaflet-container, canvas").first
            box = await map_el.bounding_box()
            if box:
                cx = int(box["x"] + box["width"] / 2)
                cy = int(box["y"] + box["height"] / 2)
                log.info("Clicking map center at (%d, %d)...", cx, cy)
                await page.mouse.click(cx, cy)
            else:
                log.warning("No map element found. Clicking page center.")
                await page.mouse.click(720, 450)

            # Wait for popup/panel and API calls
            log.info("Waiting 8s for popup and API responses...")
            await page.wait_for_timeout(8_000)

            await page.screenshot(
                path=str(OUTPUT_DIR / "03_after_click.png"), full_page=False,
            )

            # --- Extract visible popup/panel content ---
            log.info("Extracting visible popup/panel text...")
            popup_data = await page.evaluate("""
                () => {
                    const result = {
                        popups: [],
                        sidebars: [],
                        modals: [],
                        all_visible_panels: [],
                    };

                    // ArcGIS/Leaflet popups
                    document.querySelectorAll(
                        '.leaflet-popup, .esri-popup, .popup, [class*="popup"]'
                    ).forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && text.length > 5) {
                            result.popups.push({
                                class: el.className,
                                text: text.substring(0, 3000),
                                html: el.innerHTML.substring(0, 5000),
                            });
                        }
                    });

                    // Sidebars / panels
                    document.querySelectorAll(
                        '.sidebar, .panel, .leaflet-sidebar, [class*="sidebar"], '
                        + '[class*="panel"], [class*="detail"], [class*="info-panel"], '
                        + '[class*="draggable"]'
                    ).forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && text.length > 20) {
                            result.sidebars.push({
                                class: el.className.substring(0, 200),
                                text: text.substring(0, 3000),
                            });
                        }
                    });

                    // Modals
                    document.querySelectorAll(
                        '.modal, [class*="modal"], [role="dialog"]'
                    ).forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && text.length > 10) {
                            result.modals.push({
                                class: el.className.substring(0, 200),
                                visible: el.offsetParent !== null,
                                text: text.substring(0, 3000),
                            });
                        }
                    });

                    // Any element that appeared with parcel-related content
                    const body = document.body.innerText || '';
                    const keywords = ['3710897', '2045', '3114', 'م 111', 'الملقا'];
                    keywords.forEach(kw => {
                        if (body.includes(kw)) {
                            result.all_visible_panels.push({
                                keyword: kw,
                                found: true,
                            });
                        }
                    });

                    return result;
                }
            """)

            (OUTPUT_DIR / "popup_content.json").write_text(
                json.dumps(popup_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(
                "Popup data: %d popups, %d sidebars, %d modals, keywords: %s",
                len(popup_data["popups"]),
                len(popup_data["sidebars"]),
                len(popup_data["modals"]),
                [p["keyword"] for p in popup_data["all_visible_panels"]],
            )

            # Print popup content
            for p in popup_data["popups"]:
                log.info("POPUP: %s", p["text"][:500])
            for s in popup_data["sidebars"]:
                log.info("SIDEBAR: %s", s["text"][:500])

            # --- Second click attempt: try clicking slightly offset ---
            log.info("Trying a second click slightly offset...")
            if box:
                await page.mouse.click(cx + 5, cy + 5)
                await page.wait_for_timeout(5_000)
                await page.screenshot(
                    path=str(OUTPUT_DIR / "04_second_click.png"), full_page=False,
                )

            # --- Summary ---
            log.info("=" * 60)
            log.info("CAPTURE SUMMARY")
            log.info("=" * 60)
            log.info("Total post-click requests: %d", len(cap.entries))
            interesting = [e for e in cap.entries if e["interesting"]]
            log.info("Interesting requests: %d", len(interesting))
            for e in interesting:
                log.info("  %s %s -> %d", e["method"], e["url"][:140], e["status"])
                if e["response_body"]:
                    log.info("    Body preview: %s", e["response_body"][:300])

        except Exception as exc:
            log.error("Fatal: %s", exc, exc_info=True)

        finally:
            # Save all captured requests
            (OUTPUT_DIR / "click_requests.json").write_text(
                json.dumps({
                    "total": len(cap.entries),
                    "interesting": len([e for e in cap.entries if e["interesting"]]),
                    "requests": cap.entries,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Saved %d requests to click_requests.json", len(cap.entries))
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
