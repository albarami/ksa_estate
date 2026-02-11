"""Scan the Al-Hada area for all nearby parcels."""
import httpx
import json

PROXY = "https://mapservice.alriyadh.gov.sa/APIGEOPORTALN/Handler/proxy.ashx"
SERVER = "https://maps.alriyadh.gov.sa/gprtl/rest/services/WebMercator/WMParcelsLayerOne/MapServer"
H = {"Referer": "https://mapservice.alriyadh.gov.sa/geoportal/geomap"}

points = [
    ("Park link (24.6478, 46.6575)", 24.647775, 46.657480),
    ("Al-Hada main (24.6488, 46.6588)", 24.648843, 46.658778),
    ("North of main", 24.6500, 46.6588),
    ("East of main", 24.6488, 46.6610),
    ("South of park", 24.6465, 46.6575),
    ("West of park", 24.6478, 46.6560),
]

for label, lat, lng in points:
    url = (
        f"{PROXY}?{SERVER}/identify"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&sr=4326&tolerance=3"
        f"&mapExtent={lng-0.001},{lat-0.001},{lng+0.001},{lat+0.001}"
        f"&imageDisplay=1440,900,96&layers=all:2"
        f"&returnGeometry=false&f=json"
    )
    r = httpx.get(url, headers=H, timeout=15, verify=False)
    data = r.json()
    results = data.get("results", [])
    if results:
        a = results[0].get("attributes", {})
        fields = {
            "ParcelID": a.get("PARCELID") or a.get("\u0631\u0645\u0632 \u0642\u0637\u0639\u0629 \u0627\u0644\u0623\u0631\u0636"),
            "PlotNo": a.get("PARCELNO") or a.get("\u0631\u0642\u0645 \u0627\u0644\u0642\u0637\u0639\u0629"),
            "Plan": a.get("PLANNO") or a.get("\u0631\u0642\u0645 \u0627\u0644\u0645\u062e\u0637\u0637"),
            "Area": a.get("SHAPE.AREA") or a.get("\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u0642\u0637\u0639\u0629"),
            "Code": a.get("FLGBLDCODE") or a.get("\u0646\u0638\u0627\u0645 \u0627\u0644\u0628\u0646\u0627\u0621"),
            "Use": a.get("\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0627\u0631\u0636"),
            "PrimaryUse": a.get("\u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0631\u0626\u064a\u0633\u064a"),
        }
        print(f"{label}:")
        for k, v in fields.items():
            print(f"  {k}: {v}")
    else:
        print(f"{label}: No parcel found")
    print()
