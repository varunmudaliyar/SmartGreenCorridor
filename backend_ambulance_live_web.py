#!/usr/bin/env python3

"""
TomTom-driven normal traffic backend for your existing frontend.

- POST /api/simulation/start : starts SUMO + TomTom-based normal traffic.
- POST /api/simulation/stop  : stops it.
- GET  /api/simulation/status: simple running/vehicle count.
- Socket.IO 'simulation_update' event:
  {
    sim_time,
    step,
    vehicle_count,
    vehicles: [
      { id, lat, lon, speed, angle, is_ambulance, color: {r,g,b} }
    ],
    traffic_lights: {},         # empty (no signals for now)
    ambulances: [],             # empty
    active_green_corridors: 0,
    tomtom_avg_speed,
    tomtom_freeflow,
    tomtom_speed_factor,
    tomtom_density_level
  }

Your React app should already understand this structure and display vehicles.
"""

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

import traci
import threading
import time
import os
import random
import requests

# ============================================================================
# CONFIG
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tomtom-only-2025'

CORS(app, resources={r"/*": {"origins": ["http://localhost:3000"]}})
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3000"],
    async_mode='threading',
    ping_timeout=120,
    ping_interval=25
)

DATA_DIR = 'sumo_data'
SUMO_CONFIG = os.path.join(DATA_DIR, 'simulation.sumocfg')
SUMO_BINARY = 'sumo'

# TomTom config – insert your key
TOMTOM_API_KEY = "YOUR_TOMTOM_API_KEY_HERE"
TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Andheri bbox (n, s, w, e)
ANDHERI_BBOX = {
    "north": 19.1341,
    "south": 19.1017,
    "west": 72.8248,
    "east": 72.8685,
}

# TomTom sampling grid
LAT_STEPS = 3
LON_STEPS = 3

# Simulation
SIM_STEP_LENGTH = 1.0     # seconds
MAX_SIM_SECONDS = 3600.0  # 1 hour max

# Normal traffic behaviour
simulation_running = False
simulation_thread = None
normal_vehicle_counter = 0

print("=" * 80)
print("TOMTOM-ONLY NORMAL TRAFFIC BACKEND")
print("=" * 80)

# ============================================================================
# TOMTOM HELPERS
# ============================================================================

def tomtom_flow_for_point(lat, lon):
    """Fetch TomTom Flow Segment Data for a single point."""
    if not TOMTOM_API_KEY:
        return None

    params = {
        "key": TOMTOM_API_KEY,
        "point": f"{lat},{lon}",
        "unit": "KMPH"
    }
    try:
        resp = requests.get(TOMTOM_FLOW_URL, params=params, timeout=2.0)
        if resp.status_code != 200:
            print("⚠️ TomTom error:", resp.status_code, resp.text[:200])
            return None
        fs = resp.json().get("flowSegmentData", {})
        cs = fs.get("currentSpeed")
        ffs = fs.get("freeFlowSpeed")
        if cs is None or ffs is None or ffs <= 0:
            return None
        return {
            "currentSpeed": float(cs),
            "freeFlowSpeed": float(ffs)
        }
    except Exception as e:
        print("⚠️ TomTom exception:", e)
        return None


def build_tomtom_summary():
    """Sample small grid in bbox → avg speed + factor + density."""
    north = ANDHERI_BBOX["north"]
    south = ANDHERI_BBOX["south"]
    west = ANDHERI_BBOX["west"]
    east = ANDHERI_BBOX["east"]

    lat_step = (north - south) / (LAT_STEPS - 1) if LAT_STEPS > 1 else 0
    lon_step = (east - west) / (LON_STEPS - 1) if LON_STEPS > 1 else 0

    samples = []
    for i in range(LAT_STEPS):
        lat = south + i * lat_step
        for j in range(LON_STEPS):
            lon = west + j * lon_step
            data = tomtom_flow_for_point(lat, lon)
            if data:
                samples.append(data)

    if not samples:
        print("⚠️ No TomTom samples, using defaults")
        return {
            "avg_currentSpeed": 30.0,
            "avg_freeFlowSpeed": 40.0,
            "speed_factor": 0.75,
            "density_level": "medium"
        }

    avg_current = sum(s["currentSpeed"] for s in samples) / len(samples)
    avg_free = sum(s["freeFlowSpeed"] for s in samples) / len(samples)
    factor = avg_current / avg_free if avg_free > 0 else 0.75
    factor = max(0.3, min(1.5, factor))

    if avg_current >= 40:
        density = "low"
    elif avg_current >= 20:
        density = "medium"
    else:
        density = "high"

    print(f"✅ TomTom summary: avgCurrent={avg_current:.1f} km/h, "
          f"avgFreeFlow={avg_free:.1f} km/h, factor={factor:.2f}, density={density}")

    return {
        "avg_currentSpeed": avg_current,
        "avg_freeFlowSpeed": avg_free,
        "speed_factor": factor,
        "density_level": density
    }

