#!/usr/bin/env python3

"""
Ambulance Routing Backend - Smart Green Corridor with Rolling Signal Release
============================================================================
Signals are released immediately as ambulance passes them (rolling green wave)
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
import math

# ============================================================================
# CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ambulance-routing-2025'
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
MIN_VEHICLES = 100
GREEN_CORRIDOR_DETECTION_DISTANCE = 100  # meters - detect signals within this distance
SIGNAL_ACTIVATION_DISTANCE = 80  # meters - turn signal green when within this distance
SIGNAL_RELEASE_DELAY = 3  # seconds - release signal after this time past control

# Simulation state
simulation_running = False
simulation_thread = None
connected_clients = set()

# Ambulance tracking
active_ambulances = {}
ambulance_counter = 0

# Traffic signal management
CACHED_SIGNAL_POSITIONS = {}
ambulance_controlled_signals = {}  # Track which signals each ambulance has controlled

print("=" * 80)
print("AMBULANCE ROUTING BACKEND - ROLLING GREEN CORRIDOR")
print("=" * 80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n📂 Loading data...")

try:
    with open(os.path.join(DATA_DIR, 'hospitals.json'), 'r') as f:
        HOSPITALS = json.load(f)
    print(f"✅ Loaded {len(HOSPITALS)} hospitals")
except Exception as e:
    print(f"❌ Failed to load hospitals: {e}")
    sys.exit(1)

try:
    with open(os.path.join(DATA_DIR, 'hospital_routes_validated.json'), 'r') as f:
        ROUTE_DATA = json.load(f)
    print(f"✅ Loaded {ROUTE_DATA['assigned_routes']} validated routes")
except Exception as e:
    print(f"❌ Failed to load routes: {e}")
    sys.exit(1)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_route(source_idx, dest_idx):
    """Get route for hospital pair"""
    for route in ROUTE_DATA['routes']:
        if route['source_index'] == source_idx and route['dest_index'] == dest_idx:
            return route
    return None

def get_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance"""
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def get_upcoming_traffic_lights(vehicle_id, distance_threshold=GREEN_CORRIDOR_DETECTION_DISTANCE):
    """Get traffic lights ahead of vehicle within distance threshold"""
    try:
        # Get vehicle position and route
        x, y = traci.vehicle.getPosition(vehicle_id)
        route = traci.vehicle.getRoute(vehicle_id)
        route_index = traci.vehicle.getRouteIndex(vehicle_id)
        
        # Get upcoming edges (next 5 edges)
        upcoming_edges = route[route_index:route_index + 5]
        upcoming_signals = []
        
        # Get all traffic lights
        all_tls = traci.trafficlight.getIDList()
        
        for tl_id in all_tls:
            try:
                # Get controlled lanes
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                
                # Check if any controlled lane is on upcoming edges
                for lane in controlled_lanes:
                    edge_id = traci.lane.getEdgeID(lane)
                    if edge_id in upcoming_edges:
                        # Get position of traffic light
                        lane_shape = traci.lane.getShape(lane)
                        if lane_shape:
                            tl_x, tl_y = lane_shape[-1]
                            distance = get_distance(x, y, tl_x, tl_y)
                            
                            if distance <= distance_threshold:
                                upcoming_signals.append({
                                    'tl_id': tl_id,
                                    'distance': distance,
                                    'edge': edge_id,
                                    'position': (tl_x, tl_y)
                                })
                                break  # Don't add same TL multiple times
            except Exception as e:
                continue
        
        # Sort by distance
        upcoming_signals.sort(key=lambda x: x['distance'])
        return upcoming_signals[:3]  # Return closest 3 signals
    
    except Exception as e:
        return []

def set_green_corridor(tl_id, ambulance_id):
    """Force traffic light to green for ambulance"""
    try:
        # Get current state
        current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
        
        # Create all-green state (replace all 'r', 'y' with 'G')
        green_state = current_state.replace('r', 'G').replace('R', 'G').replace('y', 'G').replace('Y', 'G')
        
        # Set to green
        traci.trafficlight.setRedYellowGreenState(tl_id, green_state)
        
        # Track which ambulance controlled this signal
        if ambulance_id not in ambulance_controlled_signals:
            ambulance_controlled_signals[ambulance_id] = {}
        
        # Only update if not already controlled or needs refresh
        if tl_id not in ambulance_controlled_signals[ambulance_id]:
            ambulance_controlled_signals[ambulance_id][tl_id] = {
                'timestamp': time.time(),
                'released': False,
                'first_controlled': time.time()
            }
        else:
            # Update timestamp (ambulance still near this signal)
            ambulance_controlled_signals[ambulance_id][tl_id]['timestamp'] = time.time()
        
        return True
    except Exception as e:
        print(f" ⚠️ Failed to set green corridor for {tl_id}: {e}")
        return False

