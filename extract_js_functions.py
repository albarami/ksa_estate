"""Extract key function definitions from the Angular main bundle."""

import sys
from pathlib import Path

BUNDLE = Path("api_exploration/js_bundles/main.c06e94eb2afc49cb.js")
OUT = Path("api_exploration/key_functions.txt")

KEYWORDS = [
    "GetVIEW_BUILDINGSYSTEM",
    "TBL_LKP_BLDCODE",
    "VIEW_BUILDINGSYSTEM",
    "api/Public/",
    "APIGEOPORTALN",
    "searchNew3",
    "GET_MAH_LAYERS",
    "parcelDetail",
    "FLGBLDCODE",
    "buildingCode",
]

content = BUNDLE.read_text(encoding="utf-8")

with OUT.open("w", encoding="utf-8") as f:
    for kw in KEYWORDS:
        positions = []
        idx = 0
        while True:
            idx = content.find(kw, idx)
            if idx == -1:
                break
            positions.append(idx)
            idx += len(kw)

        sep = "=" * 60
        f.write(f"\n{sep}\n")
        f.write(f"Keyword: {kw} ({len(positions)} occurrences)\n")
        f.write(f"{sep}\n")

        for pos in positions[:10]:
            start = max(0, pos - 150)
            end = min(len(content), pos + 350)
            snippet = content[start:end]
            f.write(f"\n--- pos {pos} ---\n")
            f.write(snippet)
            f.write("\n")

print(f"Done. Written to {OUT}")
for kw in KEYWORDS:
    count = content.count(kw)
    print(f"  {kw}: {count} occurrences")
