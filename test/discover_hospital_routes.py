#!/usr/bin/env python3
"""
Hospital Route Discovery - Fixed Edge Detection
===============================================
Finds edges near hospitals using multiple methods
"""

import traci
import json
import os
import math
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = 'sumo_data'
SUMO_CONFIG = os.path.join(DATA_DIR, 'simulation.sumocfg')
SUMO_BINARY = 'sumo'
OUTPUT_FILE = os.path.join(DATA_DIR, 'hospital_routes_validated.json')

print("=" * 80)
print("HOSPITAL ROUTE DISCOVERY - FIXED EDGE DETECTION")
print("=" * 80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n📂 Loading data...")
with open(os.path.join(DATA_DIR, 'hospitals.json'), 'r') as f:
    HOSPITALS = json.load(f)
    print(f"✅ Loaded {len(HOSPITALS)} hospitals")

print("\n🏥 Hospitals:")
for i, h in enumerate(HOSPITALS):
    print(f"   {i}. {h['name']} - ({h['lat']:.6f}, {h['lon']:.6f})")

# ============================================================================
# IMPROVED EDGE DETECTION
# ============================================================================

def find_edges_near_position(lat, lon, max_distance=100):
    """Find all edges within max_distance of position"""
    print(f"      Finding edges near ({lat:.6f}, {lon:.6f})...")
    
    try:
        # Convert to SUMO coordinates
        x, y = traci.simulation.convertGeo(lon, lat, fromGeo=True)
        
        # Get all edges
        all_edges = traci.edge.getIDList()
        valid_edges = [e for e in all_edges if ':' not in e]  # Skip internal edges
        
        print(f"         Checking {len(valid_edges)} edges...")
        
        nearby_edges = []
        
        for edge_id in valid_edges:
            try:
                # Get edge shape
                edge_shape = traci.edge.getShape(edge_id)
                
                if not edge_shape or len(edge_shape) == 0:
                    continue
                
                # Check distance to edge start point
                edge_x, edge_y = edge_shape[0]
                distance = math.sqrt((x - edge_x)**2 + (y - edge_y)**2)
                
                if distance <= max_distance:
                    nearby_edges.append({
                        'edge_id': edge_id,
                        'distance': distance,
                        'position': (edge_x, edge_y)
                    })
                    
            except:
                continue
        
        # Sort by distance
        nearby_edges.sort(key=lambda e: e['distance'])
        
        if nearby_edges:
            print(f"         ✅ Found {len(nearby_edges)} edges within {max_distance}m")
            for i, edge in enumerate(nearby_edges[:5]):
                print(f"            {i+1}. {edge['edge_id']} ({edge['distance']:.1f}m)")
        else:
            print(f"         ❌ No edges found within {max_distance}m")
        
        return nearby_edges
        
    except Exception as e:
        print(f"         ❌ Error: {e}")
        return []

def find_best_route_between_edges(source_edges, dest_edges):
    """Try routing between source and dest edge lists"""
    print(f"      Trying routing between edge sets...")
    print(f"         Source edges: {len(source_edges)}")
    print(f"         Dest edges: {len(dest_edges)}")
    
    best_route = None
    best_spawn_edge = None
    best_dest_edge = None
    best_length = float('inf')
    
    # Try combinations
    attempts = 0
    max_attempts = min(len(source_edges) * len(dest_edges), 50)  # Limit attempts
    
    for source_edge_data in source_edges[:10]:
        for dest_edge_data in dest_edges[:10]:
            if attempts >= max_attempts:
                break
                
            attempts += 1
            
            source_edge = source_edge_data['edge_id']
            dest_edge = dest_edge_data['edge_id']
            
            try:
                stage = traci.simulation.findRoute(source_edge, dest_edge)
                
                if stage and hasattr(stage, 'edges') and len(stage.edges) > 0:
                    route = list(stage.edges)
                    
                    # Prefer shorter routes
                    if len(route) < best_length and len(route) >= 5:
                        best_route = route
                        best_spawn_edge = source_edge
                        best_dest_edge = dest_edge
                        best_length = len(route)
                        print(f"            ✅ Found route: {source_edge} → {dest_edge} ({len(route)} edges)")
                        
            except:
                continue
    
    if best_route:
        print(f"         ✅ Best route: {best_length} edges")
        return best_route, best_spawn_edge, best_dest_edge
    else:
        print(f"         ❌ No route found after {attempts} attempts")
        return None, None, None

def calculate_route_distance(route):
    """Calculate total distance of a route"""
    try:
        total_distance = 0
        for edge_id in route:
            try:
                length = traci.edge.getLength(edge_id)
                total_distance += length
            except:
                pass
        return total_distance
    except:
        return 0

def get_edge_position(edge_id):
    """Get lat/lon of edge start position"""
    try:
        edge_shape = traci.edge.getShape(edge_id)
        if edge_shape and len(edge_shape) > 0:
            x, y = edge_shape[0]
            lon, lat = traci.simulation.convertGeo(x, y)
            return {'lat': lat, 'lon': lon}
        return None
    except:
        return None

def validate_route(route, spawn_edge):
    """Test if route is valid by spawning test vehicle"""
    test_vehicle_id = f"test_{int(time.time() * 1000000)}"
    
    try:
        traci.vehicle.add(
            vehID=test_vehicle_id,
            routeID='',
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        
        traci.vehicle.setRoute(test_vehicle_id, route)
        
        # Step simulation
        for _ in range(10):
            traci.simulationStep()
        
        # Check if vehicle exists
        if test_vehicle_id in traci.vehicle.getIDList():
            traci.vehicle.remove(test_vehicle_id)
            return True
        
        return False
        
    except Exception as e:
        try:
            if test_vehicle_id in traci.vehicle.getIDList():
                traci.vehicle.remove(test_vehicle_id)
        except:
            pass
        return False

# ============================================================================
# MAIN DISCOVERY
# ============================================================================

def discover_all_routes():
    """Discover routes between all hospital pairs"""
    
    print("\n" + "="*80)
    print("STARTING ROUTE DISCOVERY")
    print("="*80)
    
    # Start SUMO
    print("\n🚀 Starting SUMO...")
    try:
        traci.start([
            SUMO_BINARY,
            '-c', SUMO_CONFIG,
            '--start',
            '--no-warnings',
            '--no-step-log'
        ])
        print("   ✅ SUMO started")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return
    
    # Initialize
    print("\n⏳ Initializing...")
    for _ in range(20):
        traci.simulationStep()
    print("   ✅ Ready")
    
    # Discover routes
    discovered_routes = []
    total_pairs = len(HOSPITALS) * (len(HOSPITALS) - 1)
    current_pair = 0
    
    print("\n" + "="*80)
    print(f"DISCOVERING ROUTES FOR {total_pairs} HOSPITAL PAIRS")
    print("="*80)
    
    for i, source_hospital in enumerate(HOSPITALS):
        for j, dest_hospital in enumerate(HOSPITALS):
            
            if i == j:
                continue
            
            current_pair += 1
            
            print(f"\n{'='*80}")
            print(f"[{current_pair}/{total_pairs}] Hospital {i} → Hospital {j}")
            print(f"{'='*80}")
            print(f"   SOURCE: {source_hospital['name']}")
            print(f"   DEST: {dest_hospital['name']}")
            
            # Find edges near source
            print(f"\n   🔍 Finding edges near SOURCE hospital...")
            source_edges = find_edges_near_position(
                source_hospital['lat'],
                source_hospital['lon'],
                max_distance=150  # Search within 150m
            )
            
            if not source_edges:
                print(f"   ❌ FAILED: No edges near source")
                continue
            
            # Find edges near destination
            print(f"\n   🔍 Finding edges near DESTINATION hospital...")
            dest_edges = find_edges_near_position(
                dest_hospital['lat'],
                dest_hospital['lon'],
                max_distance=150
            )
            
            if not dest_edges:
                print(f"   ❌ FAILED: No edges near destination")
                continue
            
            # Find route
            print(f"\n   🔍 Calculating route...")
            route, spawn_edge, dest_edge = find_best_route_between_edges(
                source_edges,
                dest_edges
            )
            
            if not route:
                print(f"   ❌ FAILED: No route found")
                continue
            
            # Get spawn position (closest edge to source)
            spawn_position = get_edge_position(spawn_edge)
            if not spawn_position:
                print(f"   ❌ FAILED: Cannot get spawn position")
                continue
            
            # Calculate distance from source to spawn
            spawn_dist = source_edges[0]['distance']  # Distance of closest edge
            for edge_data in source_edges:
                if edge_data['edge_id'] == spawn_edge:
                    spawn_dist = edge_data['distance']
                    break
            
            spawn_position['distance_from_hospital'] = round(spawn_dist, 2)
            
            # Calculate route distance
            distance = calculate_route_distance(route)
            
            print(f"\n   🔍 Validating route...")
            is_valid = validate_route(route, spawn_edge)
            
            if is_valid:
                print(f"   ✅✅✅ ROUTE VALIDATED! ✅✅✅")
                
                route_data = {
                    'source_index': i,
                    'dest_index': j,
                    'source_name': source_hospital['name'],
                    'dest_name': dest_hospital['name'],
                    'source_id': source_hospital['id'],
                    'dest_id': dest_hospital['id'],
                    'source_hospital_coords': {
                        'lat': source_hospital['lat'],
                        'lon': source_hospital['lon']
                    },
                    'dest_hospital_coords': {
                        'lat': dest_hospital['lat'],
                        'lon': dest_hospital['lon']
                    },
                    'spawn_position': spawn_position,
                    'route_edges': route,
                    'spawn_edge': spawn_edge,
                    'dest_edge': dest_edge,
                    'edge_count': len(route),
                    'distance_meters': round(distance, 2),
                    'validated': True,
                    'discovery_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                discovered_routes.append(route_data)
                
            else:
                print(f"   ❌ FAILED: Validation failed")
    
    # Close SUMO
    try:
        traci.close()
    except:
        pass
    
    # Save results
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    results = {
        'total_hospitals': len(HOSPITALS),
        'total_possible_routes': total_pairs,
        'discovered_routes': len(discovered_routes),
        'discovery_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'routes': discovered_routes
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Saved {len(discovered_routes)} validated routes to:")
    print(f"   {OUTPUT_FILE}")
    
    # Summary
    print("\n" + "="*80)
    print("DISCOVERY SUMMARY")
    print("="*80)
    print(f"Total hospitals: {len(HOSPITALS)}")
    print(f"Possible routes: {total_pairs}")
    print(f"Valid routes found: {len(discovered_routes)}")
    print(f"Success rate: {len(discovered_routes)/total_pairs*100:.1f}%")
    
    if discovered_routes:
        print("\n📋 Validated Routes:")
        for route in discovered_routes:
            print(f"\n   [{route['source_index']} → {route['dest_index']}] {route['source_name'][:30]}")
            print(f"      → {route['dest_name'][:30]}")
            print(f"      Spawn: {route['spawn_edge']}")
            print(f"      Distance from source: {route['spawn_position']['distance_from_hospital']}m")
            print(f"      Route: {route['edge_count']} edges, {route['distance_meters']}m")
    
    print("\n" + "="*80)
    print("✅ DISCOVERY COMPLETE")
    print("="*80)

# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    discover_all_routes()
