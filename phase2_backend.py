#!/usr/bin/env python3
"""
PHASE 2 - Real-Time Traffic Backend with Individual Traffic Signals
====================================================================
Splits traffic light clusters into individual signals for accurate visualization
"""

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import traci
import threading
import time
import json
import os
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'green-corridor-phase2-2025'

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
SUMO_BINARY = 'sumo'  # Use 'sumo-gui' for debugging

# Simulation state
simulation_running = False
simulation_thread = None
connected_clients = set()

print("=" * 80)
print("PHASE 2 - REAL-TIME TRAFFIC BACKEND (INDIVIDUAL SIGNALS)")
print("=" * 80)

# ============================================================================
# LOAD STATIC DATA
# ============================================================================

print("\n📂 Loading static data...")

with open(os.path.join(DATA_DIR, 'traffic_lights.json'), 'r') as f:
    TRAFFIC_LIGHTS = json.load(f)
    print(f"   ✅ {len(TRAFFIC_LIGHTS)} traffic light clusters")

with open(os.path.join(DATA_DIR, 'hospitals.json'), 'r') as f:
    HOSPITALS = json.load(f)
    print(f"   ✅ {len(HOSPITALS)} hospitals")

with open(os.path.join(DATA_DIR, 'valid_routes.json'), 'r') as f:
    VALID_ROUTES = json.load(f)
    print(f"   ✅ {len(VALID_ROUTES)} valid routes")

# ============================================================================
# SUMO SIMULATION THREAD
# ============================================================================

def run_sumo_simulation():
    """Run SUMO simulation and stream vehicle + individual signal data"""
    global simulation_running
    
    print("\n🚗 Starting SUMO simulation with individual traffic signals...")
    
    try:
        # Start SUMO with TraCI
        traci.start([
            SUMO_BINARY,
            '-c', SUMO_CONFIG,
            '--start',
            '--quit-on-end',
            '--step-length', '1',
            '--no-warnings', 'true',
            '--time-to-teleport', '300'
        ])
        
        print("   ✅ SUMO connected via TraCI")
        simulation_running = True
        
        step_count = 0
        update_interval = 1  # Send updates every 1 second
        
        while simulation_running and step_count < 36000:  # 10 hours
            # Advance simulation by 1 step
            traci.simulationStep()
            step_count += 1
            
            # SLOW DOWN SIMULATION - Adjust to control speed
            time.sleep(0.5)  # 0.5 = half real-time
            
            # Get current simulation time
            sim_time = traci.simulation.getTime()
            
            # Get all vehicles currently in simulation
            vehicle_ids = traci.vehicle.getIDList()
            
            # ================================================================
            # GET INDIVIDUAL TRAFFIC LIGHT SIGNAL STATES
            # ================================================================
            tl_states = {}
            tl_ids = traci.trafficlight.getIDList()
            
            for tl_id in tl_ids:
                try:
                    # Get the current signal state (e.g., "GGrrGGrr")
                    state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    
                    # Get controlled links (each link = one signal)
                    controlled_links = traci.trafficlight.getControlledLinks(tl_id)
                    
                    if not controlled_links or len(controlled_links) == 0:
                        continue
                    
                    # Get traffic light position from controlled lanes
                    positions = []
                    for link in controlled_links:
                        try:
                            if link and len(link) > 0:
                                incoming_lane = link[0][0]  # First element is incoming lane
                                lane_shape = traci.lane.getShape(incoming_lane)
                                if lane_shape and len(lane_shape) > 0:
                                    # Use end point of lane (where signal is)
                                    positions.append(lane_shape[-1])
                        except:
                            continue
                    
                    if not positions:
                        continue
                    
                    # Create individual signals for each link
                    for link_index, link in enumerate(controlled_links):
                        if link_index >= len(state):
                            break
                        
                        try:
                            # Get signal state for this specific link
                            signal_state = state[link_index]
                            
                            # Determine color for this specific signal
                            if signal_state in ['r', 'R']:
                                color = 'red'
                            elif signal_state in ['y', 'Y']:
                                color = 'yellow'
                            elif signal_state in ['g', 'G']:
                                color = 'green'
                            else:
                                color = 'off'
                            
                            # Get position for this link
                            if link_index < len(positions):
                                x, y = positions[link_index]
                            elif positions:
                                # Fall back to first position if not enough positions
                                x, y = positions[0]
                                # Add small offset to avoid overlap
                                x += link_index * 2
                                y += link_index * 2
                            else:
                                continue
                            
                            # Convert to lat/lon
                            lon, lat = traci.simulation.convertGeo(x, y)
                            
                            # Create unique ID for each signal
                            signal_id = f"{tl_id}_link_{link_index}"
                            
                            # Get incoming lane info
                            incoming_lane = None
                            if link and len(link) > 0:
                                incoming_lane = link[0][0]
                            
                            tl_states[signal_id] = {
                                'id': signal_id,
                                'cluster_id': tl_id,
                                'link_index': link_index,
                                'state': signal_state,
                                'color': color,
                                'lat': lat,
                                'lon': lon,
                                'incoming_lane': incoming_lane
                            }
                        
                        except Exception as e:
                            continue
                    
                except Exception as e:
                    continue
            
            # Debug: Print example at step 10
            if step_count == 10 and tl_ids:
                print(f"\n🚦 Traffic Signal Breakdown Example:")
                cluster_example = tl_ids[0]
                cluster_signals = [k for k in tl_states.keys() if cluster_example in k]
                print(f"   Cluster: {cluster_example}")
                print(f"   Individual signals: {len(cluster_signals)}")
                for sig_id in cluster_signals[:5]:
                    sig = tl_states[sig_id]
                    print(f"     - Link {sig['link_index']}: {sig['state']} → {sig['color']}")
                print()
            
            # ================================================================
            # Collect vehicle data
            # ================================================================
            vehicles_data = []
            
            for veh_id in vehicle_ids:
                try:
                    # Get vehicle position (x, y in SUMO coordinates)
                    x, y = traci.vehicle.getPosition(veh_id)
                    
                    # Convert to lat/lon
                    lon, lat = traci.simulation.convertGeo(x, y)
                    
                    # Get vehicle data
                    speed = traci.vehicle.getSpeed(veh_id)  # m/s
                    angle = traci.vehicle.getAngle(veh_id)  # degrees
                    veh_type = traci.vehicle.getTypeID(veh_id)
                    road_id = traci.vehicle.getRoadID(veh_id)
                    
                    # Get color based on type
                    color = traci.vehicle.getColor(veh_id)
                    
                    vehicle_info = {
                        'id': veh_id,
                        'lat': lat,
                        'lon': lon,
                        'speed': round(speed * 3.6, 1),  # Convert to km/h
                        'angle': angle,
                        'type': veh_type,
                        'road': road_id,
                        'color': {
                            'r': color[0],
                            'g': color[1],
                            'b': color[2]
                        }
                    }
                    
                    vehicles_data.append(vehicle_info)
                    
                except traci.exceptions.TraCIException:
                    continue
            
            # Send update to all connected clients every second
            if step_count % update_interval == 0:
                update_data = {
                    'sim_time': sim_time,
                    'step': step_count,
                    'vehicle_count': len(vehicles_data),
                    'vehicles': vehicles_data,
                    'traffic_lights': tl_states  # Individual signals!
                }
                
                # Broadcast to all connected clients
                socketio.emit('simulation_update', update_data, namespace='/')
            
            # Progress log every 60 seconds
            if step_count % 60 == 0:
                print(f"   Sim: {int(sim_time)}s | Vehicles: {len(vehicles_data)} | Signals: {len(tl_states)} | Clients: {len(connected_clients)}")
        
        print("\n✅ Simulation completed")
        
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        simulation_running = False
        try:
            traci.close()
            print("   TraCI connection closed")
        except:
            pass
        
        # Notify clients simulation ended
        socketio.emit('simulation_ended', {'message': 'Simulation completed'})

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    return jsonify({
        'name': 'Green Corridor Phase 2 API (Individual Signals)',
        'version': '2.0',
        'simulation_running': simulation_running,
        'connected_clients': len(connected_clients)
    })