# ============================================================================
# SUMO HELPERS
# ============================================================================

def point_in_bbox(lat, lon):
    return (ANDHERI_BBOX["south"] <= lat <= ANDHERI_BBOX["north"] and
            ANDHERI_BBOX["west"] <= lon <= ANDHERI_BBOX["east"])


def get_edges_in_bbox():
    """Return edges whose lane 0 midpoint is inside bbox."""
    edges = []
    try:
        for edge_id in traci.edge.getIDList():
            if edge_id.startswith(":"):
                continue
            lane_id = f"{edge_id}_0"
            try:
                shape = traci.lane.getShape(lane_id)
            except Exception:
                continue
            if not shape:
                continue
            mid = shape[len(shape) // 2]
            x, y = mid
            lon, lat = traci.simulation.convertGeo(x, y)
            if point_in_bbox(lat, lon):
                edges.append(edge_id)
    except Exception as e:
        print("⚠️ Error while collecting edges in bbox:", e)

    print(f"✅ Found {len(edges)} edges in bbox")
    return edges


def apply_speed_factor_to_bbox_lanes(speed_factor):
    """Scale lane speeds inside bbox by TomTom factor."""
    north = ANDHERI_BBOX["north"]
    south = ANDHERI_BBOX["south"]
    west = ANDHERI_BBOX["west"]
    east = ANDHERI_BBOX["east"]

    updated = 0
    for lane_id in traci.lane.getIDList():
        try:
            shape = traci.lane.getShape(lane_id)
            if not shape:
                continue
            mid = shape[len(shape) // 2]
            x, y = mid
            lon, lat = traci.simulation.convertGeo(x, y)
            if not (south <= lat <= north and west <= lon <= east):
                continue

            base_speed = traci.lane.getMaxSpeed(lane_id)
            new_speed = max(5.0 / 3.6, base_speed * speed_factor)
            traci.lane.setMaxSpeed(lane_id, new_speed)
            updated += 1
        except Exception:
            continue

    print(f"✅ Applied speed_factor={speed_factor:.2f} to {updated} lanes in bbox")


def compute_target_vehicle_count(density_level):
    """Map density level to target vehicle count."""
    if density_level == "low":
        return 50
    if density_level == "medium":
        return 150
    return 300  # high


def spawn_normal_vehicle(edge_id):
    """Spawn a normal vehicle on a single-edge route."""
    global normal_vehicle_counter

    veh_id = f"car_{normal_vehicle_counter}"
    normal_vehicle_counter += 1

    try:
        route_id = f"route_{veh_id}"
        traci.route.add(route_id, [edge_id])

        traci.vehicle.add(
            vehID=veh_id,
            routeID=route_id,
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        traci.vehicle.setColor(veh_id, (0, 0, 255, 255))  # blue cars
        return True
    except Exception as e:
        print(f"⚠️ Failed to spawn vehicle on {edge_id}: {e}")
        return False

# ============================================================================
# SIMULATION THREAD
# ============================================================================

def run_sumo_simulation():
    """Run SUMO with TomTom-driven normal traffic only."""
    global simulation_running

    print("\n🚗 Starting SUMO (TomTom normal traffic only)...")
    try:
        try:
            traci.close()
        except Exception:
            pass

        traci.start([
            SUMO_BINARY,
            '-c', SUMO_CONFIG,
            '--start',
            '--quit-on-end',
            '--step-length', str(SIM_STEP_LENGTH),
            '--no-warnings', 'true',
            '--time-to-teleport', '300'
        ])
        print(" ✅ SUMO started")

        # TomTom summary and apply speeds
        summary = build_tomtom_summary()
        speed_factor = summary["speed_factor"]
        density_level = summary["density_level"]

        apply_speed_factor_to_bbox_lanes(speed_factor)
        bbox_edges = get_edges_in_bbox()
        if not bbox_edges:
            print("⚠️ No edges in bbox; running with default network (no TomTom-based spawning)")
        target_count = compute_target_vehicle_count(density_level)
        print(f"🎯 Target normal vehicles in bbox: {target_count}")

        simulation_running = True
        step_count = 0
        last_log = time.time()
        last_spawn_time = 0.0

        while simulation_running and step_count * SIM_STEP_LENGTH <= MAX_SIM_SECONDS:
            sim_time = traci.simulation.getTime()

            # Spawn normal vehicles according to density
            vehicle_ids_now = traci.vehicle.getIDList()
            current_count = len(vehicle_ids_now)
            if bbox_edges and (sim_time - last_spawn_time) >= 1.0:
                if current_count < target_count:
                    gap = target_count - current_count
                    spawn_attempts = min(10, max(1, gap // 20))
                    for _ in range(spawn_attempts):
                        edge_id = random.choice(bbox_edges)
                        spawn_normal_vehicle(edge_id)
                    last_spawn_time = sim_time

            # Advance SUMO
            traci.simulationStep()
            step_count += 1
            time.sleep(SIM_STEP_LENGTH)
            sim_time = traci.simulation.getTime()
            vehicle_ids = traci.vehicle.getIDList()

            # Build vehicles list for frontend
            vehicles_data = []
            for vid in vehicle_ids:
                try:
                    x, y = traci.vehicle.getPosition(vid)
                    lon, lat = traci.simulation.convertGeo(x, y)
                    speed = traci.vehicle.getSpeed(vid)
                    angle = traci.vehicle.getAngle(vid)
                    color = traci.vehicle.getColor(vid)
                    vehicles_data.append({
                        "id": vid,
                        "lat": lat,
                        "lon": lon,
                        "speed": round(speed * 3.6, 1),
                        "angle": angle,
                        "is_ambulance": False,
                        "color": {"r": color[0], "g": color[1], "b": color[2]}
                    })
                except Exception:
                    continue

            # Emit simulation_update in existing format
            update_data = {
                "sim_time": sim_time,
                "step": step_count,
                "vehicle_count": len(vehicles_data),
                "vehicles": vehicles_data,
                "traffic_lights": {},           # empty for now
                "ambulances": [],               # none in this phase
                "active_green_corridors": 0,
                "tomtom_avg_speed": summary["avg_currentSpeed"],
                "tomtom_freeflow": summary["avg_freeFlowSpeed"],
                "tomtom_speed_factor": speed_factor,
                "tomtom_density_level": density_level
            }
            socketio.emit("simulation_update", update_data, namespace="/")

            if time.time() - last_log > 10:
                print(f" ⏱️ {int(sim_time)}s | Vehicles: {len(vehicles_data)}")
                last_log = time.time()

        print("\n✅ TomTom-only simulation completed")

    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_running = False
        try:
            traci.close()
        except Exception:
            pass
        socketio.emit("simulation_ended", {"message": "Simulation completed"}, namespace="/")

# ============================================================================
# API ENDPOINTS (MATCH EXISTING FRONTEND)
# ============================================================================

@app.route("/")
def index():
    return jsonify({
        "name": "TomTom-only Traffic Backend",
        "version": "1.0",
        "simulation_running": simulation_running
    })


@app.route("/api/simulation/start", methods=["POST"])
def start_simulation():
    global simulation_running, simulation_thread
    if simulation_running:
        return jsonify({"error": "Simulation already running"}), 400
    print("\n🚀 Starting TomTom-only simulation...")
    simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
    simulation_thread.start()
    return jsonify({"message": "Simulation started", "status": "running"})


@app.route("/api/simulation/stop", methods=["POST"])
def stop_simulation():
    global simulation_running
    if not simulation_running:
        return jsonify({"error": "Simulation not running"}), 400
    print("\n⏹️ Stopping simulation...")
    simulation_running = False
    return jsonify({"message": "Simulation stopping", "status": "stopping"})


@app.route("/api/simulation/status", methods=["GET"])
def get_simulation_status():
    try:
        count = traci.vehicle.getIDCount() if simulation_running else 0
    except Exception:
        count = 0
    return jsonify({
        "running": simulation_running,
        "vehicle_count": count
    })

# ============================================================================
# SOCKET.IO BASIC HANDLERS
# ============================================================================

@socketio.on("connect")
def handle_connect():
    print("✅ Client connected (TomTom-only backend)")
    emit("connection_response", {
        "status": "connected",
        "simulation_running": simulation_running
    })


@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Client disconnected (TomTom-only backend)")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 TOMTOM-ONLY TRAFFIC BACKEND")
    print("=" * 80)
    print("\n⏹️ Press Ctrl+C to stop\n")

    try:
        socketio.run(
            app,
            host="0.0.0.0",
            port=5000,   # use 5000 so your existing frontend works without change
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n\n⏹️ Server stopped by user")
        simulation_running = False
        try:
            traci.close()
        except Exception:
            pass
