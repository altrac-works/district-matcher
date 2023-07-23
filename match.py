import csv
import functools
import json
import logging
import os
from typing import Iterable

import shapely

CACHE_SIZE = 512


class Shapefile:
    def __init__(self):
        self.features = []

    @classmethod
    @functools.lru_cache(CACHE_SIZE)
    def load(cls, filename):
        logging.info(f"Loading {filename}")

        obj = cls()

        with open(filename) as f:
            data = json.load(f)

        for feature in data["features"]:
            obj.features.append(
                {
                    "feature": shapely.from_geojson(json.dumps(feature)),
                    "props": feature["properties"],
                }
            )

        return obj

    def find_intersecting_feature(self, raw_point):
        if isinstance(raw_point, tuple):
            lon, lat = raw_point
            point = shapely.Point(lon, lat)
        else:
            point = raw_point

        for feature in self.features:
            if feature["feature"].intersection(point):
                return feature


class Matcher:
    def __init__(self):
        self.shapefiles = []
        for shapefile_name in self.default_shapefiles():
            self.shapefiles.append(Shapefile.load(shapefile_name))

        for shapefile_name in self.preloaded_shapefiles():
            Shapefile.load(shapefile_name)

    def default_shapefiles(self):
        return []

    def match_callback(self, feature, tier: int) -> Iterable[str]:
        return []

    def match_features(self, raw_point):
        result = []

        q = []

        lon, lat = raw_point
        point = shapely.Point(lon, lat)

        for shapefile in self.shapefiles:
            candidate = shapefile.find_intersecting_feature(point)

            if candidate:
                q.append((0, candidate))

        while q:
            tier, feature = q.pop(0)
            result.append(feature)

            for shapefile_name in self.match_callback(feature, tier):
                if not os.path.exists(shapefile_name):
                    continue

                candidate = Shapefile.load(shapefile_name).find_intersecting_feature(
                    point
                )

                if candidate:
                    q.append((tier + 1, candidate))

        return result


class USDistrictsMatcher(Matcher):
    def default_shapefiles(self):
        return ["out/states/states.geojson"]

    def preloaded_shapefiles(self):
        with open("data/fips.csv") as f:
            fips = [i[0] for i in csv.reader(f)]

        result = []

        for code in fips:
            for fname in [
                f"out/congress/{code}.geojson",
                f"out/sldl/{code}.geojson",
                f"out/sldu/{code}.geojson",
            ]:
                if not os.path.exists(fname):
                    continue

                result.append(fname)

        return result

    def match_callback(self, feature, tier):
        if tier > 0:
            return []

        state_fips = feature["props"]["STATEFP"]
        return [
            f"out/congress/{state_fips}.geojson",
            f"out/sldl/{state_fips}.geojson",
            f"out/sldu/{state_fips}.geojson",
        ]
