import json
import os

from .fetch import load_states

cat = "sldl"


result = {
    "type": "FeatureCollection",
    "name": f"merged_{cat}",
    "crs": {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
    },
    "features": [],
}


for fips, _, _ in load_states():
    if cat == "sldl" and fips == "31":
        fname = "out/sldu/31.geojson"
    else:
        fname = f"out/{cat}/{fips}.geojson"

    if not os.path.exists(fname):
        continue

    print(f"processing {fips}")
    with open(fname) as f:
        result["features"].extend(json.load(f)["features"])

print("writing merged...")
with open(f"out/{cat}/merged.geojson", "w") as f:
    json.dump(result, f)
