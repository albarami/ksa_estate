"""Explore Balady UMaps for building regulation decode data.

Opens https://umaps.balady.gov.sa/, captures all network traffic,
explores search/query functionality, and looks for parcel regulation
details (floors, FAR, setbacks).
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

TARGET_URL = "https://umaps.balady.gov.sa/"
PARCEL_ID = "3710897"
PLAN_NO = "3114"

OUTPUT_DIR = Path("balady_umaps_exploration")
SS_DIR = OUTPUT_DIR / "screenshots"

TEXT_TYPES = ("json", "xml", "text", "html", "javascript", "csv")

REGULATION_KEYWORDS = (
    "floor", "ادوار", "عدد الأدوار", "ارتداد", "setback",
    "FAR", "نسبة البناء", "coverage", "تغطية", "ارتفاع",
    "height", "parking", "مواقف", "بناء", "building",
    "regulation", "نظام", "condition", "شرط", "zoning",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("balady")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

class Capture:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.phase = "load"

    async def on_response(self, response: Response) -> None:
        req = response.request
        entry: dict = {
            "phase": self.phase,
            "ts": datetime.now(timezone.utc).isoformat(),
            "url": req.url,
            "method": req.method,
            "type": req.resource_type,
            "status": response.status,
            "post_data": req.post_data,
            "query_params": parse_qs(urlparse(req.url).query),
            "response_body": None,
            "has_regulation_keywords": False,
        }
        try:
            ct = (await response.all_headers()).get("content-type", "")
            if any(t in ct for t in TEXT_TYPES):
                body = await response.text()
                entry["response_body"] = body[:10000]
                lower = body.lower()
                if any(kw in lower for kw in REGULATION_KEYWORDS):
                    entry["has_regulation_keywords"] = True
        except Exception:
            pass
        self.entries.append(entry)

        if req.resource_type in ("xhr", "fetch"):
            flag = " ***" if entry["has_regulation_keywords"] else ""
            log.info(
                "[%s] %s %s -> %d%s",
                self.phase, req.method, req.url[:150], response.status, flag,
            )


async def ss(page: Page, name: str) -> None:
    SS_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SS_DIR / name), full_page=True)
    log.info("Screenshot: %s", name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    cap = Capture()

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

            # === Load page ================================================
            log.info("Navigating to %s", TARGET_URL)
            try:
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                log.warning("Navigation: %s", exc)

            await page.wait_for_timeout(5_000)
            url_after = page.url
            log.info("Current URL: %s", url_after)
            await ss(page, "00_initial.png")

            # Save full HTML
            html = await page.content()
            (OUTPUT_DIR / "page.html").write_text(html, encoding="utf-8")
            log.info("Saved HTML: %d chars", len(html))

            # === Discover page structure ==================================
            log.info("Discovering page controls...")
            controls = await page.evaluate("""
                () => {
                    const r = {
                        title: document.title,
                        selects: [],
                        inputs: [],
                        buttons: [],
                        links: [],
                        iframes: [],
                        map_elements: [],
                    };
                    document.querySelectorAll('select').forEach(el => {
                        const opts = Array.from(el.options).map(o => ({
                            value: o.value, text: o.text.trim(),
                        }));
                        r.selects.push({
                            id: el.id, name: el.name,
                            class: el.className, options: opts.slice(0, 30),
                            count: opts.length,
                        });
                    });
                    document.querySelectorAll(
                        'input[type="text"], input[type="search"], input:not([type]), input[type="number"]'
                    ).forEach(el => {
                        r.inputs.push({
                            id: el.id, name: el.name,
                            placeholder: el.placeholder,
                            class: el.className, type: el.type,
                        });
                    });
                    document.querySelectorAll('button, input[type="submit"], a.btn').forEach(el => {
                        r.buttons.push({
                            id: el.id, text: (el.innerText || '').trim().substring(0, 80),
                            class: el.className,
                        });
                    });
                    document.querySelectorAll('iframe').forEach(el => {
                        r.iframes.push({ src: el.src, id: el.id, class: el.className });
                    });
                    // Map containers
                    document.querySelectorAll(
                        'canvas, .esri-view, .leaflet-container, .ol-viewport, .maplibregl-map, .mapboxgl-map, [class*="map"]'
                    ).forEach(el => {
                        r.map_elements.push({
                            tag: el.tagName, id: el.id,
                            class: el.className.substring(0, 100),
                        });
                    });
                    return r;
                }
            """)
            (OUTPUT_DIR / "controls.json").write_text(
                json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            log.info(
                "Controls: title='%s', %d selects, %d inputs, %d buttons, "
                "%d iframes, %d map elements",
                controls.get("title", ""),
                len(controls["selects"]),
                len(controls["inputs"]),
                len(controls["buttons"]),
                len(controls["iframes"]),
                len(controls["map_elements"]),
            )

            for inp in controls["inputs"]:
                log.info("  INPUT: id='%s' placeholder='%s'", inp["id"], inp["placeholder"])
            for sel in controls["selects"]:
                log.info("  SELECT: id='%s' (%d options)", sel["id"], sel["count"])
            for iframe in controls["iframes"]:
                log.info("  IFRAME: src='%s'", iframe["src"][:120])

            # === Handle iframes ===========================================
            if controls["iframes"]:
                for iframe_info in controls["iframes"]:
                    src = iframe_info["src"]
                    if not src or src == "about:blank":
                        continue
                    log.info("Exploring iframe: %s", src[:120])
                    for frame in page.frames:
                        if frame.url and frame.url.startswith(src[:50]):
                            log.info("  Switched to frame: %s", frame.url[:120])
                            # Discover controls inside iframe
                            try:
                                inner = await frame.evaluate("""
                                    () => {
                                        const r = { inputs: [], selects: [], buttons: [], text: '' };
                                        document.querySelectorAll('input').forEach(el => {
                                            r.inputs.push({
                                                id: el.id, placeholder: el.placeholder,
                                                type: el.type, name: el.name,
                                            });
                                        });
                                        document.querySelectorAll('select').forEach(el => {
                                            const opts = Array.from(el.options).map(
                                                o => ({value: o.value, text: o.text.trim()})
                                            );
                                            r.selects.push({
                                                id: el.id, name: el.name, options: opts.slice(0, 50),
                                            });
                                        });
                                        document.querySelectorAll('button').forEach(el => {
                                            r.buttons.push({
                                                id: el.id,
                                                text: (el.innerText || '').trim().substring(0, 80),
                                            });
                                        });
                                        r.text = document.body?.innerText?.substring(0, 3000) || '';
                                        return r;
                                    }
                                """)
                                (OUTPUT_DIR / "iframe_controls.json").write_text(
                                    json.dumps(inner, ensure_ascii=False, indent=2),
                                    encoding="utf-8",
                                )
                                log.info(
                                    "  Iframe controls: %d inputs, %d selects, %d buttons",
                                    len(inner["inputs"]),
                                    len(inner["selects"]),
                                    len(inner["buttons"]),
                                )
                                for inp in inner["inputs"]:
                                    log.info("    INPUT: id='%s' placeholder='%s'", inp["id"], inp["placeholder"])
                                for sel in inner["selects"]:
                                    log.info("    SELECT: id='%s' (%d opts)", sel["id"], len(sel["options"]))
                            except Exception as exc:
                                log.warning("  Iframe eval failed: %s", exc)

            # === Try search functionality =================================
            cap.phase = "search"
            await page.wait_for_timeout(3_000)
            await ss(page, "01_before_search.png")

            # Try typing parcel ID in any visible search input
            search_selectors = [
                "input[type='search']",
                "input[placeholder*='بحث']",
                "input[placeholder*='search']",
                "input[placeholder*='Search']",
                "input[placeholder*='رقم']",
                "input[id*='search']",
                "input[id*='Search']",
                "#txtSearch",
                ".search-input",
                "input.form-control",
            ]
            searched = False
            for sel in search_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        log.info("Found search input: %s", sel)
                        await el.fill(PARCEL_ID)
                        await page.wait_for_timeout(1_000)
                        await el.press("Enter")
                        await page.wait_for_timeout(3_000)
                        await ss(page, "02_search_parcel.png")
                        searched = True
                        break
                except Exception:
                    continue

            if not searched:
                log.info("No visible search input found on main page. Trying frames...")
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    for sel in search_selectors:
                        try:
                            el = frame.locator(sel).first
                            if await el.count() > 0:
                                log.info("Found search in frame: %s", sel)
                                await el.fill(PARCEL_ID)
                                await page.wait_for_timeout(1_000)
                                await el.press("Enter")
                                await page.wait_for_timeout(3_000)
                                await ss(page, "02_search_parcel_frame.png")
                                searched = True
                                break
                        except Exception:
                            continue
                    if searched:
                        break

            # === Wait and capture more network activity ====================
            await page.wait_for_timeout(5_000)
            await ss(page, "03_after_wait.png")

            # === Collect JS bundle URLs for endpoint mining ================
            js_urls = [
                e["url"] for e in cap.entries
                if e["url"].endswith(".js") and "balady" in e["url"]
            ]
            log.info("Balady JS bundles: %d", len(js_urls))
            endpoints_found: list[str] = []

            for js_url in js_urls[:5]:
                fname = js_url.split("/")[-1].split("?")[0]
                log.info("  Downloading: %s", fname)
                try:
                    resp = await ctx.request.get(js_url, timeout=30_000)
                    content = await resp.text()
                    # Search for API endpoint patterns
                    api_matches = re.findall(
                        r'["\'](?:https?://[^"\']*(?:api|rest|service|query|identify|search)[^"\']*)["\']',
                        content, re.IGNORECASE,
                    )
                    unique = sorted(set(m.strip("\"'") for m in api_matches))
                    if unique:
                        log.info("    Endpoints in %s: %d", fname, len(unique))
                        for ep in unique[:20]:
                            log.info("      %s", ep[:150])
                        endpoints_found.extend(unique)

                    # Search for regulation keywords
                    for kw in ["FLGBLDCODE", "buildingCode", "setback", "floor", "FAR",
                               "regulation", "نظام البناء", "ارتداد", "ادوار"]:
                        idx = content.find(kw)
                        if idx != -1:
                            start = max(0, idx - 100)
                            end = min(len(content), idx + 200)
                            log.info("    FOUND '%s' in %s: ...%s...", kw, fname, content[start:end][:200])
                except Exception as exc:
                    log.warning("    Download failed: %s", exc)

            # === Summary ==================================================
            log.info("=" * 60)
            log.info("SUMMARY")
            log.info("=" * 60)
            total = len(cap.entries)
            xhr = [e for e in cap.entries if e["type"] in ("xhr", "fetch")]
            reg = [e for e in cap.entries if e["has_regulation_keywords"]]
            log.info("Total requests: %d", total)
            log.info("XHR/fetch: %d", len(xhr))
            log.info("With regulation keywords: %d", len(reg))
            for r in reg:
                log.info("  %s %s", r["method"], r["url"][:150])
            log.info("Endpoints from JS: %d", len(set(endpoints_found)))
            log.info("Search attempted: %s", searched)

        except Exception as exc:
            log.error("Fatal: %s", exc, exc_info=True)

        finally:
            # Save captured requests
            req_file = OUTPUT_DIR / "captured_requests.json"
            payload = {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "total": len(cap.entries),
                "requests": cap.entries,
            }
            req_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            log.info("Saved %d requests to %s", len(cap.entries), req_file)

            if endpoints_found:
                ep_file = OUTPUT_DIR / "discovered_endpoints.json"
                ep_file.write_text(
                    json.dumps(sorted(set(endpoints_found)), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
