import requests
import time

# ===== CONFIG =====

TOMTOM_API_KEY = "mPtfLSFK8MXJHzOuvE6CJJKYn56Hcw2v"

# Andheri bbox (n, s, w, e)
NORTH = 19.1341
SOUTH = 19.1017
WEST = 72.8248
EAST = 72.8685

# Grid resolution (inclusive)
LAT_STEPS = 3   # e.g., 3x3 grid
LON_STEPS = 3

FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def fetch_flow_for_point(lat, lon):
    params = {
        "key": TOMTOM_API_KEY,
        "point": f"{lat},{lon}",
        "unit": "KMPH"
    }
    resp = requests.get(FLOW_URL, params=params, timeout=3.0)
    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    fs = data.get("flowSegmentData")
    if not fs:
        return None

    return {
        "currentSpeed": fs.get("currentSpeed"),
        "freeFlowSpeed": fs.get("freeFlowSpeed"),
        "currentTravelTime": fs.get("currentTravelTime"),
        "freeFlowTravelTime": fs.get("freeFlowTravelTime"),
        "confidence": fs.get("confidence"),
        "roadClosure": fs.get("roadClosure")
    }


def generate_grid_points():
    lat_step = (NORTH - SOUTH) / (LAT_STEPS - 1) if LAT_STEPS > 1 else 0
    lon_step = (EAST - WEST) / (LON_STEPS - 1) if LON_STEPS > 1 else 0

    points = []
    for i in range(LAT_STEPS):
        lat = SOUTH + i * lat_step
        for j in range(LON_STEPS):
            lon = WEST + j * lon_step
            points.append((lat, lon))
    return points


if __name__ == "__main__":
    print("=== TomTom Flow Segment Data Grid Test ===")
    points = generate_grid_points()
    print(f"Sampling {len(points)} points in bbox:")
    print(f"  NORTH={NORTH}, SOUTH={SOUTH}, WEST={WEST}, EAST={EAST}")
    print()

    for idx, (lat, lon) in enumerate(points, start=1):
        print(f"[{idx}/{len(points)}] Point lat={lat:.6f}, lon={lon:.6f}")
        result = fetch_flow_for_point(lat, lon)
        if not result:
            print("  ❌ No flowSegmentData or error")
        else:
            cs = result["currentSpeed"]
            ffs = result["freeFlowSpeed"]
            conf = result["confidence"]
            rc = result["roadClosure"]
            print(f"  currentSpeed / freeFlowSpeed : {cs} / {ffs} km/h")
            print(f"  confidence                   : {conf}")
            print(f"  roadClosure                  : {rc}")
        print()
        # Optional small delay to be nice to the API
        time.sleep(0.3)
