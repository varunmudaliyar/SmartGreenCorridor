#!/usr/bin/env python3
"""
Ambulance Routing Backend - Web Integration
===========================================
Flask + SocketIO backend for ambulance routing web application
Supports Normal Mode and Green Corridor Mode
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

MIN_VEHICLES = 100  # Wait for traffic before allowing spawns

# Simulation state
simulation_running = False
simulation_thread = None
connected_clients = set()

# Ambulance tracking
active_ambulances = {}
ambulance_counter = 0

print("=" * 80)
print("AMBULANCE ROUTING BACKEND - WEB INTEGRATION")
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

# ============================================================================
# SUMO SIMULATION THREAD
# ============================================================================

def run_sumo_simulation():
    """Run SUMO simulation"""
    global simulation_running, active_ambulances
    
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
        
        print("   ✅ SUMO started")
        simulation_running = True
        
        step_count = 0
        last_log = time.time()
        
        while simulation_running and step_count < 36000:
            traci.simulationStep()
            step_count += 1
            time.sleep(0.5)  # Simulation speed
            
            sim_time = traci.simulation.getTime()
            vehicle_ids = traci.vehicle.getIDList()
            
            # Update ambulances
            for amb_id in list(active_ambulances.keys()):
                if amb_id in vehicle_ids:
                    try:
                        road = traci.vehicle.getRoadID(amb_id)
                        speed = traci.vehicle.getSpeed(amb_id)
                        route = traci.vehicle.getRoute(amb_id)
                        route_index = traci.vehicle.getRouteIndex(amb_id)
                        position = traci.vehicle.getPosition(amb_id)
                        
                        active_ambulances[amb_id]['current_road'] = road
                        active_ambulances[amb_id]['speed'] = round(speed * 3.6, 1)
                        active_ambulances[amb_id]['status'] = 'en_route'
                        active_ambulances[amb_id]['progress'] = f"{route_index + 1}/{len(route)}"
                        active_ambulances[amb_id]['progress_percent'] = round((route_index + 1) / len(route) * 100, 1)
                        
                    except:
                        pass
                else:
                    # Ambulance completed
                    if amb_id in active_ambulances:
                        if active_ambulances[amb_id].get('status') != 'arrived':
                            print(f"\n🏥 Ambulance {amb_id} ARRIVED at destination!")
                            active_ambulances[amb_id]['status'] = 'arrived'
                            active_ambulances[amb_id]['arrival_time'] = time.time()
                            
                            # Notify clients
                            socketio.emit('ambulance_arrived', {
                                'ambulance_id': amb_id,
                                'source': active_ambulances[amb_id]['source_name'],
                                'destination': active_ambulances[amb_id]['dest_name']
                            })
                        
                        # Remove after 10 seconds
                        if time.time() - active_ambulances[amb_id].get('arrival_time', time.time()) > 10:
                            del active_ambulances[amb_id]
            
            # Get traffic light states
            tl_states = {}
            tl_ids = traci.trafficlight.getIDList()
            
            for tl_id in tl_ids[:100]:  # Limit for performance
                try:
                    state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    controlled_links = traci.trafficlight.getControlledLinks(tl_id)
                    
                    if not controlled_links:
                        continue
                    
                    for link_index, link in enumerate(controlled_links[:4]):  # First 4 links
                        if link_index >= len(state):
                            break
                        
                        try:
                            signal_state = state[link_index]
                            
                            if signal_state in ['r', 'R']:
                                color = 'red'
                            elif signal_state in ['y', 'Y']:
                                color = 'yellow'
                            elif signal_state in ['g', 'G']:
                                color = 'green'
                            else:
                                color = 'off'
                            
                            if link and len(link) > 0:
                                incoming_lane = link[0][0]
                                lane_shape = traci.lane.getShape(incoming_lane)
                                if lane_shape:
                                    x, y = lane_shape[-1]
                                    lon, lat = traci.simulation.convertGeo(x, y)
                                    
                                    signal_id = f"{tl_id}_link_{link_index}"
                                    
                                    tl_states[signal_id] = {
                                        'id': signal_id,
                                        'cluster_id': tl_id,
                                        'state': signal_state,
                                        'color': color,
                                        'lat': lat,
                                        'lon': lon
                                    }
                        except:
                            continue
                            
                except:
                    continue
            
            # Collect vehicle data
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
            
            # Send update to clients
            if step_count % 1 == 0:  # Every step
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
                
                update_data = {
                    'sim_time': sim_time,
                    'step': step_count,
                    'vehicle_count': len(vehicles_data),
                    'vehicles': vehicles_data,
                    'traffic_lights': tl_states,
                    'ambulances': ambulance_data
                }
                
                socketio.emit('simulation_update', update_data, namespace='/')
            
            # Console log
            if time.time() - last_log > 10:
                print(f"   ⏱️  {int(sim_time)}s | Vehicles: {len(vehicles_data)} | Ambulances: {len(active_ambulances)}")
                last_log = time.time()
        
        print("\n✅ Simulation completed")
        
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_running = False
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
    """API root"""
    return jsonify({
        'name': 'Ambulance Routing Backend',
        'version': '1.0',
        'simulation_running': simulation_running,
        'active_ambulances': len(active_ambulances),
        'hospitals': len(HOSPITALS)
    })

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    """Get all hospitals"""
    return jsonify(HOSPITALS)

@app.route('/api/spawn-ambulance', methods=['POST'])
def spawn_ambulance():
    """Spawn ambulance with source and destination"""
    global active_ambulances, ambulance_counter
    
    if not simulation_running:
        return jsonify({'error': 'Simulation not running'}), 400
    
    # Check minimum vehicle count
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
    mode = data.get('mode', 'normal')  # 'normal' or 'green_corridor'
    
    if source_idx is None or dest_idx is None:
        return jsonify({'error': 'Source and destination required'}), 400
    
    if source_idx == dest_idx:
        return jsonify({'error': 'Source and destination cannot be same'}), 400
    
    print(f"\n{'='*80}")
    print(f"🚑 AMBULANCE SPAWN REQUEST")
    print(f"{'='*80}")
    print(f"   Source: Hospital {source_idx}")
    print(f"   Destination: Hospital {dest_idx}")
    print(f"   Mode: {mode}")
    
    # Get route
    route_info = get_route(source_idx, dest_idx)
    if not route_info:
        return jsonify({'error': f'No route found for hospitals {source_idx} → {dest_idx}'}), 400
    
    route_edges = route_info['route_edges']
    spawn_edge = route_info['spawn_edge']
    
    print(f"   Route edges: {len(route_edges)}")
    print(f"   Spawn edge: {spawn_edge}")
    
    # Create ambulance ID
    ambulance_counter += 1
    amb_id = f"ambulance_{ambulance_counter}_{int(time.time())}"
    
    try:
        # Add vehicle to SUMO
        print(f"   Adding to SUMO...")
        traci.vehicle.add(
            vehID=amb_id,
            routeID='',
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        
        # Set route
        traci.vehicle.setRoute(amb_id, route_edges)
        
        # Configure based on mode
        if mode == 'green_corridor':
            # Green corridor: GREEN color, ignores traffic lights
            traci.vehicle.setColor(amb_id, (0, 255, 0, 255))
            traci.vehicle.setSpeedMode(amb_id, 32)  # Ignore traffic lights
            traci.vehicle.setMaxSpeed(amb_id, 30)
            print(f"   Mode: GREEN CORRIDOR 🟢")
        else:
            # Normal mode: RED color, respects traffic lights
            traci.vehicle.setColor(amb_id, (255, 0, 0, 255))
            traci.vehicle.setMaxSpeed(amb_id, 25)
            print(f"   Mode: NORMAL 🔴")
        
        # Track ambulance
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
        
        print(f"   ✅ Ambulance spawned: {amb_id}")
        print(f"{'='*80}\n")
        
        # Notify clients
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
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ambulances', methods=['GET'])
def get_ambulances():
    """Get all active ambulances"""
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
    """Start SUMO simulation"""
    global simulation_running, simulation_thread
    
    if simulation_running:
        return jsonify({'error': 'Simulation already running'}), 400
    
    print("\n🚀 Starting simulation...")
    simulation_thread = threading.Thread(target=run_sumo_simulation, daemon=True)
    simulation_thread.start()
    
    return jsonify({'message': 'Simulation started', 'status': 'running'})

@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    """Stop SUMO simulation"""
    global simulation_running
    
    if not simulation_running:
        return jsonify({'error': 'Simulation not running'}), 400
    
    print("\n⏹️  Stopping simulation...")
    simulation_running = False
    
    return jsonify({'message': 'Simulation stopping', 'status': 'stopping'})

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Get simulation status"""
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
        'active_ambulances': len(active_ambulances)
    })

# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
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
    """Handle client disconnection"""
    client_id = request.sid
    connected_clients.discard(client_id)
    print(f'❌ Client disconnected: {client_id} (Total: {len(connected_clients)})')

@socketio.on('request_simulation_start')
def handle_start_request():
    """Handle start request via WebSocket"""
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
    """Handle stop request via WebSocket"""
    global simulation_running
    
    if simulation_running:
        print("\n⏹️  Stopping simulation via WebSocket...")
        simulation_running = False
        emit('simulation_stopped', {'message': 'Simulation stopping'}, broadcast=True)
    else:
        emit('error', {'message': 'Simulation not running'})

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 AMBULANCE ROUTING BACKEND READY")
    print("="*80)
    print("\n📊 Configuration:")
    print(f"   • Hospitals: {len(HOSPITALS)}")
    print(f"   • Validated routes: {ROUTE_DATA['assigned_routes']}")
    print(f"   • Min vehicles for spawn: {MIN_VEHICLES}")
    print("\n🌐 Server:")
    print("   • Backend API: http://localhost:5000")
    print("   • WebSocket: ws://localhost:5000")
    print("\n🚑 Features:")
    print("   • Normal Mode: Red ambulance, stops at red lights")
    print("   • Green Corridor Mode: Green ambulance, ignores red lights")
    print("   • Real-time tracking via WebSocket")
    print("\n⏹️  Press Ctrl+C to stop")
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
        print("\n\n⏹️  Server stopped by user")
        simulation_running = False
        try:
            traci.close()
        except:
            pass
