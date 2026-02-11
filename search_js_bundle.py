"""Deep search the Angular main bundle for embedded regulation data."""

import json
import re
from pathlib import Path

BUNDLE = Path("api_exploration/js_bundles/main.c06e94eb2afc49cb.js")
OUT = Path("js_bundle_regulation_search.json")

content = BUNDLE.read_text(encoding="utf-8")
print(f"Bundle size: {len(content):,} chars")

findings: dict = {
    "bundle_size": len(content),
    "exact_code_matches": [],
    "view_buildingsystem_fields": [],
    "embedded_objects": [],
    "numeric_patterns": [],
}


# ---------------------------------------------------------------------------
# 1. Search for exact building code strings
# ---------------------------------------------------------------------------
code_patterns = [
    "م 111", "م111", "م 112", "م 113",
    "س 111", "س111", "س 112", "س 113",
    "م 211", "م 212", "م 311",
    "س 211", "س 212", "س 311",
]

print("\n=== Exact code string matches ===")
for pat in code_patterns:
    idx = 0
    while True:
        idx = content.find(pat, idx)
        if idx == -1:
            break
        start = max(0, idx - 250)
        end = min(len(content), idx + 250)
        snippet = content[start:end]
        findings["exact_code_matches"].append({
            "pattern": pat,
            "position": idx,
            "snippet": snippet,
        })
        print(f"  FOUND '{pat}' at {idx}")
        idx += len(pat)

if not findings["exact_code_matches"]:
    print("  None found")


# ---------------------------------------------------------------------------
# 2. Search for VIEW_BUILDINGSYSTEM field names
# ---------------------------------------------------------------------------
field_names = [
    "CONSTRUCTIONFACTOR", "CONSTRUCTIONRATIO",
    "BOUNCES", "ALTITUDES", "PARKING",
    "PLANNINGREQUIREMENTS", "USES", "NOTES",
]

print("\n=== VIEW_BUILDINGSYSTEM field names ===")
for field in field_names:
    positions = []
    idx = 0
    while True:
        idx = content.find(field, idx)
        if idx == -1:
            break
        positions.append(idx)
        idx += len(field)

    print(f"  {field}: {len(positions)} occurrences")
    # Save first 3 with context
    for pos in positions[:3]:
        start = max(0, pos - 200)
        end = min(len(content), pos + 300)
        findings["view_buildingsystem_fields"].append({
            "field": field,
            "position": pos,
            "snippet": content[start:end],
        })


# ---------------------------------------------------------------------------
# 3. Search for embedded lookup objects/arrays near building keywords
# ---------------------------------------------------------------------------
print("\n=== Searching for embedded objects near building keywords ===")

# Look for patterns like {ID:8,FLGBLDCODE:"م 111",...} or arrays of such
obj_patterns = [
    # JSON-like objects with ID and code
    r'\{[^{}]{0,100}(?:ID|id)["\s:]+\d+[^{}]{0,100}(?:FLGBLDCODE|bldcode|code)[^{}]{0,200}\}',
    # Arrays of objects with building-related keys
    r'\[[^[\]]{0,50}\{[^{}]{0,100}(?:FLGBLDCODE|BUILDINGUSECODE|bldCode)[^{}]{0,200}\}',
    # Lookup-style: number key to string value with م or س
    r'(?:\d+\s*:\s*["\'][مس][^"\']{1,30}["\'])',
]

for i, pat in enumerate(obj_patterns):
    matches = re.findall(pat, content)
    print(f"  Pattern {i}: {len(matches)} matches")
    for m in matches[:5]:
        findings["embedded_objects"].append({
            "pattern_idx": i,
            "match": m[:500],
        })
        print(f"    {m[:200]}")


# ---------------------------------------------------------------------------
# 4. Search for numeric regulation-like patterns near keywords
# ---------------------------------------------------------------------------
print("\n=== Numeric patterns near building keywords ===")

# Find sections of code near BUILDINGUSECODE, bldcode, etc.
anchor_keywords = [
    "BUILDINGUSECODE", "TBL_LKP_BLDCODE", "GetVIEW_BUILDINGSYSTEM",
    "bldcode", "buildingCode", "BuildingUseCode",
]

