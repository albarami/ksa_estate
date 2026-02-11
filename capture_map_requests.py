"""Playwright script to capture all network traffic from the Riyadh Geoportal.

Opens the Riyadh Municipality geoportal map, intercepts every network
request/response, detects the map framework (ArcGIS / Leaflet / OpenLayers),
clicks on a target coordinate, then also loads a direct parcel-ID URL.
All captured traffic is saved to a JSON file for API reverse-engineering.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import (
    BrowserContext,
    Frame,
    Page,
    Response,
    async_playwright,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_URL = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"
PARCEL_URL = "https://mapservice.alriyadh.gov.sa/geoportal/?parcelid=3710897"

# WGS-84 coordinates for Al-Hada district, Riyadh
TARGET_LAT = 24.8256
TARGET_LNG = 46.6526

OUTPUT_FILE = Path("geoportal_captured.json")
SCREENSHOT_DIR = Path("screenshots")

MAP_LOAD_TIMEOUT_MS = 90_000
POST_CLICK_WAIT_S = 10

# Content-type substrings we consider "textual" (safe to read as text)
TEXT_CONTENT_TYPES = ("json", "xml", "text", "html", "javascript", "csv")

# API URL patterns we especially care about
KEY_API_PATTERNS = (
    "/MapServer/identify",
    "/FeatureServer/query",
    "/MapServer/find",
    "/MapServer/export",
    "/GPServer/",
    "/rest/services/",
    "/arcgis/",
    "parcelid",
    "parcel",
    "query",
    "identify",
    "getfeature",
    "wfs",
    "wms",
)

# Arabic field names that indicate parcel / building regulation data
ARABIC_FIELDS = (
    "نظام البناء",
    "شروط البناء",
    "استعمال الأرض",
    "رقم المخطط",
    "رقم القطعة",
    "الارتداد",
    "عدد الأدوار",
    "نسبة البناء",
    "الاستعمال",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("capture")


# ---------------------------------------------------------------------------
# Capture storage
# ---------------------------------------------------------------------------

class RequestCapture:
    """Accumulates network entries tagged by phase."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.console_logs: list[dict] = []
        self.phase: str = "initial_load"

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        log.info("--- Phase changed to: %s ---", phase)

    async def on_response(self, response: Response) -> None:
        """Handle every HTTP response that Playwright sees."""
        request = response.request

        entry: dict = {
            "phase": self.phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": request.url,
            "method": request.method,
            "resource_type": request.resource_type,
            "request_headers": await request.all_headers(),
            "query_params": parse_qs(urlparse(request.url).query),
            "post_data": request.post_data,
            "status": response.status,
            "status_text": response.status_text,
            "response_headers": await response.all_headers(),
            "response_body": None,
            "contains_arabic_fields": [],
        }

        # Read response body for textual content types only
        try:
            content_type = (await response.all_headers()).get(
                "content-type", "",
            )
            if any(t in content_type for t in TEXT_CONTENT_TYPES):
                body = await response.text()
                entry["response_body"] = body
                # Scan for Arabic field names
                for field in ARABIC_FIELDS:
                    if field in body:
                        entry["contains_arabic_fields"].append(field)
                if entry["contains_arabic_fields"]:
                    log.info(
                        "[%s] *** ARABIC FIELDS FOUND *** %s -> %s",
                        self.phase,
                        request.url[:120],
                        entry["contains_arabic_fields"],
                    )
        except Exception:
            entry["response_body"] = "<binary or unavailable>"

        self.entries.append(entry)

        # Log notable requests
        url_lower = request.url.lower()
        is_key_api = any(p in url_lower for p in KEY_API_PATTERNS)
        is_xhr = request.resource_type in ("xhr", "fetch")

        if is_key_api:
            log.info(
                "[%s] *** KEY API *** %s %s -> %d",
                self.phase, request.method,
                request.url[:180], response.status,
            )
        elif is_xhr:
            log.info(
                "[%s] XHR %s %s -> %d",
                self.phase, request.method,
                request.url[:180], response.status,
            )

    def on_console(self, msg) -> None:
        """Capture browser console output."""
        self.console_logs.append({
            "phase": self.phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": msg.type,
            "text": msg.text,
        })

    def on_websocket(self, ws, phase_ref: "RequestCapture") -> None:
        """Attach listeners for a WebSocket connection."""
        log.info("[%s] WebSocket opened: %s", phase_ref.phase, ws.url)

        def on_frame_sent(payload):
            phase_ref.entries.append({
                "phase": phase_ref.phase,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": ws.url,
                "resource_type": "websocket",
                "direction": "sent",
                "data": payload if isinstance(payload, str) else "<binary>",
            })

        def on_frame_received(payload):
            phase_ref.entries.append({
                "phase": phase_ref.phase,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": ws.url,
                "resource_type": "websocket",
                "direction": "received",
                "data": payload if isinstance(payload, str) else "<binary>",
            })

        ws.on("framesent", on_frame_sent)
        ws.on("framereceived", on_frame_received)

    def save(self, path: Path) -> None:
        """Write everything to a JSON file."""
        # Collect entries that contain Arabic parcel fields
        arabic_hits = [
            e for e in self.entries if e.get("contains_arabic_fields")
        ]
        payload = {
            "meta": {
                "target_url": TARGET_URL,
                "parcel_url": PARCEL_URL,
                "target_coords": {
                    "lat": TARGET_LAT,
                    "lng": TARGET_LNG,
                },
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "total_requests": len(self.entries),
                "total_console_logs": len(self.console_logs),
                "arabic_field_hits": len(arabic_hits),
            },
            "requests": self.entries,
            "console_logs": self.console_logs,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(
            "Saved %d requests (%d with Arabic fields) to %s",
            len(self.entries), len(arabic_hits), path,
        )


# ---------------------------------------------------------------------------
# Map framework detection
# ---------------------------------------------------------------------------

DETECT_MAP_FRAMEWORK_JS = """
() => {
    const result = {
        framework: null,
        ready: false,
        details: {},
        hasIframe: false,
        iframeSrc: null,
    };

    // --- ArcGIS JS API ---------------------------------------------------
    const esriView = document.querySelector('.esri-view');
    if (window.view && window.view.ready) {
        result.framework = 'arcgis';
        result.ready = true;
        result.details = { source: 'window.view' };
        return result;
    }
    if (window.app && window.app.view && window.app.view.ready) {
        result.framework = 'arcgis';
        result.ready = true;
        result.details = { source: 'window.app.view' };
        return result;
    }
    if (esriView && esriView.classList.contains('esri-view--ready')) {
        result.framework = 'arcgis';
        result.ready = true;
        result.details = { source: '.esri-view--ready' };
        return result;
    }
    if (esriView && esriView.__view && esriView.__view.ready) {
        result.framework = 'arcgis';
        result.ready = true;
        result.details = { source: 'esriView.__view' };
        return result;
    }
    // ArcGIS detected but not yet ready
    if (esriView || window.require && window.require.toUrl) {
        result.framework = 'arcgis';
        result.details = { source: 'esri-view-exists-not-ready' };
        return result;
    }

    // --- Leaflet ---------------------------------------------------------
    if (window.L && window.L.map) {
        result.framework = 'leaflet';
        // Find the first Leaflet map instance
        const containers = document.querySelectorAll('.leaflet-container');
        if (containers.length > 0) {
            result.ready = true;
            result.details = { containers: containers.length };
        }
        return result;
    }

    // --- OpenLayers ------------------------------------------------------
    if (window.ol && window.ol.Map) {
        result.framework = 'openlayers';
        const olMaps = document.querySelectorAll('.ol-viewport');
        if (olMaps.length > 0) {
            result.ready = true;
            result.details = { viewports: olMaps.length };
        }
        return result;
    }

    // --- Angular / React wrappers ----------------------------------------
    const ngRoot = document.querySelector('[ng-version]')
        || document.querySelector('app-root');
    if (ngRoot) {
        result.framework = 'angular';
        // Check for any canvas or known map container inside
        const canvas = ngRoot.querySelector('canvas');
        const mapDiv = ngRoot.querySelector(
            '[class*="map"], [id*="map"], .esri-view, .leaflet-container, .ol-viewport'
        );
        result.ready = !!(canvas || mapDiv);
        result.details = {
            hasCanvas: !!canvas,
            hasMapDiv: !!mapDiv,
        };
        return result;
    }
    const reactRoot = document.getElementById('root')
        || document.getElementById('app');
    if (reactRoot && reactRoot.querySelector('[data-reactroot], [class*="map"]')) {
        result.framework = 'react';
        const canvas = reactRoot.querySelector('canvas');
        result.ready = !!canvas;
        result.details = { hasCanvas: !!canvas };
        return result;
    }

    // --- Iframe containing a map -----------------------------------------
    const iframes = document.querySelectorAll('iframe');
    for (const iframe of iframes) {
        const src = iframe.src || '';
        if (src && (
            src.includes('map') || src.includes('geomap') ||
            src.includes('arcgis') || src.includes('geoportal')
        )) {
            result.hasIframe = true;
            result.iframeSrc = src;
            result.framework = 'iframe';
            result.ready = true;
            return result;
        }
    }
    // Also check iframes without obvious src keywords
    if (iframes.length > 0) {
        result.hasIframe = true;
        result.iframeSrc = iframes[0].src || '(no src)';
        result.details = { totalIframes: iframes.length };
    }

    // --- Generic canvas check (last resort) ------------------------------
    const canvases = document.querySelectorAll('canvas');
    if (canvases.length > 0) {
        result.framework = 'unknown-canvas';
        result.ready = true;
        result.details = { canvases: canvases.length };
        return result;
    }

    return result;
}
"""

# ---------------------------------------------------------------------------
# Zoom / click helpers for each framework
# ---------------------------------------------------------------------------

ZOOM_AND_CLICK_ARCGIS_JS = """
(coords) => {
    let view = window.view
        || (window.app && window.app.view)
        || null;
    if (!view) {
        const c = document.querySelector('.esri-view');
        if (c && c.__view) view = c.__view;
    }
    if (!view) {
        for (const key of Object.keys(window)) {
            const v = window[key];
            if (v && typeof v === 'object' && v.toScreen && v.goTo) {
                view = v; break;
            }
        }
    }
    if (!view) return { error: 'arcgis view not found' };

    return view.goTo({ center: [coords.lng, coords.lat], zoom: 17 })
        .then(() => {
            const sp = view.toScreen({
                type: 'point', latitude: coords.lat, longitude: coords.lng,
                spatialReference: { wkid: 4326 },
            });
            return { x: Math.round(sp.x), y: Math.round(sp.y) };
        })
        .catch(e => ({ error: e.message }));
}
"""

ZOOM_AND_CLICK_LEAFLET_JS = """
(coords) => {
    // Find the first Leaflet map instance
    let map = null;
    document.querySelectorAll('.leaflet-container').forEach(el => {
        if (el._leaflet_map) map = el._leaflet_map;
        // Alternative: check L._mapInstances or iterate window properties
    });
    if (!map) {
        for (const key of Object.keys(window)) {
            const v = window[key];
            if (v && v._container && v.setView && v.latLngToContainerPoint) {
                map = v; break;
            }
        }
    }
    if (!map) return { error: 'leaflet map not found' };

    map.setView([coords.lat, coords.lng], 17);
    const pt = map.latLngToContainerPoint([coords.lat, coords.lng]);
    return { x: Math.round(pt.x), y: Math.round(pt.y) };
}
"""

ZOOM_AND_CLICK_OPENLAYERS_JS = """
(coords) => {
    // OpenLayers stores map on the viewport's parent
    const viewport = document.querySelector('.ol-viewport');
    if (!viewport) return { error: 'ol-viewport not found' };
    const mapEl = viewport.parentElement;
    // OL map instances are often stored as a property on the element
    let map = null;
    for (const key of Object.keys(mapEl)) {
        if (mapEl[key] && mapEl[key].getView && mapEl[key].getPixelFromCoordinate) {
            map = mapEl[key]; break;
        }
    }
    if (!map) return { error: 'openlayers map not found' };

    const view = map.getView();
    const coord = ol.proj.fromLonLat([coords.lng, coords.lat]);
    view.setCenter(coord);
    view.setZoom(17);
    map.renderSync();
    const pixel = map.getPixelFromCoordinate(coord);
    return { x: Math.round(pixel[0]), y: Math.round(pixel[1]) };
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_evaluate(target: Page | Frame, expression: str, arg=None):
    """Run evaluate wrapped in a try/except for resilience."""
    try:
        if arg is not None:
            return await target.evaluate(expression, arg)
        return await target.evaluate(expression)
    except Exception as exc:
        log.warning("evaluate failed: %s", exc)
        return None


async def _screenshot(page: Page, name: str) -> None:
    """Save a screenshot to the screenshots directory."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / name
    await page.screenshot(path=str(path), full_page=False)
    log.info("Screenshot: %s", path)


async def _get_map_context(page: Page) -> tuple[Page | Frame, dict]:
    """Detect map framework and return the right execution context.

    If the map lives inside an iframe, returns the iframe Frame object
    so all subsequent evaluate() calls target the correct context.

    Returns:
        (context, detection_result) where context is Page or Frame.
    """
    detection = await _safe_evaluate(page, DETECT_MAP_FRAMEWORK_JS)
    log.info("Map framework detection: %s", detection)

    if not detection:
        return page, {"framework": None, "ready": False}

    # If the map is inside an iframe, switch context
    if detection.get("framework") == "iframe" or detection.get("hasIframe"):
        iframe_src = detection.get("iframeSrc", "")
        log.info("Map detected in iframe: %s", iframe_src)

        # Find the matching iframe Frame in Playwright
        for frame in page.frames:
            if frame.url and (
                "map" in frame.url.lower()
                or "geomap" in frame.url.lower()
                or "arcgis" in frame.url.lower()
                or "geoportal" in frame.url.lower()
                or frame.url == iframe_src
            ):
                log.info("Switched to iframe context: %s", frame.url)
                # Re-detect framework inside the iframe
                inner = await _safe_evaluate(frame, DETECT_MAP_FRAMEWORK_JS)
                log.info("Inner iframe detection: %s", inner)
                return frame, inner or detection

        log.warning("Could not switch to iframe context; staying on main page.")

    return page, detection


# ---------------------------------------------------------------------------
# Approach A: Click on map at target coordinates
# ---------------------------------------------------------------------------

async def approach_a_click_map(
    page: Page,
    capture: RequestCapture,
) -> None:
    """Zoom to target coordinates and click on the map canvas."""
    log.info("=== APPROACH A: Click map at %.4f, %.4f ===", TARGET_LAT, TARGET_LNG)

    # Detect framework and get correct context (page or iframe)
    ctx, detection = await _get_map_context(page)
    framework = detection.get("framework") if detection else None
    log.info("Using framework: %s", framework)

    # Wait for map readiness with a generous timeout
    if not detection or not detection.get("ready"):
        log.info("Waiting for map to become ready (up to %ds)...", MAP_LOAD_TIMEOUT_MS // 1000)
        try:
            await ctx.wait_for_function(
                "() => { const c = document.querySelector('canvas, .leaflet-container, .ol-viewport, .esri-view'); return !!c; }",
                timeout=MAP_LOAD_TIMEOUT_MS,
            )
            await page.wait_for_timeout(3_000)
            # Re-detect after waiting
            ctx, detection = await _get_map_context(page)
            framework = detection.get("framework") if detection else None
        except Exception:
            log.warning("Map readiness wait timed out.")

    capture.set_phase("map_ready")
    await page.wait_for_timeout(2_000)

    # Choose the right zoom/click JS for the framework
    coords = {"lat": TARGET_LAT, "lng": TARGET_LNG}
    screen_pt = None

    if framework == "arcgis":
        screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_ARCGIS_JS, coords)
    elif framework == "leaflet":
        screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_LEAFLET_JS, coords)
    elif framework == "openlayers":
        screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_OPENLAYERS_JS, coords)
    else:
        log.warning("Unknown framework '%s'; will try ArcGIS then fallback.", framework)
        screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_ARCGIS_JS, coords)
        if not screen_pt or "error" in (screen_pt or {}):
            screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_LEAFLET_JS, coords)
        if not screen_pt or "error" in (screen_pt or {}):
            screen_pt = await _safe_evaluate(ctx, ZOOM_AND_CLICK_OPENLAYERS_JS, coords)

    log.info("Screen point result: %s", screen_pt)

    # Fallback: center of canvas
    if not screen_pt or "error" in (screen_pt or {}):
        log.warning("Framework zoom/click failed. Falling back to center-of-canvas.")
        # Try to find canvas in the right context
        if isinstance(ctx, Frame):
            canvas_el = ctx.locator("canvas").first
        else:
            canvas_el = page.locator("canvas").first
        box = await canvas_el.bounding_box()
        if box:
            screen_pt = {"x": int(box["width"] / 2), "y": int(box["height"] / 2)}
        else:
            log.error("No canvas found for click. Skipping Approach A.")
            return

    await _screenshot(page, "A_before_click.png")

    # Perform the click — target the topmost interactive map layer.
    # MapLibre GL / MapBox GL renders a <div> overlay above the <canvas>,
    # so we try multiple selectors in order of priority.
    capture.set_phase("after_click")
    log.info("Clicking at (%s, %s)...", screen_pt["x"], screen_pt["y"])

    click_target = isinstance(ctx, Frame) and ctx or page

    # Priority order: MapLibre/MapBox overlay > Leaflet container > canvas
    click_selectors = [
        ".maplibregl-canvas-container, .mapboxgl-canvas-container",
        ".leaflet-gl-layer",
        ".leaflet-container",
        "canvas",
    ]
    clicked = False
    for selector in click_selectors:
        el = click_target.locator(selector).first
        if await el.count() > 0:
            log.info("Clicking on element: %s", selector)
            try:
                await el.click(
                    position={"x": screen_pt["x"], "y": screen_pt["y"]},
                    timeout=10_000,
                )
                clicked = True
                break
            except Exception as click_exc:
                log.warning("Click on '%s' failed: %s. Trying next.", selector, click_exc)

    # Last resort: force-click on the page coordinates directly
    if not clicked:
        log.warning("All selectors failed. Force-clicking via page.mouse.")
        try:
            # Get canvas bounding box for absolute coordinates
            canvas_el = click_target.locator("canvas").first
            box = await canvas_el.bounding_box()
            if box:
                abs_x = box["x"] + screen_pt["x"]
                abs_y = box["y"] + screen_pt["y"]
                await page.mouse.click(abs_x, abs_y)
                clicked = True
        except Exception as mouse_exc:
            log.error("Force mouse click failed: %s", mouse_exc)

    if clicked:
        log.info("Waiting %ds for API responses after click...", POST_CLICK_WAIT_S)
        await page.wait_for_timeout(POST_CLICK_WAIT_S * 1_000)
    else:
        log.error("Could not click the map. Continuing to Approach B.")

    await _screenshot(page, "A_after_click.png")


