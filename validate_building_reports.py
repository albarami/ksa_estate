"""Validate the BuildingSystem PDF report across multiple parcels.

Downloads the building-code-report for each parcel, extracts text
from the PDF, parses regulation values into structured JSON, and
prints a comparison table.
"""

import asyncio
import json
import re
from pathlib import Path

import fitz  # PyMuPDF
from playwright.async_api import async_playwright

REPORT_URL = (
    "https://mapservice.alriyadh.gov.sa/BuildingSystem/"
    "building-code-report-experimental?parcelId={pid}"
)
PARCEL_IDS = [3710897, 3710898, 3900000]
PDF_DIR = Path("building_reports")
OUT = Path("building_regulations_decoded_final.json")


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text("text")
    doc.close()
    return text


# ---------------------------------------------------------------------------
# Parse regulation values from Arabic PDF text
# ---------------------------------------------------------------------------

def parse_regulations(text: str, parcel_id: int) -> dict:
    """Parse structured regulation data from the PDF text."""
    result: dict = {
        "parcel_id": parcel_id,
        "raw_text": text,
        "building_code": None,
        "allowed_uses": [],
        "max_floors": None,
        "floors_description": None,
        "far": None,
        "coverage_ratio": None,
        "setbacks": {},
        "parking": None,
        "notes": [],
        "plan_number": None,
        "parcel_number": None,
        "district": None,
        "municipality": None,
    }

    # Work line-by-line — the PDF text is structured with clear sections
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    cleaned = " ".join(lines)

    # --- Building code (line containing م or س followed by digits) ---
    for line in lines:
        m = re.search(r'(\d{3})\s*([مس])', line)
        if m:
            result["building_code"] = f"{m.group(2)} {m.group(1)}"
            break
    # Also try T-codes
    if not result["building_code"]:
        t_match = re.search(r'(T\d+[\s.]*\d*)', cleaned)
        if t_match:
            result["building_code"] = t_match.group(1).strip()

    # --- Plan/parcel from the combined line like "المخطط رقم3114القطعة رقم2045" ---
    plan_m = re.search(r'اﻟﻤﺨﻄﻂ\s*رﻗﻢ\s*(\d+)', cleaned)
    if not plan_m:
        plan_m = re.search(r'المخطط\s*رقم\s*(\d+)', cleaned)
    if plan_m:
        result["plan_number"] = plan_m.group(1)

    parcel_m = re.search(r'اﻟﻘﻄﻌﺔ\s*رﻗﻢ\s*(\d+)', cleaned)
    if not parcel_m:
        parcel_m = re.search(r'القطعة\s*رقم\s*(\d+)', cleaned)
    if parcel_m:
        result["parcel_number"] = parcel_m.group(1)

    # --- District (line after اﻟﺤﻲ اﺳﻢ or standalone district name) ---
    for i, line in enumerate(lines):
        if "اﳌﻠﻘﺎ" in line or "الملقا" in line:
            result["district"] = "الملقا"
        if "اﻟﺤﻲ" in line and i + 1 < len(lines):
            result["district"] = lines[i + 1] if len(lines[i + 1]) < 30 else result["district"]

    # --- Municipality ---
    for line in lines:
        if "ﻗﻄﺎع" in line or "قطاع" in line:
            result["municipality"] = line

    # --- Allowed uses (section: اﻻﺳﺘﺨﺪاﻣﺎت then individual lines) ---
    use_map = {
        "ﺳﻜﻨﻲ": "residential", "سكني": "residential", "سكنى": "residential",
        "ﺗﺠﺎري": "commercial", "تجاري": "commercial",
        "ﻣﻜﺎﺗﺐ": "offices", "مكاتب": "offices",
        "ﻣﺨﺘﻠﻂ": "mixed_use", "مختلط": "mixed_use",
        "ﺻﻨﺎﻋﻲ": "industrial", "صناعي": "industrial",
    }
    in_uses = False
    for line in lines:
        if "اﻻﺳﺘﺨﺪاﻣﺎت" in line or "الاستخدامات" in line:
            in_uses = True
            continue
        if in_uses:
            if "اﻻرﺗﺪاد" in line or "الارتداد" in line:
                in_uses = False
                continue
            for ar, en in use_map.items():
                if ar in line and en not in result["allowed_uses"]:
                    result["allowed_uses"].append(en)

    # --- Floors (section: اﻻرﺗﻔﺎﻋﺎت) ---
    floor_section_found = False
    for i, line in enumerate(lines):
        if "اﻻرﺗﻔﺎﻋﺎت" in line or "الارتفاعات" in line:
            floor_section_found = True
            # Collect next few lines until we hit the next section
            floor_text = " ".join(lines[i + 1:i + 4])
            result["floors_description"] = floor_text
            continue

    # Parse floor count from common patterns across entire text
    if "أول" in cleaned and ("أرﴈ" in cleaned or "أرضي" in cleaned):
        result["max_floors"] = 2
    elif "دورين" in cleaned:
        result["max_floors"] = 2
    elif "ثلاث" in cleaned:
        result["max_floors"] = 3
    elif "أربع" in cleaned:
        result["max_floors"] = 4

    # --- FAR (line containing ﻣﻌﺎﻣﻞ and a decimal) ---
    far_m = re.search(r'(?:ﻣﻌﺎﻣﻞ|معامل).*?(\d+\.?\d+)', cleaned)
    if far_m:
        val = float(far_m.group(1))
        if 0.1 <= val <= 10:
            result["far"] = val

    # --- Coverage ratio (line containing %XX or XX%) ---
    cov_m = re.search(r'(?:ﻧﺴﺒﺔ|نسبة|ﺗﻐﻄﻴﺔ|تغطية).*?%\s*(\d+)', cleaned)
    if cov_m:
        result["coverage_ratio"] = int(cov_m.group(1)) / 100.0
    if not result["coverage_ratio"]:
        cov_m2 = re.search(r'%(\d+)', cleaned)
        if cov_m2:
            val = int(cov_m2.group(1))
            if 20 <= val <= 100:
                result["coverage_ratio"] = val / 100.0

    # --- Setbacks (section: اﻻرﺗﺪادات) ---
    in_setback = False
    setback_lines = []
    for line in lines:
        if "اﻻرﺗﺪادات" in line or "الارتدادات" in line:
            in_setback = True
            # Capture the rest of this line too
            rest = re.sub(r'اﻻرﺗﺪادات|الارتدادات', '', line).strip()
            if rest:
                setback_lines.append(rest)
            continue
        if in_setback:
            if "اﻻرﺗﻔﺎﻋﺎت" in line or "الارتفاعات" in line:
                break
            setback_lines.append(line)
    if setback_lines:
        raw = " ".join(setback_lines)
        result["setbacks"]["raw"] = raw
        meters = re.findall(r'م(\d+\.?\d*)', raw)
        if meters:
            result["setbacks"]["meter_values"] = [float(v) for v in meters]

    # --- Parking ---
    in_parking = False
    parking_lines = []
    for line in lines:
        if "ﻣﻮاﻗﻒ" in line or "مواقف" in line:
            in_parking = True
            rest = re.sub(r'.*ﻣﻮاﻗﻒ|.*مواقف', '', line).strip()
            if rest:
                parking_lines.append(rest)
            continue
        if in_parking:
            if "اﻟﻤﻼﺣﻈﺎت" in line or "الملاحظات" in line:
                break
            parking_lines.append(line)
    if parking_lines:
        result["parking"] = " ".join(parking_lines)[:300]

    # --- Notes (section: اﻟﻤﻼﺣﻈﺎت, split on - dashes) ---
    in_notes = False
    notes_text = []
    for line in lines:
        if "اﻟﻤﻼﺣﻈﺎت" in line or "الملاحظات" in line:
            in_notes = True
            continue
        if in_notes:
            notes_text.append(line)
    if notes_text:
        full = " ".join(notes_text)
        items = re.split(r'\s*-\s*', full)
        result["notes"] = [n.strip() for n in items if len(n.strip()) > 5][:10]

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    PDF_DIR.mkdir(exist_ok=True)
    all_results: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)
        headers = {
            "Referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap",
        }

        for pid in PARCEL_IDS:
            url = REPORT_URL.format(pid=pid)
            pdf_path = PDF_DIR / f"report_{pid}.pdf"
            print(f"\n{'='*60}")
            print(f"Parcel {pid}")
            print(f"{'='*60}")

            # Download PDF
            print(f"  Downloading: {url}")
            try:
                r = await ctx.request.get(url, headers=headers, timeout=30_000)
                body = await r.body()
                print(f"  Status: {r.status}, Size: {len(body)}")

                if r.status != 200 or len(body) < 500:
                    text = body.decode("utf-8", errors="replace")
                    print(f"  ERROR: {text[:300]}")
                    all_results.append({
                        "parcel_id": pid,
                        "error": f"HTTP {r.status}, size {len(body)}",
                    })
                    continue

                pdf_path.write_bytes(body)
                print(f"  Saved: {pdf_path}")

            except Exception as exc:
                print(f"  Download failed: {exc}")
                all_results.append({"parcel_id": pid, "error": str(exc)})
                continue

            # Extract text
            text = extract_pdf_text(pdf_path)
            print(f"  Extracted text: {len(text)} chars")
            print(f"  Preview: {text[:300]}")

            # Save raw text
            txt_path = PDF_DIR / f"report_{pid}.txt"
            txt_path.write_text(text, encoding="utf-8")

            # Parse regulations
            regs = parse_regulations(text, pid)
            # Remove raw_text from JSON (it's in the .txt file)
            raw = regs.pop("raw_text", "")
            all_results.append(regs)

            print(f"\n  Parsed:")
            print(f"    Building code: {regs.get('building_code')}")
            print(f"    Allowed uses: {regs.get('allowed_uses')}")
            print(f"    Max floors: {regs.get('max_floors')}")
            print(f"    Floors desc: {regs.get('floors_description')}")
            print(f"    FAR: {regs.get('far')}")
            print(f"    Coverage: {regs.get('coverage_ratio')}")
            print(f"    Setbacks: {regs.get('setbacks')}")
            print(f"    Parking: {regs.get('parking')}")
            print(f"    Notes: {len(regs.get('notes', []))} items")

        await browser.close()

    # Save final JSON
    OUT.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {OUT}")

    # Print comparison table
    print(f"\n{'='*80}")
    print("COMPARISON TABLE")
    print(f"{'='*80}")
    header = f"{'Field':<25} ", 
    for r in all_results:
        pid = r.get("parcel_id", "?")
        header += (f"| {str(pid):<20} ",)
    print("".join(header))
    print("-" * 80)

    fields = [
        ("building_code", "Building Code"),
        ("allowed_uses", "Allowed Uses"),
        ("max_floors", "Max Floors"),
        ("far", "FAR"),
        ("coverage_ratio", "Coverage Ratio"),
        ("setbacks", "Setbacks"),
        ("parking", "Parking"),
    ]
    for key, label in fields:
        row = f"{label:<25} "
        for r in all_results:
            val = r.get(key, "N/A")
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            elif isinstance(val, dict):
                val = str(val.get("meter_values", val.get("raw", "N/A")))
            row += f"| {str(val)[:20]:<20} "
        print(row)


asyncio.run(main())
