import time

from flask import Flask, jsonify, render_template, request

from .match import USDistrictsMatcher

app = Flask("district_matcher.app")
matcher = USDistrictsMatcher()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/v1/match.json")
def match():
    begin = time.time()

    lat = request.args.get("lat")
    lon = request.args.get("lon")

    try:
        lat = float(lat)
        lon = float(lon)
    except TypeError:
        return "lat and lon required", 400
    except ValueError:
        return "lat and lon must be numbers", 400

    features = matcher.match_features([lon, lat])
    ocdids = [feat["props"]["OCDID"] for feat in features]
    end = time.time()

    return jsonify(
        ocdids=ocdids, perf={"match_time_ms": round((end - begin) * 1000, 3)}
    )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