for kw in anchor_keywords:
    idx = 0
    count = 0
    while count < 5:
        idx = content.find(kw, idx)
        if idx == -1:
            break
        # Look in a 1000-char window around the keyword
        start = max(0, idx - 500)
        end = min(len(content), idx + 500)
        window = content[start:end]

        # Search for number sequences that look like regulation values
        # e.g., arrays of numbers, or key:value with small numbers
        nums = re.findall(r'(?:floors?|ادوار|setback|ارتداد|FAR|نسبة)\s*[:\s=]+\s*(\d+\.?\d*)', window, re.IGNORECASE)
        if nums:
            findings["numeric_patterns"].append({
                "keyword": kw,
                "position": idx,
                "numbers_found": nums,
                "window": window,
            })
            print(f"  Near '{kw}' at {idx}: numbers={nums}")

        idx += len(kw)
        count += 1


# ---------------------------------------------------------------------------
# 5. Search for any large data arrays that could be lookup tables
# ---------------------------------------------------------------------------
print("\n=== Searching for large data arrays ===")

# Find arrays with 10+ objects containing numeric IDs
# Pattern: [{...ID:1...},{...ID:2...},...]
large_array_pattern = r'\[\s*\{[^[\]]{10,500}(?:ID|Id|id)\s*[:\s]+\d+[^[\]]{10,500}\}\s*(?:,\s*\{[^[\]]{10,500}\}){5,}'
large_matches = re.findall(large_array_pattern, content)
print(f"  Large arrays with ID fields: {len(large_matches)}")
for m in large_matches[:3]:
    # Check if it has building-related content
    m_lower = m.lower()
    if any(kw in m_lower for kw in ["bld", "building", "code", "floor", "setback", "نظام"]):
        findings["embedded_objects"].append({
            "type": "large_array",
            "match": m[:2000],
        })
        print(f"    Building-related array ({len(m)} chars): {m[:300]}")


# ---------------------------------------------------------------------------
# 6. Search for any URL containing regulation/building endpoints we missed
# ---------------------------------------------------------------------------
print("\n=== URL patterns with building/regulation ===")
url_pattern = r'["\'](?:https?://[^"\']*|/[^"\']*)?(?:building|regulation|bldcode|getview|condition|floor|setback|bounces|altitudes)[^"\']*["\']'
url_matches = re.findall(url_pattern, content, re.IGNORECASE)
unique_urls = sorted(set(m.strip("\"'") for m in url_matches))
print(f"  Found {len(unique_urls)} unique URL-like strings")
for u in unique_urls:
    print(f"    {u[:200]}")
    findings["embedded_objects"].append({"type": "url_pattern", "match": u[:500]})


# ---------------------------------------------------------------------------
# 7. One more: search for Arabic regulation terms in string literals
# ---------------------------------------------------------------------------
print("\n=== Arabic regulation strings ===")
arabic_patterns = [
    (r'"[^"]*عدد الأدوار[^"]*"', "floors"),
    (r'"[^"]*نسبة البناء[^"]*"', "FAR"),
    (r'"[^"]*الارتداد[^"]*"', "setback"),
    (r'"[^"]*ارتداد[^"]*"', "setback2"),
    (r'"[^"]*معامل البناء[^"]*"', "construction_factor"),
    (r'"[^"]*مواقف[^"]*"', "parking"),
    (r'"[^"]*ارتفاع[^"]*"', "height"),
    (r'"[^"]*تغطية[^"]*"', "coverage"),
]

for pat, label in arabic_patterns:
    matches = re.findall(pat, content)
    unique = sorted(set(matches))
    if unique:
        print(f"  {label}: {len(unique)} unique strings")
        for m in unique[:5]:
            print(f"    {m[:150]}")
            findings["embedded_objects"].append({"type": f"arabic_{label}", "match": m[:300]})


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nSaved to {OUT}")
print(f"  Exact code matches: {len(findings['exact_code_matches'])}")
print(f"  Field name snippets: {len(findings['view_buildingsystem_fields'])}")
print(f"  Embedded objects: {len(findings['embedded_objects'])}")
print(f"  Numeric patterns: {len(findings['numeric_patterns'])}")
