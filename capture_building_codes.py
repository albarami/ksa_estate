"""Capture the Riyadh building-codes lookup page and extract every code.

Opens the eServices BuildingCodes.aspx page, enumerates every option in
the building-code dropdown, selects each one, captures the resulting
regulation details, and saves all data to JSON.
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

TARGET_URL = (
    "https://eservices.alriyadh.gov.sa/Pages/BLS/Common/BuildingCodes.aspx"
)

OUTPUT_DIR = Path("building_codes_output")
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
PAGE_HTML_FILE = OUTPUT_DIR / "building_codes_page.html"
ALL_CODES_FILE = OUTPUT_DIR / "building_codes_all.json"
REQUESTS_FILE = OUTPUT_DIR / "building_codes_captured_requests.json"

TEXT_CONTENT_TYPES = ("json", "xml", "text", "html", "javascript", "csv")

# Arabic field names we're hunting for in regulation details
REGULATION_FIELDS_AR = (
    "عدد الأدوار",
    "نسبة البناء",
    "الارتداد",
    "الاستعمالات المسموحة",
    "أقصى ارتفاع",
    "نسبة التغطية",
    "مواقف السيارات",
    "ارتداد أمامي",
    "ارتداد جانبي",
    "ارتداد خلفي",
    "نظام البناء",
    "شروط البناء",
    "الاستعمال",
)

# Specific codes we know about from parcel queries
PRIORITY_CODES = ["م 111", "س 111", "T5 2 مختلط دورين"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("bldcodes")


# ---------------------------------------------------------------------------
# Network capture
# ---------------------------------------------------------------------------

class RequestCapture:
    """Lightweight request/response capture."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.phase: str = "initial_load"

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    async def on_response(self, response: Response) -> None:
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
            "response_headers": await response.all_headers(),
            "response_body": None,
        }
        try:
            ct = (await response.all_headers()).get("content-type", "")
            if any(t in ct for t in TEXT_CONTENT_TYPES):
                entry["response_body"] = await response.text()
        except Exception:
            entry["response_body"] = "<unavailable>"
        self.entries.append(entry)

        if request.resource_type in ("xhr", "fetch"):
            log.info(
                "[%s] XHR %s %s -> %d",
                self.phase, request.method,
                request.url[:160], response.status,
            )

    def save(self, path: Path) -> None:
        payload = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "total": len(self.entries),
            "requests": self.entries,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Saved %d requests to %s", len(self.entries), path)


# ---------------------------------------------------------------------------
# Screenshot helper
# ---------------------------------------------------------------------------

