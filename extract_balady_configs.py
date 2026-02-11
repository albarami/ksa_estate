"""Extract key config responses from Balady UMaps captured requests."""

import json
from pathlib import Path

data = json.loads(Path("balady_umaps_exploration/captured_requests.json").read_text(encoding="utf-8"))
out_path = Path("balady_umaps_exploration/key_configs.json")

configs: dict = {}
targets = [
    "service-Config", "popup-config", "identify-feature",
    "toggleLayers", "field-config", "GenerateArcGISToken",
    "CreateToken", "GetAPIs", "Lucene", "autocomplete-search",
    "side-bar", "indoorFloor", "criticalSites",
]

for req in data["requests"]:
    url = req.get("url", "")
    body = req.get("response_body")
    if not body:
        continue
    for t in targets:
        if t in url:
            key = t
            if key not in configs:
                configs[key] = {"url": url[:300], "body": body}

out_path.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Extracted {len(configs)} config responses")
for k, v in configs.items():
    body_len = len(v["body"])
    print(f"  {k}: {body_len} chars")