# ---------------------------------------------------------------------------
# Approach B: Navigate to direct parcel URL
# ---------------------------------------------------------------------------

async def approach_b_parcel_url(
    page: Page,
    capture: RequestCapture,
) -> None:
    """Navigate to a direct parcel-ID URL and capture what fires."""
    log.info("=== APPROACH B: Direct parcel URL %s ===", PARCEL_URL)
    capture.set_phase("parcel_url_load")

    try:
        await page.goto(PARCEL_URL, wait_until="domcontentloaded", timeout=60_000)
    except Exception as exc:
        log.warning("Parcel URL navigation issue: %s", exc)

    current = page.url
    log.info("Current URL after parcel nav: %s", current)

    await _screenshot(page, "B_after_parcel_nav.png")

    # Wait for map / data to load
    log.info("Waiting %ds for parcel data to load...", POST_CLICK_WAIT_S)
    await page.wait_for_timeout(POST_CLICK_WAIT_S * 1_000)

    await _screenshot(page, "B_parcel_loaded.png")

    # Check if there are any popups or panels with parcel info
    body_text = await _safe_evaluate(page, "() => document.body.innerText") or ""
    found_fields = [f for f in ARABIC_FIELDS if f in body_text]
    if found_fields:
        log.info("Arabic fields found in page text: %s", found_fields)
    else:
        log.info("No Arabic fields found directly in page text.")


