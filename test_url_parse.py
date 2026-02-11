"""Test URL parsing fix."""
from backend.geocode import parse_coordinates

# The problematic URL
url = "https://www.google.com/maps/place/24%C2%B038'55.8%22N+46%C2%B039'31.6%22E/@24.6504059,46.6590325,15.5z/data=!4m4!3m3!8m2!3d24.648843!4d46.658778"

coords = parse_coordinates(url)
print(f"Parsed: {coords}")
print(f"Expected: (24.648843, 46.658778)  <-- the actual pin")
print(f"Wrong:    (24.6504059, 46.6590325) <-- the viewport center")

if coords:
    lat, lng = coords
    if abs(lat - 24.648843) < 0.001 and abs(lng - 46.658778) < 0.001:
        print("CORRECT - pin location!")
    else:
        print("WRONG - got viewport center!")
