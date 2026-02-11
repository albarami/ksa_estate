"""Find the BuildingSystem URL context in the bundle and hit it."""

import json
from pathlib import Path

BUNDLE = Path("api_exploration/js_bundles/main.c06e94eb2afc49cb.js")
content = BUNDLE.read_text(encoding="utf-8")

target = "BuildingSystem/building-code-report"
idx = 0
count = 0
while True:
    idx = content.find(target, idx)
    if idx == -1:
        break
    start = max(0, idx - 400)
    end = min(len(content), idx + 400)
    snippet = content[start:end]
    print(f"\n{'='*60}")
    print(f"Match {count} at position {idx}")
    print(f"{'='*60}")
    print(snippet)
    count += 1
    idx += len(target)

# Also search for BuildingSystem/ generally
print(f"\n\n{'='*60}")
print("All BuildingSystem/ references:")
print(f"{'='*60}")
target2 = "BuildingSystem"
idx = 0
while True:
    idx = content.find(target2, idx)
    if idx == -1:
        break
    start = max(0, idx - 100)
    end = min(len(content), idx + 200)
    print(f"\n  pos {idx}: ...{content[start:end]}...")
    idx += len(target2)

# Also search for BuildingGuide
print(f"\n\n{'='*60}")
print("All BuildingGuide references:")
print(f"{'='*60}")
target3 = "BuildingGuide"
idx = 0
while True:
    idx = content.find(target3, idx)
    if idx == -1:
        break
    start = max(0, idx - 100)
    end = min(len(content), idx + 200)
    print(f"\n  pos {idx}: ...{content[start:end]}...")
    idx += len(target3)
