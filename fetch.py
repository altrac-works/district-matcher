import csv
import functools
import json
import logging
import os
import shutil
import subprocess
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


def patch_ocdids():
    def patch_file(filename, callback):
        filename = f"out/{filename}.geojson"
        if not os.path.exists(filename):
            return

        logging.info(f"Patching ocdids in {filename}...")

        with open(filename) as f:
            data = json.load(f)

        for feature in data["features"]:
            feature["properties"]["OCDID"] = callback(feature["properties"])

        with open(filename, "w") as f:
            json.dump(data, f, separators=(",", ":"))

    def congress_callback(prefix, props):
        district = props["CD" + CONGRESS + "FP"]
        if district == "00":
            return f"{prefix}/cd:at-large"

        return f"{prefix}/cd:{district.lstrip('0')}"

    patch_file(
        "states/states",
        lambda p: f"ocd-division/country:us/state:{p['STUSPS'].lower()}",
    )

    for fips, _, abbrev in load_states():
        abbrev = abbrev.lower()
        prefix = f"ocd-division/country:us/state:{abbrev}"

        patch_file(f"sldl/{fips}", lambda p: f"{prefix}/sldl:{p['SLDLST'].lstrip('0')}")
        patch_file(
            f"sldu/{fips}", lambda p: f"{prefix}/sldl:{p['SLDUST'].lower().lstrip('0')}"
        )
        patch_file(f"congress/{fips}", functools.partial(congress_callback, prefix))


def main():
    logging.basicConfig(level=logging.DEBUG)

    download_file(f"STATE/tl_{DATASET}_us_state.zip", "states/states")

    for fips, name, _ in load_states():
        download_file(f"SLDL/tl_{DATASET}_{fips}_sldl.zip", f"sldl/{fips}")
        download_file(f"SLDU/tl_{DATASET}_{fips}_sldu.zip", f"sldu/{fips}")
        download_file(f"CD/tl_{DATASET}_{fips}_cd{CONGRESS}.zip", f"congress/{fips}")

    patch_ocdids()


if __name__ == "__main__":
    main()