def release_signal(tl_id, ambulance_id):
    """Release a single signal back to normal operation"""
    try:
        traci.trafficlight.setProgram(tl_id, "0")
        
        if ambulance_id in ambulance_controlled_signals:
            if tl_id in ambulance_controlled_signals[ambulance_id]:
                ambulance_controlled_signals[ambulance_id][tl_id]['released'] = True
        
        return True
    except Exception as e:
        print(f" ⚠️ Failed to release {tl_id}: {e}")
        return False

def release_ambulance_signals(ambulance_id):
    """Release all signals controlled by this ambulance"""
    if ambulance_id not in ambulance_controlled_signals:
        return
    
    print(f"\n🔄 Releasing all signals for {ambulance_id}...")
    released_count = 0
    
    for tl_id, signal_info in ambulance_controlled_signals[ambulance_id].items():
        if not signal_info['released']:
            if release_signal(tl_id, ambulance_id):
                released_count += 1
                print(f" ⚪ Restored: {tl_id}")
    
    if released_count > 0:
        print(f" ✅ Released {released_count} signals")
    
    # Clean up tracking
    del ambulance_controlled_signals[ambulance_id]

def check_and_release_passed_signals(ambulance_id):
    """Release signals that the ambulance has passed"""
    if ambulance_id not in ambulance_controlled_signals:
        return
    
    try:
        # Get ambulance position
        x, y = traci.vehicle.getPosition(ambulance_id)
        current_time = time.time()
        
        for tl_id, signal_info in list(ambulance_controlled_signals[ambulance_id].items()):
            if signal_info['released']:
                continue
            
            # Check how long since we last updated this signal
            time_since_last_update = current_time - signal_info['timestamp']
            
            # If we haven't updated this signal in SIGNAL_RELEASE_DELAY seconds,
            # it means ambulance has moved past it
            if time_since_last_update > SIGNAL_RELEASE_DELAY:
                if release_signal(tl_id, ambulance_id):
                    # Calculate approximate distance (if possible)
                    try:
                        tl_lanes = traci.trafficlight.getControlledLanes(tl_id)
                        if tl_lanes:
                            lane_shape = traci.lane.getShape(tl_lanes[0])
                            if lane_shape:
                                tl_x, tl_y = lane_shape[-1]
                                distance = get_distance(x, y, tl_x, tl_y)
                                print(f" ⚪ Released passed signal: {tl_id} ({distance:.1f}m behind {ambulance_id})")
                            else:
                                print(f" ⚪ Released passed signal: {tl_id}")
                    except:
                        print(f" ⚪ Released passed signal: {tl_id}")
    
    except Exception as e:
        pass

# ============================================================================
# SUMO SIMULATION THREAD
# ============================================================================

