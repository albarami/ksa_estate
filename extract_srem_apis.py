"""Extract key SREM API responses from captured traffic."""

import json
from pathlib import Path

data = json.loads(Path("srem_exploration/srem_public_api.json").read_text(encoding="utf-8"))
out = Path("srem_exploration/key_api_responses.json")

apis: dict = {}
for req in data["requests"]:
    url = req.get("url", "")
    body = req.get("response_body")
    if not body or not req.get("interesting"):
        continue
    if "prod-srem-api" in url or "prod-inquiryservice" in url:
        key = url.split("?")[0].split("/")[-1]
        if key not in apis:
            apis[key] = {
                "url": url[:300],
                "method": req.get("method"),
                "post_data": req.get("post_data"),
                "status": req.get("status"),
                "phase": req.get("phase"),
                "response_preview": body[:5000],
            }

out.write_text(json.dumps(apis, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Extracted {len(apis)} unique API responses:")
for k, v in apis.items():
    method = v["method"]
    url_short = v["url"][:100]
    resp_len = len(v["response_preview"])
    print(f"  {k}: {method} {url_short} ({resp_len} chars)")
