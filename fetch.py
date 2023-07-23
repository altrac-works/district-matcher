import csv
import functools
import json
import logging
import os
import shutil
import subprocess
import sys
import zipfile

import requests

BASE_URL = "https://www2.census.gov/geo/tiger/TIGER_RD18/LAYER"
DATASET = "rd22"
CONGRESS = "118"


@functools.cache
def http_session():
    return requests.Session()


def download_file(url, name):
    dest_base = f"out/{name}"
    dest = f"{dest_base}.zip"

    if not os.path.exists(dest):
        if directory := os.path.dirname(dest):
            os.makedirs(directory, exist_ok=True)

        logging.info(f"Downloading {url} to {dest}")
        with http_session().get(f"{BASE_URL}/{url}", stream=True) as resp:
            resp.raw.read = functools.partial(resp.raw.read, decode_content=True)
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp.raw, f)

    else:
        logging.info(f"Skipping downloading {name}")

    if not os.path.exists(f"{dest_base}.geojson"):
        cleanup = []
        try:
            with zipfile.ZipFile(dest, "r") as z:
                for name in z.namelist():
                    if name.endswith(".xml"):
                        continue

                    ext = name.split(".")[-1]
                    cleanup.append(f"{dest_base}.{ext}")
                    with z.open(name, "r") as inp:
                        with open(f"{dest_base}.{ext}", "wb") as out:
                            shutil.copyfileobj(inp, out)

                    logging.info(f"Extracted {name} to {dest_base}.{ext}")

            subprocess.check_output(
                [
                    "ogr2ogr",
                    "-f",
                    "GeoJSON",
                    "-s_srs",
                    f"{dest_base}.prj",
                    "-t_srs",
                    "EPSG:4326",
                    f"{dest_base}.geojson",
                    f"{dest_base}.shp",
                ]
            )
            logging.info(f"Created {dest_base}.geojson")

            for filename in cleanup:
                os.unlink(filename)

        except zipfile.BadZipFile:
            logging.warn(f"Skipping postprocessing for {dest}, it is not a zip file")

    else:
        logging.info(f"Skipping extracting {dest_base}")


@functools.cache
def load_states():
    with open("data/fips.csv") as f:
        return list(csv.reader(f))


def patch_ocdids(state_filter=None):
    def patch_file(filename, callback):
        filename = f"out/{filename}.geojson"
        if not os.path.exists(filename):
            return

        logging.info(f"Patching ocdids in {filename}...")

        with open(filename) as f:
            data = json.load(f)

        new_features = []
        for feature in data["features"]:
            if (ocdid := callback(feature["properties"])) is not None:
                feature["properties"]["OCDID"] = ocdid
                new_features.append(feature)

        data["features"] = new_features

        with open(filename, "w") as f:
            json.dump(data, f, separators=(",", ":"))

    def state_prefix(abbrev):
        return f"ocd-division/country:us/state:{abbrev}"

    def sldl_callback(abbrev, p):
        sldlst = p["SLDLST"].lower().lstrip("0")
        if sldlst.startswith("zz"):
            return

        prefix = state_prefix(abbrev)

        nametags = p["NAMELSAD"].split()
        if abbrev == "ma":
            assert nametags[-1] == "District"
            nametags = nametags[:-1]

            if nametags[0] == "Barnstable-Dukes-Nantucket":
                # why are you like this, Massachusetts
                return f"{prefix}/sldl:barnstable_dukes_and_nantucket"

            return f"{prefix}/sldl:{nametags[0]}_{nametags[1]}".lower()

        elif abbrev == "vt":
            name = "_".join(nametags[:-3]).lower()
            return f"{prefix}/sldl:{name}"

        elif abbrev == "nh":
            names = nametags[3:]  # "State House District"
            return f"{prefix}/sldl:{names[0].lower()}_{names[1].lstrip('0')}"

        return f"{prefix}/sldl:{sldlst}"

    def sldu_callback(abbrev, p):
        sldust = p["SLDUST"].lower().lstrip("0")
        if "zz" in sldust:
            return

        prefix = state_prefix(abbrev)
        nametags = p["NAMELSAD"].split()

        if abbrev == "dc":
            return f"ocd-division/country:us/district:dc/ward:{sldust}"

        elif abbrev == "vt":
            names = nametags[:-2]  # "Senate District"

            # FIXME: redistricting will absolutely break this
            fixed = {
                "chs": "chittenden-southeast",
                "chc": "chittenden-central",
                "chn": "chittenden-north",
            }
            if sldust in fixed:
                district = fixed[sldust]
            else:
                district = "_".join(names).lower()

            return f"{prefix}/sldu:{district}"

        elif abbrev == "ma":
            # PLEASE stop
            ordinals = {
                "First": "1st",
                "Second": "2nd",
                "Third": "3rd",
                "Fourth": "4th",
                "Fifth": "5th",
            }

            names = nametags[:-1]  # "District"

            ord_prefix = None
            if names[0] in ordinals:
                ord_prefix = ordinals[names[0]]
                names = names[1:]

            result = []
            if ord_prefix:
                result.append(ord_prefix)

            names = [i.lower() for i in names]
            if "-" in names[0]:
                dashed = names[0].split("-")
                result.append("_".join(dashed[:-1]) + "_and_" + dashed[-1])
            else:
                result.append("_".join(n.lower() for n in names))

            district = "_".join(result)

            return f"{prefix}/sldu:{district}"

        return f"{prefix}/sldu:{sldust}"

    def congress_callback(abbrev, props):
        if abbrev == "dc":
            # DC "does not have" congressional representation
            return

        prefix = state_prefix(abbrev)
        district = props["CD" + CONGRESS + "FP"]

        if district.lower().startswith("zz"):
            return

        if district == "00":
            return f"{prefix}/cd:at-large"

        return f"{prefix}/cd:{district.lstrip('0').lower()}"

    patch_file(
        "states/states",
        lambda p: f"ocd-division/country:us/state:{p['STUSPS'].lower()}",
    )

    for fips, name, abbrev in load_states():
        if state_filter is not None and state_filter != name:
            continue

        abbrev = abbrev.lower()

        patch_file(f"sldl/{fips}", functools.partial(sldl_callback, abbrev))
        patch_file(f"sldu/{fips}", functools.partial(sldu_callback, abbrev))
        patch_file(f"congress/{fips}", functools.partial(congress_callback, abbrev))


def main():
    logging.basicConfig(level=logging.DEBUG)

    download_file(f"STATE/tl_{DATASET}_us_state.zip", "states/states")

    state_filter = None
    if len(sys.argv) > 1:
        state_filter = sys.argv[1]

    for fips, name, _ in load_states():
        if state_filter is not None and state_filter != name:
            continue

        download_file(f"SLDL/tl_{DATASET}_{fips}_sldl.zip", f"sldl/{fips}")
        download_file(f"SLDU/tl_{DATASET}_{fips}_sldu.zip", f"sldu/{fips}")
        download_file(f"CD/tl_{DATASET}_{fips}_cd{CONGRESS}.zip", f"congress/{fips}")

    patch_ocdids(state_filter)


if __name__ == "__main__":
    main()
