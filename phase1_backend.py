#!/usr/bin/env python3
"""
PHASE 1 - Backend Server for Green Corridor Web Visualization
==============================================================
Provides REST API and WebSocket for real-time data streaming
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import os
import sys

# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'green-corridor-mumbai-2025'

# Enable CORS for React frontend
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize SocketIO with CORS
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)

# Data directory
DATA_DIR = 'sumo_data'

print("=" * 80)
print("GREEN CORRIDOR - PHASE 1 BACKEND SERVER")
print("=" * 80)

# ============================================================================
# VERIFY DATA FILES
# ============================================================================

required_files = {
    'network': os.path.join(DATA_DIR, 'mumbai.net.xml'),
    'traffic_lights': os.path.join(DATA_DIR, 'traffic_lights.json'),
    'hospitals': os.path.join(DATA_DIR, 'hospitals.json'),
    'valid_routes': os.path.join(DATA_DIR, 'valid_routes.json')
}

print("\n📂 Checking data files...")
all_files_exist = True

for name, path in required_files.items():
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024
        print(f"   ✅ {name}: {path} ({size:.1f} KB)")
    else:
        print(f"   ❌ {name}: MISSING - {path}")
        all_files_exist = False

if not all_files_exist:
    print("\n❌ Missing required files! Run complete_phase0.py first")
    sys.exit(1)

# Load JSON data into memory for fast access
print("\n📊 Loading data into memory...")

with open(required_files['traffic_lights'], 'r') as f:
    TRAFFIC_LIGHTS = json.load(f)
    print(f"   ✅ Loaded {len(TRAFFIC_LIGHTS)} traffic lights")

with open(required_files['hospitals'], 'r') as f:
    HOSPITALS = json.load(f)
    print(f"   ✅ Loaded {len(HOSPITALS)} hospitals")

with open(required_files['valid_routes'], 'r') as f:
    VALID_ROUTES = json.load(f)
    print(f"   ✅ Loaded {len(VALID_ROUTES)} valid routes")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def convert_network_to_geojson():
    """
    Convert SUMO network to GeoJSON for web map display
    This runs once at startup to avoid repeated parsing
    """
    print("\n🗺️  Converting SUMO network to GeoJSON...")
    
    try:
        import sumolib
        net = sumolib.net.readNet(required_files['network'])
        
        features = []
        
        # Convert edges (roads) to GeoJSON LineStrings
        edge_count = 0
        for edge in net.getEdges():
            shape = edge.getShape()
            
            # Convert SUMO coordinates to lat/lon
            coordinates = []
            for x, y in shape:
                lon, lat = net.convertXY2LonLat(x, y)
                coordinates.append([lon, lat])
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "properties": {
                    "edge_id": edge.getID(),
                    "name": edge.getName() or "Unnamed Road",
                    "speed_limit": round(edge.getSpeed() * 3.6, 1),  # m/s to km/h
                    "lanes": edge.getLaneNumber(),
                    "length": round(edge.getLength(), 1)
                }
            }
            
            features.append(feature)
            edge_count += 1
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        print(f"   ✅ Converted {edge_count} road edges to GeoJSON")
        
        return geojson
    
    except Exception as e:
        print(f"   ❌ Failed to convert network: {e}")
        return {"type": "FeatureCollection", "features": []}

# Pre-compute GeoJSON at startup
NETWORK_GEOJSON = convert_network_to_geojson()

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Root endpoint - API info"""
    return jsonify({
        'name': 'Green Corridor Backend API',
        'version': '1.0',
        'phase': 1,
        'status': 'running',
        'endpoints': {
            'network': '/api/network',
            'traffic_lights': '/api/traffic-lights',
            'hospitals': '/api/hospitals',
            'routes': '/api/routes',
            'stats': '/api/stats'
        }
    })

@app.route('/api/network', methods=['GET'])
def get_network():
    """
    GET /api/network
    Returns: GeoJSON of road network for map display
    """
    return jsonify(NETWORK_GEOJSON)