# ---------------------------------------------------------------------------
# Summary & analysis
# ---------------------------------------------------------------------------

def print_summary(capture: RequestCapture) -> None:
    """Log a summary of captured traffic."""
    total = len(capture.entries)
    by_phase: dict[str, int] = {}
    for e in capture.entries:
        by_phase[e["phase"]] = by_phase.get(e["phase"], 0) + 1

    key_hits = [
        e for e in capture.entries
        if any(p in e.get("url", "").lower() for p in KEY_API_PATTERNS)
        and e.get("resource_type") in ("xhr", "fetch", "websocket")
    ]
    arabic_hits = [e for e in capture.entries if e.get("contains_arabic_fields")]

    log.info("=" * 70)
    log.info("CAPTURE SUMMARY")
    log.info("  Total requests captured: %d", total)
    for phase, count in sorted(by_phase.items()):
        log.info("    %s: %d", phase, count)
    log.info("  Key API XHR/fetch hits: %d", len(key_hits))
    log.info("  Responses with Arabic parcel fields: %d", len(arabic_hits))

    if key_hits:
        log.info("  Key API URLs:")
        for h in key_hits:
            log.info(
                "    [%s] %s %s -> %s",
                h["phase"], h.get("method", "?"),
                h["url"][:140], h.get("status", "?"),
            )

    if arabic_hits:
        log.info("  Arabic field matches:")
        for h in arabic_hits:
            log.info(
                "    [%s] %s -> fields: %s",
                h["phase"], h["url"][:120],
                h["contains_arabic_fields"],
            )
    log.info("=" * 70)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run() -> None:
    """Execute the full capture workflow."""
    capture = RequestCapture()
    browser = None

    async with async_playwright() as pw:
        try:
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
                java_script_enabled=True,
            )
            page: Page = await context.new_page()

            # --- Attach listeners -----------------------------------------
            page.on("response", capture.on_response)
            page.on("console", capture.on_console)
            page.on("websocket", lambda ws: capture.on_websocket(ws, capture))

            # === APPROACH A: Open map and click ============================
            log.info("Navigating to %s", TARGET_URL)
            page_loaded = False
            try:
                await page.goto(
                    TARGET_URL, wait_until="domcontentloaded", timeout=60_000,
                )
                page_loaded = True
            except Exception as exc:
                log.warning("Navigation issue (continuing): %s", exc)

            current_url = page.url
            log.info("Current URL: %s", current_url)
            await _screenshot(page, "00_after_nav.png")

            if not page_loaded or "about:" in current_url or "chrome-error" in current_url:
                log.error("Page did not load: %s", current_url)
                return

            # Cloudflare / challenge check
            body_text = await _safe_evaluate(
                page, "() => (document.body.innerText || '').substring(0, 500)",
            ) or ""
            if "checking your browser" in body_text.lower():
                log.info("Cloudflare challenge detected; waiting 30s...")
                try:
                    await page.wait_for_function(
                        "() => !document.body.innerText.toLowerCase().includes('checking your browser')",
                        timeout=30_000,
                    )
                    await page.wait_for_timeout(3_000)
                except Exception:
                    log.warning("Cloudflare challenge may not have cleared.")

            # Give the page some time to initialize JS frameworks
            await page.wait_for_timeout(5_000)
            await _screenshot(page, "01_page_loaded.png")

            # Run Approach A (isolated — failure won't skip Approach B)
            try:
                await approach_a_click_map(page, capture)
            except Exception as a_exc:
                log.error("Approach A failed: %s", a_exc, exc_info=True)

            # === APPROACH B: Direct parcel URL =============================
            try:
                await approach_b_parcel_url(page, capture)
            except Exception as b_exc:
                log.error("Approach B failed: %s", b_exc, exc_info=True)

            # === Summary ===================================================
            print_summary(capture)

        except Exception as exc:
            log.error("Unexpected error: %s", exc, exc_info=True)

        finally:
            try:
                capture.save(OUTPUT_FILE)
            except Exception as save_exc:
                log.error("Failed to save: %s", save_exc)
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run())
