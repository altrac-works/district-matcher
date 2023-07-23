import logging
import multiprocessing
import os
import random
import time

from .match import USDistrictsMatcher


def gen_point():
    lon = random.uniform(-124.77, -66.95)
    lat = random.uniform(24.52, 49.38)

    return lon, lat


logging.basicConfig(level=logging.DEBUG)
m = USDistrictsMatcher()

cpus = os.cpu_count() - 1
print(f"Using {cpus} processes")

pool = multiprocessing.Pool(cpus)
batch = 10000

count = 0
while True:
    points = [gen_point() for _ in range(10000)]

    start = time.time()
    pool.map(m.match_features, points)
    total = time.time() - start
    print(f"{batch} points matched in {total:.2f}s ({batch / total:.1f}pps)")