@app.route('/api/traffic-lights', methods=['GET'])
def get_traffic_lights():
    """
    GET /api/traffic-lights
    Returns: Array of traffic light positions with lat/lon
    """
    return jsonify(TRAFFIC_LIGHTS)

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    """
    GET /api/hospitals
    Returns: Array of hospital locations
    """
    return jsonify(HOSPITALS)

@app.route('/api/routes', methods=['GET'])
def get_routes():
    """
    GET /api/routes
    Optional query params:
    - source_id: Filter routes from specific hospital
    - dest_id: Filter routes to specific hospital
    
    Returns: Array of valid ambulance routes
    """
    source_id = request.args.get('source_id', type=int)
    dest_id = request.args.get('dest_id', type=int)
    
    routes = VALID_ROUTES
    
    if source_id:
        routes = [r for r in routes if r['source_id'] == source_id]
    
    if dest_id:
        routes = [r for r in routes if r['dest_id'] == dest_id]
    
    return jsonify(routes)

@app.route('/api/routes/<int:route_id>', methods=['GET'])
def get_route_by_id(route_id):
    """
    GET /api/routes/{route_id}
    Returns: Single route details
    """
    route = next((r for r in VALID_ROUTES if r['id'] == route_id), None)
    
    if route:
        return jsonify(route)
    else:
        return jsonify({'error': 'Route not found'}), 404

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    GET /api/stats
    Returns: Network statistics
    """
    stats = {
        'network': {
            'roads': len(NETWORK_GEOJSON['features']),
            'file_size_kb': round(os.path.getsize(required_files['network']) / 1024, 1)
        },
        'traffic_lights': {
            'count': len(TRAFFIC_LIGHTS)
        },
        'hospitals': {
            'count': len(HOSPITALS),
            'dummy_count': sum(1 for h in HOSPITALS if h.get('is_dummy', False))
        },
        'routes': {
            'count': len(VALID_ROUTES),
            'avg_distance_km': round(sum(r['distance_km'] for r in VALID_ROUTES) / len(VALID_ROUTES), 2),
            'avg_duration_min': round(sum(r['estimated_time_min'] for r in VALID_ROUTES) / len(VALID_ROUTES), 2),
            'total_traffic_lights': sum(r['traffic_lights_count'] for r in VALID_ROUTES)
        }
    }
    
    return jsonify(stats)

# ============================================================================
# WEBSOCKET HANDLERS (For Phase 2+)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Client connected to WebSocket"""
    print(f'✅ Client connected: {request.sid}')
    
    emit('connection_response', {
        'status': 'connected',
        'phase': 1,
        'message': 'Connected to Green Corridor Backend'
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print(f'❌ Client disconnected: {request.sid}')

@socketio.on('request_data')
def handle_data_request(data):
    """Handle data requests from frontend"""
    data_type = data.get('type', 'unknown')
    
    print(f'📡 Data request: {data_type} from {request.sid}')
    
    if data_type == 'traffic_lights':
        emit('traffic_lights_data', TRAFFIC_LIGHTS)
    
    elif data_type == 'hospitals':
        emit('hospitals_data', HOSPITALS)
    
    elif data_type == 'routes':
        emit('routes_data', VALID_ROUTES)
    
    else:
        emit('error', {'message': f'Unknown data type: {data_type}'})

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🚀 STARTING BACKEND SERVER")
    print("=" * 80)
    print("\n📍 Backend URL: http://localhost:5000")
    print("📍 API Docs: http://localhost:5000/")
    print("📍 Network Data: http://localhost:5000/api/network")
    print("\n🔌 WebSocket: ws://localhost:5000")
    print("\n💡 Frontend should connect to: http://localhost:5000")
    print("\n⏹️  Press Ctrl+C to stop server")
    print("=" * 80 + "\n")
    
    # Run with eventlet for WebSocket support
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to avoid double execution
    )
