"""Explore SREM public indicators for transaction/market data.

Opens srem.moj.gov.sa, captures all network requests, navigates
the public dashboard sections, and extracts any transaction APIs.
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

TARGET_URL = "https://srem.moj.gov.sa"
OUTPUT_DIR = Path("srem_exploration")
SS_DIR = OUTPUT_DIR / "screenshots"

TEXT_TYPES = ("json", "xml", "text", "html", "javascript", "csv")
INTERESTING_KW = (
    "indicator", "transaction", "price", "market", "dashboard",
    "stat", "report", "query", "search", "district", "city",
    "sqm", "meter", "value", "count", "average", "median",
    "api", "graphql", "rest", "data", "chart",
    "عقار", "صفقة", "مؤشر", "سعر", "متر", "معاملة",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("srem")


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
            "interesting": False,
        }
        try:
            ct = (await response.all_headers()).get("content-type", "")
            if any(t in ct for t in TEXT_TYPES):
                body = await response.text()
                entry["response_body"] = body[:5000]
                combined = (req.url + (body[:2000] if body else "")).lower()
                if any(kw in combined for kw in INTERESTING_KW):
                    entry["interesting"] = True
        except Exception:
            pass
        self.entries.append(entry)
        if req.resource_type in ("xhr", "fetch"):
            flag = " ***" if entry["interesting"] else ""
            log.info(
                "[%s] %s %s -> %d%s",
                self.phase, req.method, req.url[:150], response.status, flag,
            )


async def ss(page: Page, name: str) -> None:
    SS_DIR.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SS_DIR / name), full_page=True)


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
            locale="ar-SA",
        )

        try:
            page: Page = await ctx.new_page()
            page.on("response", cap.on_response)

            # === Load main page ===
            log.info("Loading %s", TARGET_URL)
            try:
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                log.warning("Nav: %s", exc)

            await page.wait_for_timeout(5_000)
            log.info("URL: %s", page.url)
            await ss(page, "00_main.png")

            # Save HTML
            html = await page.content()
            (OUTPUT_DIR / "main_page.html").write_text(html, encoding="utf-8")

            # === Find navigation links ===
            log.info("Finding navigation links...")
            nav_links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href || '';
                        const text = (a.innerText || '').trim();
                        if (text && href && !href.includes('javascript:') && text.length < 100) {
                            links.push({ href, text: text.substring(0, 80) });
                        }
                    });
                    return links;
                }
            """)
            (OUTPUT_DIR / "nav_links.json").write_text(
                json.dumps(nav_links, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            log.info("Found %d links", len(nav_links))

            # Filter for indicator/dashboard/public links
            indicator_keywords = [
                "مؤشر", "indicator", "dashboard", "لوحة",
                "إحصائ", "statistic", "تقرير", "report",
                "صفق", "transaction", "سوق", "market",
                "عقار", "real-estate", "بيانات", "data",
            ]
            target_links = []
            for link in nav_links:
                combined = (link["href"] + link["text"]).lower()
                if any(kw in combined for kw in indicator_keywords):
                    target_links.append(link)

            log.info("Indicator/dashboard links: %d", len(target_links))
            for tl in target_links:
                log.info("  %s -> %s", tl["text"][:50], tl["href"][:100])

            # === Visit each indicator page ===
            for i, link in enumerate(target_links[:8]):
                href = link["href"]
                text = link["text"]
                cap.phase = f"page_{i}_{text[:20]}"

                log.info("\nVisiting [%d]: %s -> %s", i, text[:50], href[:100])
                try:
                    await page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(5_000)
                    await ss(page, f"page_{i:02d}.png")
                    log.info("  URL: %s", page.url)

                    # Check if login is required
                    body_text = await page.evaluate(
                        "() => (document.body?.innerText || '').substring(0, 1000)"
                    )
                    if body_text and ("تسجيل الدخول" in body_text or "login" in body_text.lower()):
                        log.info("  LOGIN REQUIRED - skipping")
                        continue

                    # Scroll down to trigger lazy-loaded content
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await page.wait_for_timeout(2_000)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2_000)
                    await ss(page, f"page_{i:02d}_scrolled.png")

                except Exception as exc:
                    log.warning("  Failed: %s", exc)

            # === Also try known SREM public URLs ===
            public_urls = [
                "https://srem.moj.gov.sa/indicators",
                "https://srem.moj.gov.sa/dashboard",
                "https://srem.moj.gov.sa/statistics",
                "https://srem.moj.gov.sa/reports",
                "https://srem.moj.gov.sa/market",
                "https://srem.moj.gov.sa/public",
                "https://srem.moj.gov.sa/transactions",
            ]

            for url in public_urls:
                slug = url.split("/")[-1]
                cap.phase = f"try_{slug}"
                log.info("\nTrying: %s", url)
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                    await page.wait_for_timeout(3_000)
                    final_url = page.url
                    log.info("  -> %s (status via page)", final_url)
                    if final_url != url and "login" in final_url.lower():
                        log.info("  Redirected to login - requires auth")
                    else:
                        await ss(page, f"try_{slug}.png")
                except Exception as exc:
                    log.warning("  Failed: %s", exc)

            # === Summary ===
            log.info("\n" + "=" * 60)
            log.info("SUMMARY")
            log.info("=" * 60)
            total = len(cap.entries)
            xhr = [e for e in cap.entries if e["type"] in ("xhr", "fetch")]
            interesting = [e for e in cap.entries if e["interesting"]]
            log.info("Total requests: %d", total)
            log.info("XHR/fetch: %d", len(xhr))
            log.info("Interesting: %d", len(interesting))

            # Print interesting endpoints
            seen: set[str] = set()
            for e in interesting:
                key = f"{e['method']} {e['url'][:100]}"
                if key not in seen:
                    seen.add(key)
                    log.info("  [%s] %s %s -> %d", e["phase"], e["method"], e["url"][:140], e["status"])

        except Exception as exc:
            log.error("Fatal: %s", exc, exc_info=True)

        finally:
            req_file = OUTPUT_DIR / "srem_public_api.json"
            payload = {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "total": len(cap.entries),
                "interesting_count": len([e for e in cap.entries if e["interesting"]]),
                "requests": cap.entries,
            }
            req_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            log.info("Saved %d requests to %s", len(cap.entries), req_file)
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