def run_sumo_simulation():
    """Run SUMO simulation with rolling green corridor"""
    global simulation_running, active_ambulances, CACHED_SIGNAL_POSITIONS
    
    print("\n🚗 Starting SUMO simulation...")
    
    try:
        traci.start([
            SUMO_BINARY,
            '-c', SUMO_CONFIG,
            '--start',
            '--quit-on-end',
            '--step-length', '1',
            '--no-warnings', 'true',
            '--time-to-teleport', '300'
        ])
        
        print(" ✅ SUMO started")
        simulation_running = True
        step_count = 0
        last_log = time.time()
        
        while simulation_running and step_count < 36000:
            traci.simulationStep()
            step_count += 1
            time.sleep(0.5)
            
            sim_time = traci.simulation.getTime()
            vehicle_ids = traci.vehicle.getIDList()
            
            # ================================================================
            # ROLLING GREEN CORRIDOR MANAGEMENT
            # ================================================================
            
            active_green_corridors = set()
            
            for amb_id in list(active_ambulances.keys()):
                if amb_id in vehicle_ids:
                    try:
                        # Update ambulance info
                        road = traci.vehicle.getRoadID(amb_id)
                        speed = traci.vehicle.getSpeed(amb_id)
                        route = traci.vehicle.getRoute(amb_id)
                        route_index = traci.vehicle.getRouteIndex(amb_id)
                        x, y = traci.vehicle.getPosition(amb_id)
                        
                        active_ambulances[amb_id]['current_road'] = road
                        active_ambulances[amb_id]['speed'] = round(speed * 3.6, 1)
                        active_ambulances[amb_id]['status'] = 'en_route'
                        active_ambulances[amb_id]['progress'] = f"{route_index + 1}/{len(route)}"
                        active_ambulances[amb_id]['progress_percent'] = round((route_index + 1) / len(route) * 100, 1)
                        
                        # GREEN CORRIDOR MODE - Rolling green wave
                        if active_ambulances[amb_id]['mode'] == 'green_corridor':
                            upcoming_signals = get_upcoming_traffic_lights(amb_id)
                            
                            # Track current upcoming signals
                            current_upcoming_tl_ids = set()
                            
                            if upcoming_signals:
                                # Turn upcoming signals green
                                for signal_info in upcoming_signals:
                                    tl_id = signal_info['tl_id']
                                    distance = signal_info['distance']
                                    
                                    # Set to green if close enough
                                    if distance <= SIGNAL_ACTIVATION_DISTANCE:
                                        if set_green_corridor(tl_id, amb_id):
                                            active_green_corridors.add(tl_id)
                                            current_upcoming_tl_ids.add(tl_id)
                                            
                                            if step_count % 20 == 0:
                                                print(f" 🟢 Green corridor: {tl_id} for {amb_id} ({distance:.1f}m)")
                            
                            # Release signals that ambulance has passed
                            check_and_release_passed_signals(amb_id)
                    
                    except Exception as e:
                        pass
                
                else:
                    # Ambulance completed
                    if amb_id in active_ambulances:
                        if active_ambulances[amb_id].get('status') != 'arrived':
                            print(f"\n🏥 Ambulance {amb_id} ARRIVED at destination!")
                            
                            # Calculate travel time
                            spawn_time = active_ambulances[amb_id]['spawn_time']
                            arrival_time = time.time()
                            travel_duration = arrival_time - spawn_time
                            
                            active_ambulances[amb_id]['status'] = 'arrived'
                            active_ambulances[amb_id]['arrival_time'] = arrival_time
                            
                            # Release all remaining signals
                            release_ambulance_signals(amb_id)
                            
                            # Send complete history data to frontend
                            socketio.emit('ambulance_completed', {
                                'ambulance_id': amb_id,
                                'source': active_ambulances[amb_id]['source_name'],
                                'destination': active_ambulances[amb_id]['dest_name'],
                                'mode': active_ambulances[amb_id]['mode'],
                                'start_time': int(spawn_time * 1000),
                                'end_time': int(arrival_time * 1000),
                                'travel_time': round(travel_duration, 2),
                                'route_length': active_ambulances[amb_id]['route_length']
                            })
                            
                            print(f" ✅ Travel completed in {travel_duration:.1f}s")
                            print(f" 📊 History data sent to frontend")
                        
                        # Remove ambulance after 10 seconds
                        if time.time() - active_ambulances[amb_id].get('arrival_time', time.time()) > 10:
                            del active_ambulances[amb_id]
            
            # ================================================================
            # TRAFFIC LIGHTS WITH POSITION CACHING
            # ================================================================
            
            tl_data = {}
            tl_ids = traci.trafficlight.getIDList()
            
            for tl_id in tl_ids[:200]:
                try:
                    state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    controlled_links = traci.trafficlight.getControlledLinks(tl_id)
                    
                    if not controlled_links or len(controlled_links) == 0:
                        continue
                    
                    for link_index, link_set in enumerate(controlled_links):
                        if link_index >= len(state):
                            break
                        
                        if not link_set or len(link_set) == 0:
                            continue
                        
                        try:
                            signal_id = f"{tl_id}_link_{link_index}"
                            signal_state_char = state[link_index]
                            
                            if signal_state_char in ['r', 'R']:
                                color = 'red'
                            elif signal_state_char in ['y', 'Y']:
                                color = 'yellow'
                            elif signal_state_char in ['g', 'G']:
                                color = 'green'
                            else:
                                color = 'off'
                            
                            if signal_id in CACHED_SIGNAL_POSITIONS:
                                cached_pos = CACHED_SIGNAL_POSITIONS[signal_id]
                                tl_data[signal_id] = {
                                    'id': signal_id,
                                    'cluster_id': tl_id,
                                    'link_index': link_index,
                                    'state': signal_state_char,
                                    'color': color,
                                    'lat': cached_pos['lat'],
                                    'lon': cached_pos['lon'],
                                    'incoming_lane': cached_pos['incoming_lane'],
                                    'green_corridor_active': tl_id in active_green_corridors
                                }
                            else:
                                link = link_set[0]
                                if len(link) < 1:
                                    continue
                                
                                incoming_lane = link[0]
                                lane_shape = traci.lane.getShape(incoming_lane)
                                
                                if not lane_shape or len(lane_shape) == 0:
                                    continue
                                
                                x, y = lane_shape[-1]
                                lon, lat = traci.simulation.convertGeo(x, y)
                                lat = round(lat, 6)
                                lon = round(lon, 6)
                                
                                CACHED_SIGNAL_POSITIONS[signal_id] = {
                                    'lat': lat,
                                    'lon': lon,
                                    'incoming_lane': incoming_lane
                                }
                                
                                tl_data[signal_id] = {
                                    'id': signal_id,
                                    'cluster_id': tl_id,
                                    'link_index': link_index,
                                    'state': signal_state_char,
                                    'color': color,
                                    'lat': lat,
                                    'lon': lon,
                                    'incoming_lane': incoming_lane,
                                    'green_corridor_active': tl_id in active_green_corridors
                                }
                        
                        except Exception as e:
                            continue
                
                except Exception as e:
                    continue
            
            # ================================================================
            # COLLECT VEHICLE DATA
            # ================================================================
            
            vehicles_data = []
            for veh_id in vehicle_ids:
                try:
                    x, y = traci.vehicle.getPosition(veh_id)
                    lon, lat = traci.simulation.convertGeo(x, y)
                    speed = traci.vehicle.getSpeed(veh_id)
                    angle = traci.vehicle.getAngle(veh_id)
                    color = traci.vehicle.getColor(veh_id)
                    is_ambulance = veh_id in active_ambulances
                    
                    vehicle_info = {
                        'id': veh_id,
                        'lat': lat,
                        'lon': lon,
                        'speed': round(speed * 3.6, 1),
                        'angle': angle,
                        'is_ambulance': is_ambulance,
                        'color': {
                            'r': color[0],
                            'g': color[1],
                            'b': color[2]
                        }
                    }
                    vehicles_data.append(vehicle_info)
                except:
                    continue
            
            # ================================================================
            # PREPARE AMBULANCE DATA
            # ================================================================
            
            ambulance_data = []
            for amb_id, amb_info in active_ambulances.items():
                ambulance_data.append({
                    'id': amb_id,
                    'source': amb_info['source_name'],
                    'destination': amb_info['dest_name'],
                    'mode': amb_info['mode'],
                    'status': amb_info.get('status', 'spawning'),
                    'speed': amb_info.get('speed', 0),
                    'progress': amb_info.get('progress', '0/0'),
                    'progress_percent': amb_info.get('progress_percent', 0)
                })
            
            # ================================================================
            # SEND UPDATE
            # ================================================================
            
            if step_count % 1 == 0:
                update_data = {
                    'sim_time': sim_time,
                    'step': step_count,
                    'vehicle_count': len(vehicles_data),
                    'vehicles': vehicles_data,
                    'traffic_lights': tl_data,
                    'ambulances': ambulance_data,
                    'active_green_corridors': len(active_green_corridors)
                }
                socketio.emit('simulation_update', update_data, namespace='/')
            
            # ================================================================
            # CONSOLE LOG
            # ================================================================
            
            if time.time() - last_log > 10:
                print(f" ⏱️ {int(sim_time)}s | Vehicles: {len(vehicles_data)} | "
                      f"Ambulances: {len(active_ambulances)} | Signals: {len(tl_data)} | "
                      f"Green Corridors: {len(active_green_corridors)}")
                last_log = time.time()
        
        print("\n✅ Simulation completed")
    
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        simulation_running = False
        
        # Clean up all controlled signals
        for amb_id in list(ambulance_controlled_signals.keys()):
            release_ambulance_signals(amb_id)
        
        try:
            traci.close()
        except:
            pass
        
        socketio.emit('simulation_ended', {'message': 'Simulation completed'})

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    return jsonify({
        'name': 'Ambulance Routing Backend - Rolling Green Corridor',
        'version': '2.3',
        'simulation_running': simulation_running,
        'active_ambulances': len(active_ambulances),
        'hospitals': len(HOSPITALS),
        'cached_signals': len(CACHED_SIGNAL_POSITIONS),
        'controlled_signals': sum(len(signals) for signals in ambulance_controlled_signals.values())
    })

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    return jsonify(HOSPITALS)