async def _ss(page: Page, name: str) -> None:
    """Save a screenshot."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / name
    await page.screenshot(path=str(path), full_page=True)
    log.info("Screenshot: %s", path)


# ---------------------------------------------------------------------------
# Page analysis helpers
# ---------------------------------------------------------------------------

async def discover_form_controls(page: Page) -> dict:
    """Find all interactive form controls on the page."""
    controls = await page.evaluate("""
        () => {
            const result = { selects: [], inputs: [], buttons: [], tables: [] };

            // Dropdowns / selects
            document.querySelectorAll('select').forEach(el => {
                const options = Array.from(el.options).map(o => ({
                    value: o.value,
                    text: o.text.trim(),
                    selected: o.selected,
                }));
                result.selects.push({
                    id: el.id,
                    name: el.name,
                    className: el.className,
                    optionCount: options.length,
                    options: options,
                });
            });

            // Text inputs
            document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])').forEach(el => {
                result.inputs.push({
                    id: el.id,
                    name: el.name,
                    placeholder: el.placeholder,
                    value: el.value,
                    className: el.className,
                });
            });

            // Buttons / submits
            document.querySelectorAll('button, input[type="submit"], input[type="button"], a.btn').forEach(el => {
                result.buttons.push({
                    id: el.id,
                    name: el.name || '',
                    text: el.innerText?.trim().substring(0, 80) || '',
                    type: el.type || el.tagName,
                    className: el.className,
                });
            });

            // Tables on the page
            document.querySelectorAll('table').forEach((table, idx) => {
                const headers = Array.from(
                    table.querySelectorAll('thead th, tr:first-child th')
                ).map(th => th.innerText.trim());
                const rowCount = table.querySelectorAll('tbody tr, tr').length;
                result.tables.push({
                    index: idx,
                    id: table.id,
                    className: table.className,
                    headers: headers,
                    rowCount: rowCount,
                });
            });

            return result;
        }
    """)
    return controls


async def extract_visible_text(page: Page) -> str:
    """Get all visible text from the page body."""
    return await page.evaluate("() => document.body.innerText") or ""


async def extract_regulation_table(page: Page) -> list[dict]:
    """Extract any visible regulation data from tables or labeled fields."""
    return await page.evaluate("""
        () => {
            const results = [];

            // Strategy 1: look for label-value pairs (common in .aspx pages)
            // e.g. <span class="label">عدد الأدوار</span> <span>3</span>
            const labels = document.querySelectorAll(
                'td, th, span, label, div, dt, .label, .field-label'
            );
            const labelMap = {};
            labels.forEach(el => {
                const text = el.innerText?.trim();
                if (!text || text.length > 100) return;
                // Find the adjacent sibling or next cell with a value
                const next = el.nextElementSibling;
                if (next) {
                    const val = next.innerText?.trim();
                    if (val && val.length < 500) {
                        labelMap[text] = val;
                    }
                }
                // Also check parent row for table cells
                const row = el.closest('tr');
                if (row) {
                    const cells = Array.from(row.querySelectorAll('td, th'));
                    if (cells.length >= 2) {
                        const key = cells[0].innerText?.trim();
                        const value = cells.slice(1).map(
                            c => c.innerText?.trim()
                        ).join(' | ');
                        if (key && key.length < 100) {
                            labelMap[key] = value;
                        }
                    }
                }
            });
            results.push({ type: 'label_value_pairs', data: labelMap });

            // Strategy 2: extract all tables as arrays
            document.querySelectorAll('table').forEach((table, idx) => {
                const headers = Array.from(
                    table.querySelectorAll('thead th, tr:first-child th, tr:first-child td')
                ).map(th => th.innerText.trim());

                const rows = [];
                table.querySelectorAll('tbody tr, tr').forEach(tr => {
                    const cells = Array.from(tr.querySelectorAll('td'))
                        .map(td => td.innerText.trim());
                    if (cells.length > 0) rows.push(cells);
                });

                if (rows.length > 0) {
                    results.push({
                        type: 'table',
                        index: idx,
                        id: table.id,
                        headers: headers,
                        rows: rows,
                    });
                }
            });

            // Strategy 3: look for div-based cards/panels with regulation data
            document.querySelectorAll(
                '.panel, .card, .detail, .result, [class*="regulation"], [class*="code"]'
            ).forEach(panel => {
                const text = panel.innerText?.trim();
                if (text && text.length > 10 && text.length < 2000) {
                    results.push({ type: 'panel', text: text });
                }
            });

            return results;
        }
    """)


async def extract_all_dropdown_options(page: Page, select_id: str) -> list[dict]:
    """Extract every option from a <select> element."""
    return await page.evaluate("""
        (selectId) => {
            const el = document.getElementById(selectId)
                     || document.querySelector(`select[name="${selectId}"]`)
                     || document.querySelector('select');
            if (!el) return [];
            return Array.from(el.options).map(o => ({
                value: o.value,
                text: o.text.trim(),
            }));
        }
    """, select_id)


# ---------------------------------------------------------------------------
# Core: iterate codes and capture regulations
# ---------------------------------------------------------------------------

async def iterate_codes(
    page: Page,
    select_id: str,
    options: list[dict],
    capture: RequestCapture,
) -> list[dict]:
    """Select each building-code option and extract the resulting regs."""
    all_codes: list[dict] = []

    for i, option in enumerate(options):
        code_value = option["value"]
        code_text = option["text"]

        # Skip placeholder / empty options
        if not code_value or code_value == "0" or code_text in (
            "", "--", "اختر", "Select", "اختر نظام البناء",
        ):
            log.info("  [%d/%d] Skipping placeholder: '%s'", i + 1, len(options), code_text)
            continue

        log.info(
            "  [%d/%d] Selecting code: '%s' (value=%s)",
            i + 1, len(options), code_text, code_value,
        )
        capture.set_phase(f"code_{code_value}")

        try:
            # Select the option
            await page.select_option(f"#{select_id}", code_value, timeout=5_000)
        except Exception:
            try:
                await page.select_option(
                    f"select[name='{select_id}']", code_value, timeout=5_000,
                )
            except Exception:
                # Last resort: try selecting by the <select> element directly
                try:
                    await page.locator("select").first.select_option(
                        code_value, timeout=5_000,
                    )
                except Exception as exc:
                    log.warning("    Could not select '%s': %s", code_text, exc)
                    all_codes.append({
                        "code_text": code_text,
                        "code_value": code_value,
                        "error": str(exc),
                    })
                    continue

        # Wait for postback / AJAX response
        await page.wait_for_timeout(3_000)

        # Try waiting for network idle briefly
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass

        # Extract regulation data
        regulations = await extract_regulation_table(page)
        visible_text = await extract_visible_text(page)

        # Check which Arabic fields appear
        found_fields: dict[str, str] = {}
        for field in REGULATION_FIELDS_AR:
            if field in visible_text:
                # Try to extract the value after the field name
                pattern = re.escape(field) + r"[:\s]*([^\n\r]{1,200})"
                match = re.search(pattern, visible_text)
                if match:
                    found_fields[field] = match.group(1).strip()
                else:
                    found_fields[field] = "(found but value not extracted)"

        entry = {
            "code_text": code_text,
            "code_value": code_value,
            "found_arabic_fields": found_fields,
            "regulation_data": regulations,
            "visible_text_snippet": visible_text[:2000],
        }
        all_codes.append(entry)

        if found_fields:
            log.info("    Arabic fields found: %s", list(found_fields.keys()))

        # Screenshot for priority codes or every 10th code
        is_priority = any(
            pc in code_text for pc in PRIORITY_CODES
        )
        if is_priority or i % 10 == 0:
            safe_name = re.sub(r'[^\w\-.]', '_', code_text)[:30]
            await _ss(page, f"code_{i:03d}_{safe_name}.png")

    return all_codes


# ---------------------------------------------------------------------------
# Fallback: if no dropdown, try searching for each code
# ---------------------------------------------------------------------------

async def search_for_codes(
    page: Page,
    input_selector: str,
    submit_selector: str | None,
    capture: RequestCapture,
) -> list[dict]:
    """Type each priority code into a search input and capture results."""
    all_codes: list[dict] = []

    for code_text in PRIORITY_CODES:
        log.info("  Searching for code: '%s'", code_text)
        capture.set_phase(f"search_{code_text}")

        try:
            await page.fill(input_selector, code_text, timeout=5_000)
            await page.wait_for_timeout(500)

            if submit_selector:
                await page.click(submit_selector, timeout=5_000)
            else:
                await page.press(input_selector, "Enter")

            await page.wait_for_timeout(3_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except Exception:
                pass

            regulations = await extract_regulation_table(page)
            visible_text = await extract_visible_text(page)

            found_fields: dict[str, str] = {}
            for field in REGULATION_FIELDS_AR:
                if field in visible_text:
                    pattern = re.escape(field) + r"[:\s]*([^\n\r]{1,200})"
                    match = re.search(pattern, visible_text)
                    if match:
                        found_fields[field] = match.group(1).strip()

            safe_name = re.sub(r'[^\w\-.]', '_', code_text)[:30]
            await _ss(page, f"search_{safe_name}.png")

            all_codes.append({
                "code_text": code_text,
                "code_value": code_text,
                "found_arabic_fields": found_fields,
                "regulation_data": regulations,
                "visible_text_snippet": visible_text[:2000],
            })

            if found_fields:
                log.info("    Arabic fields found: %s", list(found_fields.keys()))

        except Exception as exc:
            log.warning("    Search failed for '%s': %s", code_text, exc)
            all_codes.append({
                "code_text": code_text,
                "error": str(exc),
            })

    return all_codes


# ---------------------------------------------------------------------------
# TRC guide: scrape each building-category page for regulation tables
# ---------------------------------------------------------------------------

TRC_BASE = "https://trc.alriyadh.gov.sa"

async def scrape_trc_categories(
    page: Page,
    capture: RequestCapture,
) -> list[dict]:
    """Open the TRC guide, click each category, extract regulation tables."""
    results: list[dict] = []
    capture.set_phase("trc_guide")

    log.info("Navigating to TRC guide: %s", TRC_BASE)
    try:
        await page.goto(TRC_BASE, wait_until="networkidle", timeout=60_000)
    except Exception as exc:
        log.warning("TRC navigation: %s", exc)

    await page.wait_for_timeout(2_000)
    await _ss(page, "trc_00_index.png")

    # The TRC index page lists categories as clickable rows/links.
    # Each one opens a detail page with regulation tables.
    categories = await page.evaluate("""
        () => {
            const items = [];
            // The TRC page has a list of clickable items — usually <a> or
            // clickable <div> rows, each with a title and an expand icon
            const links = document.querySelectorAll(
                'a[href], .accordion-item, .list-group-item, [class*="item"]'
            );
            links.forEach(el => {
                const text = el.innerText?.trim();
                const href = el.href || el.getAttribute('data-href') || '';
                if (text && text.length > 5 && text.length < 200) {
                    // Filter to building-regulation keywords
                    const keywords = [
                        'اشتراطات', 'requirements', 'سكني', 'تجاري',
                        'residential', 'commercial', 'building', 'بناء',
                        'مباني', 'فلل', 'villa', 'tower', 'أبراج',
                        'شقق', 'apartment', 'مكتب', 'office',
                        'مختلط', 'mixed', 'صناع', 'industrial',
                    ];
                    const lower = (text + href).toLowerCase();
                    if (keywords.some(k => lower.includes(k)) || href.includes('.html')) {
                        items.push({
                            text: text.substring(0, 150),
                            href: href,
                            tag: el.tagName,
                        });
                    }
                }
            });
            return items;
        }
    """)
    log.info("Found %d TRC category links", len(categories))

    # Also find all clickable expand icons/buttons (often info icons)
    expandable = await page.query_selector_all(
        ".info-icon, .expand-btn, [class*='expand'], "
        "[class*='detail'], .fa-info-circle, .fa-chevron-down, "
        ".accordion-button, [data-toggle='collapse']"
    )
    log.info("Found %d expandable elements", len(expandable))

    # Click each expand element to open detail panels
    for i, el in enumerate(expandable[:40]):
        try:
            await el.click(timeout=3_000)
            await page.wait_for_timeout(1_500)
        except Exception:
            pass

    # After expanding, re-screenshot and extract
    await _ss(page, "trc_01_expanded.png")

    # Now try clicking each category link to navigate to detail pages
    visited: set[str] = set()
    for i, cat in enumerate(categories[:30]):
        href = cat["href"]
        text = cat["text"]

        if href in visited or not href:
            continue
        visited.add(href)

        # Resolve relative URLs
        if href.startswith("/"):
            href = f"{TRC_BASE}{href}"
        elif not href.startswith("http"):
            href = f"{TRC_BASE}/{href}"

        # Skip external links
        if "alriyadh.gov.sa" not in href and "trc." not in href:
            continue

        log.info(
            "  [%d/%d] TRC category: '%s' -> %s",
            i + 1, len(categories), text[:60], href[:100],
        )
        capture.set_phase(f"trc_cat_{i}")

        try:
            await page.goto(href, wait_until="networkidle", timeout=30_000)
        except Exception:
            try:
                await page.goto(href, wait_until="domcontentloaded", timeout=30_000)
            except Exception as exc:
                log.warning("    Navigation failed: %s", exc)
                continue

        await page.wait_for_timeout(2_000)

        # Click any expand buttons on the detail page
        detail_expanders = await page.query_selector_all(
            ".info-icon, .expand-btn, [class*='expand'], "
            ".accordion-button, [data-toggle='collapse'], "
            ".fa-info-circle, .fa-chevron-down, .fa-plus"
        )
        for exp in detail_expanders[:20]:
            try:
                await exp.click(timeout=2_000)
                await page.wait_for_timeout(800)
            except Exception:
                pass

        # Extract tables and content
        detail_regs = await extract_regulation_table(page)
        detail_text = await extract_visible_text(page)

        # Scan for regulation fields
        found_fields: dict[str, str] = {}
        for field in REGULATION_FIELDS_AR:
            if field in detail_text:
                pattern = re.escape(field) + r"[:\s]*([^\n\r]{1,200})"
                match = re.search(pattern, detail_text)
                if match:
                    found_fields[field] = match.group(1).strip()
                else:
                    found_fields[field] = "(present)"

        entry = {
            "source": "trc_guide",
            "category_text": text,
            "category_url": href,
            "found_arabic_fields": found_fields,
            "regulation_data": detail_regs,
            "visible_text_snippet": detail_text[:3000],
        }
        results.append(entry)

        if found_fields:
            log.info("    Fields found: %s", list(found_fields.keys()))

        # Screenshot notable pages
        if found_fields or i < 5 or i % 5 == 0:
            safe = re.sub(r'[^\w\-.]', '_', text)[:30]
            await _ss(page, f"trc_cat_{i:02d}_{safe}.png")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run() -> None:
    """Execute the building-codes capture workflow."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

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
            )
            page: Page = await context.new_page()
            page.on("response", capture.on_response)

            # === Navigate =================================================
            log.info("Navigating to %s", TARGET_URL)
            try:
                await page.goto(
                    TARGET_URL, wait_until="domcontentloaded", timeout=60_000,
                )
            except Exception as exc:
                log.warning("Navigation issue: %s", exc)

            await page.wait_for_timeout(3_000)

            current = page.url
            log.info("Current URL: %s", current)
            await _ss(page, "00_initial_page.png")

            # Save full page HTML
            html = await page.content()
            PAGE_HTML_FILE.write_text(html, encoding="utf-8")
            log.info("Saved HTML (%d chars): %s", len(html), PAGE_HTML_FILE)

            # === Discover form controls ===================================
            log.info("Discovering form controls...")
            controls = await discover_form_controls(page)
            controls_file = OUTPUT_DIR / "form_controls.json"
            controls_file.write_text(
                json.dumps(controls, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(
                "Controls: %d selects, %d inputs, %d buttons, %d tables",
                len(controls["selects"]),
                len(controls["inputs"]),
                len(controls["buttons"]),
                len(controls["tables"]),
            )

            # Log details for each select
            for sel in controls["selects"]:
                log.info(
                    "  SELECT id='%s' name='%s' options=%d",
                    sel["id"], sel["name"], sel["optionCount"],
                )
                # Show first few options
                for opt in sel["options"][:5]:
                    log.info("    -> '%s' (value=%s)", opt["text"], opt["value"])
                if sel["optionCount"] > 5:
                    log.info("    ... and %d more", sel["optionCount"] - 5)

            # === Collect all PDF links from the page ======================
            log.info("Collecting PDF download links...")
            pdf_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href || '';
                        const text = a.innerText?.trim() || '';
                        const parent = a.closest('tr, li, div');
                        const context = parent?.innerText?.trim().substring(0, 200) || '';
                        if (href.toLowerCase().includes('.pdf')
                            || href.toLowerCase().includes('download')
                            || a.querySelector('img[src*="pdf"]')
                            || a.querySelector('[class*="pdf"]')) {
                            links.push({
                                href: href,
                                text: text,
                                context: context,
                            });
                        }
                    });
                    return links;
                }
            """)
            log.info("Found %d PDF links", len(pdf_links))
            for pl in pdf_links:
                log.info("  PDF: %s (%s)", pl["context"][:80], pl["href"][:120])

            # Download each PDF
            pdf_dir = OUTPUT_DIR / "pdfs"
            pdf_dir.mkdir(exist_ok=True)
            for i, pl in enumerate(pdf_links):
                href = pl["href"]
                if not href:
                    continue
                fname = href.split("/")[-1].split("?")[0] or f"code_{i}.pdf"
                log.info("  Downloading: %s -> %s", fname, href[:120])
                try:
                    resp = await context.request.get(href, timeout=30_000)
                    body = await resp.body()
                    (pdf_dir / fname).write_bytes(body)
                    log.info("    Saved %d bytes", len(body))
                    pl["downloaded"] = True
                    pl["filename"] = fname
                    pl["size_bytes"] = len(body)
                except Exception as exc:
                    log.warning("    Download failed: %s", exc)
                    pl["downloaded"] = False

            # === Extract regulation data from the visible table ===========
            log.info("Extracting visible table data...")
            regulations = await extract_regulation_table(page)
            visible_text = await extract_visible_text(page)

            all_codes: list[dict] = [{
                "source": "BuildingCodes.aspx",
                "page_title": await page.title(),
                "pdf_links": pdf_links,
                "regulation_data": regulations,
                "visible_text": visible_text[:5000],
            }]

            # === Now visit the TRC guide and scrape each category =========
            log.info("=" * 60)
            log.info("Pivoting to TRC guide for traditional building codes")
            log.info("=" * 60)

            trc_categories = await scrape_trc_categories(page, capture)
            all_codes.extend(trc_categories)

            # === Check if page uses iframes ===============================
            iframes = page.frames
            if len(iframes) > 1:
                log.info("Page has %d frames — checking for content:", len(iframes))
                for frame in iframes:
                    if frame == page.main_frame:
                        continue
                    log.info("  Frame: %s", frame.url[:120])
                    try:
                        frame_html = await frame.content()
                        if len(frame_html) > 500:
                            frame_path = OUTPUT_DIR / f"frame_{frame.name or 'unnamed'}.html"
                            frame_path.write_text(frame_html, encoding="utf-8")
                            log.info("  Saved frame HTML: %s", frame_path)
                    except Exception:
                        pass

            # === Final screenshot =========================================
            await _ss(page, "99_final_state.png")

            # === Save all codes ===========================================
            payload = {
                "meta": {
                    "source_url": TARGET_URL,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "total_codes_processed": len(all_codes),
                    "codes_with_regulations": sum(
                        1 for c in all_codes
                        if c.get("found_arabic_fields")
                    ),
                },
                "codes": all_codes,
            }
            ALL_CODES_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(
                "Saved %d codes to %s",
                len(all_codes), ALL_CODES_FILE,
            )

            # === Summary ==================================================
            log.info("=" * 60)
            log.info("SUMMARY")
            log.info("=" * 60)
            log.info("Total codes processed: %d", len(all_codes))

            codes_with_data = [
                c for c in all_codes if c.get("found_arabic_fields")
            ]
            log.info("Codes with Arabic regulation fields: %d", len(codes_with_data))

            if codes_with_data:
                for c in codes_with_data[:10]:
                    log.info(
                        "  '%s': %s",
                        c.get("code_text", "?"),
                        list(c["found_arabic_fields"].keys()),
                    )

            # Unique code texts seen
            unique_codes = sorted(set(
                c.get("code_text", "")
                for c in all_codes
                if c.get("code_text") and not c.get("error")
            ))
            log.info("Unique building codes found: %d", len(unique_codes))
            for code in unique_codes[:20]:
                log.info("  %s", code)
            if len(unique_codes) > 20:
                log.info("  ... and %d more", len(unique_codes) - 20)

        except Exception as exc:
            log.error("Fatal error: %s", exc, exc_info=True)

        finally:
            try:
                capture.save(REQUESTS_FILE)
            except Exception as exc:
                log.error("Failed to save requests: %s", exc)
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run())