@app.route('/api/traffic-lights', methods=['GET'])
def get_traffic_lights():
    return jsonify(TRAFFIC_LIGHTS)

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    return jsonify(HOSPITALS)

@app.route('/api/routes', methods=['GET'])
def get_routes():
    return jsonify(VALID_ROUTES)

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    """Start SUMO simulation in background thread"""
    global simulation_running, simulation_thread
    
    if simulation_running:
        return jsonify({'error': 'Simulation already running'}), 400
    
    simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
    simulation_thread.start()
    
    return jsonify({'message': 'Simulation started', 'status': 'running'})

@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    """Stop SUMO simulation"""
    global simulation_running
    
    if not simulation_running:
        return jsonify({'error': 'Simulation not running'}), 400
    
    simulation_running = False
    
    return jsonify({'message': 'Simulation stopping', 'status': 'stopping'})

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Get current simulation status"""
    return jsonify({
        'running': simulation_running,
        'connected_clients': len(connected_clients)
    })

# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Client connected to WebSocket"""
    client_id = request.sid
    connected_clients.add(client_id)
    
    print(f'✅ Client connected: {client_id} (Total: {len(connected_clients)})')
    
    emit('connection_response', {
        'status': 'connected',
        'client_id': client_id,
        'simulation_running': simulation_running
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    client_id = request.sid
    connected_clients.discard(client_id)
    
    print(f'❌ Client disconnected: {client_id} (Total: {len(connected_clients)})')

@socketio.on('request_simulation_start')
def handle_start_request():
    """Client requests simulation start"""
    global simulation_running, simulation_thread
    
    if not simulation_running:
        simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
        simulation_thread.start()
        
        emit('simulation_started', {'message': 'Simulation started'}, broadcast=True)

@socketio.on('request_simulation_stop')
def handle_stop_request():
    """Client requests simulation stop"""
    global simulation_running
    
    simulation_running = False
    emit('simulation_stopped', {'message': 'Simulation stopping'}, broadcast=True)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🚀 STARTING PHASE 2 BACKEND (INDIVIDUAL TRAFFIC SIGNALS)")
    print("=" * 80)
    print("\n📍 Backend: http://localhost:5000")
    print("📍 WebSocket: ws://localhost:5000")
    print("\n💡 Frontend: http://localhost:3000")
    print("\n⚙️  Simulation Speed: 0.5x (adjust time.sleep in code)")
    print("🚦 Traffic Signals: Individual (not clusters)")
    print("\n⏹️  Press Ctrl+C to stop")
    print("=" * 80 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False
    )