@app.route('/api/spawn-ambulance', methods=['POST'])
def spawn_ambulance():
    global active_ambulances, ambulance_counter
    
    if not simulation_running:
        return jsonify({'error': 'Simulation not running'}), 400
    
    try:
        vehicle_count = traci.vehicle.getIDCount()
        if vehicle_count < MIN_VEHICLES:
            return jsonify({
                'error': f'Waiting for traffic to build up',
                'current_vehicles': vehicle_count,
                'required_vehicles': MIN_VEHICLES
            }), 400
    except:
        pass
    
    data = request.json
    source_idx = data.get('source')
    dest_idx = data.get('destination')
    mode = data.get('mode', 'normal')
    
    if source_idx is None or dest_idx is None:
        return jsonify({'error': 'Source and destination required'}), 400
    
    if source_idx == dest_idx:
        return jsonify({'error': 'Source and destination cannot be same'}), 400
    
    print(f"\n{'='*80}")
    print(f"🚑 AMBULANCE SPAWN REQUEST")
    print(f"{'='*80}")
    print(f" Source: Hospital {source_idx}")
    print(f" Destination: Hospital {dest_idx}")
    print(f" Mode: {mode}")
    
    route_info = get_route(source_idx, dest_idx)
    
    if not route_info:
        return jsonify({'error': f'No route found for hospitals {source_idx} → {dest_idx}'}), 400
    
    route_edges = route_info['route_edges']
    ambulance_counter += 1
    amb_id = f"ambulance_{ambulance_counter}_{int(time.time())}"
    
    try:
        traci.vehicle.add(
            vehID=amb_id,
            routeID='',
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        
        traci.vehicle.setRoute(amb_id, route_edges)
        
        if mode == 'green_corridor':
            # Green corridor: GREEN color, smart signal control
            traci.vehicle.setColor(amb_id, (0, 255, 0, 255))
            traci.vehicle.setSpeedMode(amb_id, 32)
            traci.vehicle.setMaxSpeed(amb_id, 30)
            print(f" Mode: ROLLING GREEN CORRIDOR 🟢 (Releases signals as it passes)")
        else:
            # Normal mode: RED color, respects all signals
            traci.vehicle.setColor(amb_id, (255, 0, 0, 255))
            traci.vehicle.setMaxSpeed(amb_id, 25)
            print(f" Mode: NORMAL 🔴 (Respects all signals)")
        
        active_ambulances[amb_id] = {
            'source_idx': source_idx,
            'dest_idx': dest_idx,
            'source_name': route_info['source_name'],
            'dest_name': route_info['dest_name'],
            'mode': mode,
            'spawn_time': time.time(),
            'status': 'spawned',
            'route': route_edges,
            'route_length': len(route_edges)
        }
        
        print(f" ✅ Ambulance spawned: {amb_id}")
        print(f"{'='*80}\n")
        
        socketio.emit('ambulance_spawned', {
            'ambulance_id': amb_id,
            'source': route_info['source_name'],
            'destination': route_info['dest_name'],
            'mode': mode
        })
        
        return jsonify({
            'success': True,
            'ambulance_id': amb_id,
            'source': route_info['source_name'],
            'destination': route_info['dest_name'],
            'mode': mode,
            'route_length': len(route_edges),
            'message': 'Ambulance spawned successfully'
        })
    
    except Exception as e:
        print(f" ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ambulances', methods=['GET'])
def get_ambulances():
    ambulances_list = []
    for amb_id, amb_info in active_ambulances.items():
        ambulances_list.append({
            'id': amb_id,
            'source': amb_info['source_name'],
            'destination': amb_info['dest_name'],
            'mode': amb_info['mode'],
            'status': amb_info.get('status', 'unknown'),
            'speed': amb_info.get('speed', 0),
            'progress': amb_info.get('progress', '0/0'),
            'progress_percent': amb_info.get('progress_percent', 0)
        })
    return jsonify(ambulances_list)

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    global simulation_running, simulation_thread
    
    if simulation_running:
        return jsonify({'error': 'Simulation already running'}), 400
    
    print("\n🚀 Starting simulation...")
    simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
    simulation_thread.start()
    
    return jsonify({'message': 'Simulation started', 'status': 'running'})

@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    global simulation_running
    
    if not simulation_running:
        return jsonify({'error': 'Simulation not running'}), 400
    
    print("\n⏹️ Stopping simulation...")
    simulation_running = False
    
    return jsonify({'message': 'Simulation stopping', 'status': 'stopping'})

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    try:
        vehicle_count = traci.vehicle.getIDCount() if simulation_running else 0
    except:
        vehicle_count = 0
    
    return jsonify({
        'running': simulation_running,
        'vehicle_count': vehicle_count,
        'ready_for_ambulances': vehicle_count >= MIN_VEHICLES,
        'min_vehicles_required': MIN_VEHICLES,
        'connected_clients': len(connected_clients),
        'active_ambulances': len(active_ambulances),
        'cached_signals': len(CACHED_SIGNAL_POSITIONS),
        'controlled_signals': sum(len(signals) for signals in ambulance_controlled_signals.values())
    })

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
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
    client_id = request.sid
    connected_clients.discard(client_id)
    print(f'❌ Client disconnected: {client_id} (Total: {len(connected_clients)})')

@socketio.on('request_simulation_start')
def handle_start_request():
    global simulation_running, simulation_thread
    
    if not simulation_running:
        print("\n🚀 Starting simulation via WebSocket...")
        simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
        simulation_thread.start()
        emit('simulation_started', {'message': 'Simulation started'}, broadcast=True)
    else:
        emit('error', {'message': 'Simulation already running'})

@socketio.on('request_simulation_stop')
def handle_stop_request():
    global simulation_running
    
    if simulation_running:
        print("\n⏹️ Stopping simulation via WebSocket...")
        simulation_running = False
        emit('simulation_stopped', {'message': 'Simulation stopping'}, broadcast=True)
    else:
        emit('error', {'message': 'Simulation not running'})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 AMBULANCE ROUTING BACKEND - ROLLING GREEN CORRIDOR")
    print("="*80)
    print("\n📊 Configuration:")
    print(f" • Hospitals: {len(HOSPITALS)}")
    print(f" • Validated routes: {ROUTE_DATA['assigned_routes']}")
    print(f" • Min vehicles for spawn: {MIN_VEHICLES}")
    print(f" • Green corridor detection: {GREEN_CORRIDOR_DETECTION_DISTANCE}m")
    print(f" • Signal activation distance: {SIGNAL_ACTIVATION_DISTANCE}m")
    print(f" • Signal release delay: {SIGNAL_RELEASE_DELAY}s after passing")
    print("\n🌐 Server:")
    print(" • Backend API: http://localhost:5000")
    print(" • WebSocket: ws://localhost:5000")
    print("\n🚑 Features:")
    print(" • Normal Mode: Red ambulance, respects all traffic lights")
    print(" • Rolling Green Corridor: Green ambulance, creates rolling green wave")
    print(" • ✅ Signals released immediately as ambulance passes (3s delay)")
    print(" • Complete history tracking")
    print(" • Real-time tracking via WebSocket")
    print("\n⏹️ Press Ctrl+C to stop")
    print("="*80 + "\n")
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n\n⏹️ Server stopped by user")
        simulation_running = False
        
        # Clean up all signals on exit
        for amb_id in list(ambulance_controlled_signals.keys()):
            release_ambulance_signals(amb_id)
        
        try:
            traci.close()
        except:
            pass
