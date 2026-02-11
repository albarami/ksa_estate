"""Search captured traffic for ArcGIS tokens and layer config details."""

import json
import re
from pathlib import Path

CAPTURED = Path("geoportal_captured.json")
OUT = Path("arcgis_token_investigation.json")

data = json.loads(CAPTURED.read_text(encoding="utf-8"))
requests = data["requests"]

findings: dict = {
    "token_in_urls": [],
    "token_in_response_headers": [],
    "token_in_response_bodies": [],
    "layers_config": None,
    "layers_config_token_fields": [],
    "proxy_urls_with_token": [],
    "authenticate_response": None,
    "all_unique_api_urls": [],
}

seen_urls: set[str] = set()

for req in requests:
    url = req.get("url", "")
    body = req.get("response_body", "") or ""
    resp_headers = req.get("response_headers", {})
    req_headers = req.get("request_headers", {})

    # Collect unique API-related URLs (not tiles)
    if "/api/" in url.lower() or "query" in url.lower() or "identify" in url.lower():
        path = url.split("?")[0]
        if path not in seen_urls:
            seen_urls.add(path)
            findings["all_unique_api_urls"].append(path)

    # Check URLs for token= parameter
    url_lower = url.lower()
    if "token=" in url_lower or "token%3d" in url_lower:
        findings["token_in_urls"].append({
            "url": url[:500],
            "phase": req.get("phase"),
        })

    # Check response headers for token-related headers
    for hdr_name, hdr_val in resp_headers.items():
        if "token" in hdr_name.lower() and len(hdr_val) > 10:
            findings["token_in_response_headers"].append({
                "url": url[:200],
                "header": hdr_name,
                "value": hdr_val[:500],
            })

    # Check GET_MAH_LAYERS response
    if "GET_MAH_LAYERS" in url:
        findings["layers_config"] = {
            "url": url,
            "status": req.get("status"),
            "body_length": len(body),
            "body_preview": body[:8000],
        }
        # Search for token-like fields in the JSON
        if body:
            try:
                layers_data = json.loads(body)
                if isinstance(layers_data, list):
                    for item in layers_data:
                        if isinstance(item, dict):
                            for key, val in item.items():
                                key_l = key.lower()
                                if any(t in key_l for t in ("token", "key", "secret", "credential")):
                                    findings["layers_config_token_fields"].append({
                                        "field": key,
                                        "value": str(val)[:500],
                                        "layer_url": item.get("URL", ""),
                                        "layer_name": item.get("LAYERNAME", ""),
                                    })
            except json.JSONDecodeError:
                pass

    # Check authenticate response
    if "authenticate" in url.lower() and body:
        findings["authenticate_response"] = {
            "url": url,
            "body": body[:2000],
            "request_headers_apikey": req_headers.get("apikey", ""),
        }

    # Check all response bodies for token patterns (skip large/binary)
    if body and isinstance(body, str) and 100 < len(body) < 100000:
        # Skip Google/Firebase
        if "google" in url.lower() or "firebase" in url.lower():
            continue

        lower_body = body.lower()
        if any(k in lower_body for k in ['"token"', "'token'", "token=", "arcgis"]):
            findings["token_in_response_bodies"].append({
                "url": url[:300],
                "phase": req.get("phase"),
                "body_length": len(body),
                "body_snippet": body[:3000],
            })

    # Check proxy URLs
    if "proxy.ashx" in url:
        if "token" in url_lower:
            findings["proxy_urls_with_token"].append(url[:500])

# Summary
print(f"Token in URLs: {len(findings['token_in_urls'])}")
print(f"Token in response headers: {len(findings['token_in_response_headers'])}")
print(f"Token in response bodies: {len(findings['token_in_response_bodies'])}")
print(f"Layers config token fields: {len(findings['layers_config_token_fields'])}")
print(f"Proxy URLs with token: {len(findings['proxy_urls_with_token'])}")
print(f"Authenticate response found: {findings['authenticate_response'] is not None}")
print(f"Layers config found: {findings['layers_config'] is not None}")
if findings["layers_config"]:
    print(f"  Layers body length: {findings['layers_config']['body_length']}")

OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nSaved to {OUT}")
