"""Search the main JS bundle for the GetVIEW_BUILDINGSYSTEM function body
and any URL it calls to fetch regulation data."""

from pathlib import Path

BUNDLE = Path("api_exploration/js_bundles/main.c06e94eb2afc49cb.js")
OUT = Path("api_exploration/GetVIEW_BUILDINGSYSTEM_definition.txt")

content = BUNDLE.read_text(encoding="utf-8")

# Find the function definition
targets = [
    "GetVIEW_BUILDINGSYSTEM",
    "GetVIEW_BUILDINGSYSTEMShow",
    "GetTBL_LKP_BLDCODE",
    "GetFLGBLOCKED",
    "VIEW_BUILDINGSYSTEM",
    "urlAPI",
    "SaveBuildingUseCodeAll",
]

with OUT.open("w", encoding="utf-8") as f:
    for target in targets:
        # Find key:\"functionName\" or functionName: patterns
        # In minified Angular, functions are defined as object methods
        # like: key:"GetVIEW_BUILDINGSYSTEM",value:function(...)
        pattern = f'key:"{target}"'
        idx = content.find(pattern)
        if idx == -1:
            pattern = f"key:'{target}'"
            idx = content.find(pattern)
        if idx == -1:
            # Try direct function definition
            pattern = f"{target}=function"
            idx = content.find(pattern)
        if idx == -1:
            pattern = f"{target}:function"
            idx = content.find(pattern)

        if idx != -1:
            start = max(0, idx - 50)
            end = min(len(content), idx + 800)
            snippet = content[start:end]
            f.write(f"\n{'='*70}\n")
            f.write(f"FOUND: '{target}' at position {idx}\n")
            f.write(f"Pattern: {pattern}\n")
            f.write(f"{'='*70}\n")
            f.write(snippet)
            f.write("\n")
            print(f"FOUND: {target} at pos {idx}")
        else:
            print(f"NOT FOUND as method: {target}")
            # Still search for any occurrence with context
            idx = content.find(target)
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(content), idx + 500)
                snippet = content[start:end]
                f.write(f"\n{'='*70}\n")
                f.write(f"REFERENCE: '{target}' at position {idx}\n")
                f.write(f"{'='*70}\n")
                f.write(snippet)
                f.write("\n")

print(f"\nWritten to {OUT}")
