#!/usr/bin/env python3
"""
Verify All Routes and Get Spawn Positions - Headless
====================================================
Tests all 30 hospital routes automatically
Captures actual spawn positions (lat/lon)
No user interaction, no GUI
"""

import traci
import json
import os
import time
import sys

# Fix paths - look in parent directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PARENT_DIR, 'sumo_data')
SUMO_CONFIG = os.path.join(DATA_DIR, 'simulation.sumocfg')
SUMO_BINARY = 'sumo'  # Headless
INPUT_FILE = os.path.join(DATA_DIR, 'hospital_routes_validated.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'hospital_routes_with_spawn_positions.json')

print("=" * 80)
print("VERIFY ALL ROUTES AND GET SPAWN POSITIONS - HEADLESS")
print("=" * 80)

# Check if files exist
print(f"\n📂 Checking files...")
print(f"   Script dir: {SCRIPT_DIR}")
print(f"   Parent dir: {PARENT_DIR}")
print(f"   Data dir: {DATA_DIR}")
print(f"   Input file: {INPUT_FILE}")

if not os.path.exists(INPUT_FILE):
    print(f"\n❌ Error: Input file not found!")
    print(f"   Looking for: {INPUT_FILE}")
    print(f"\n💡 Please run this script from the correct directory:")
    print(f"   cd {PARENT_DIR}")
    print(f"   python test/verify_and_get_spawn_positions.py")
    sys.exit(1)

if not os.path.exists(SUMO_CONFIG):
    print(f"\n❌ Error: SUMO config not found!")
    print(f"   Looking for: {SUMO_CONFIG}")
    sys.exit(1)

print("   ✅ All files found")

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n📂 Loading route assignments...")
with open(INPUT_FILE, 'r') as f:
    route_data = json.load(f)

total_routes = len(route_data['routes'])
print(f"✅ Loaded {total_routes} route assignments")

# ============================================================================
# VERIFICATION FUNCTION
# ============================================================================

def verify_route_and_get_spawn(route_info, route_index, total):
    """Verify a route and get spawn position"""
    
    source_idx = route_info['source_index']
    dest_idx = route_info['dest_index']
    route_edges = route_info['route_edges']
    spawn_edge = route_info['spawn_edge']
    
    print(f"\n{'='*80}")
    print(f"[{route_index + 1}/{total}] Testing Route: Hospital {source_idx} → {dest_idx}")
    print(f"{'='*80}")
    print(f"   Source: {route_info['source_name']}")
    print(f"   Dest: {route_info['dest_name']}")
    print(f"   Edges: {route_info['edge_count']}")
    print(f"   Spawn edge: {spawn_edge}")
    
    test_vehicle_id = f"test_{int(time.time() * 1000000)}"
    
    try:
        # Add test vehicle
        print(f"\n   🚑 Spawning test vehicle: {test_vehicle_id}")
        traci.vehicle.add(
            vehID=test_vehicle_id,
            routeID='',
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        
        # Set route
        traci.vehicle.setRoute(test_vehicle_id, route_edges)
        
        # Step simulation to let vehicle spawn
        print(f"   ⏳ Stepping simulation...")
        for _ in range(10):
            traci.simulationStep()
        
        # Check if vehicle spawned
        if test_vehicle_id not in traci.vehicle.getIDList():
            print(f"   ❌ FAILED: Vehicle did not spawn")
            return None
        
        # Get spawn position
        print(f"   📍 Getting spawn position...")
        x, y = traci.vehicle.getPosition(test_vehicle_id)
        lon, lat = traci.simulation.convertGeo(x, y)
        
        # Get current road
        current_road = traci.vehicle.getRoadID(test_vehicle_id)
        route_index_pos = traci.vehicle.getRouteIndex(test_vehicle_id)
        
        spawn_position = {
            'lat': round(lat, 7),
            'lon': round(lon, 7),
            'x': round(x, 2),
            'y': round(y, 2),
            'edge': current_road,
            'route_index': route_index_pos
        }
        
        print(f"   ✅ Spawn position captured:")
        print(f"      Lat/Lon: ({spawn_position['lat']}, {spawn_position['lon']})")
        print(f"      SUMO X/Y: ({spawn_position['x']}, {spawn_position['y']})")
        print(f"      Current edge: {current_road}")
        
        # Let vehicle run a bit to verify route works
        print(f"   🔍 Verifying route works...")
        for step in range(50):
            traci.simulationStep()
            
            if test_vehicle_id not in traci.vehicle.getIDList():
                print(f"      ⚠️  Vehicle disappeared at step {step}")
                break
            
            if step == 49:
                route_idx = traci.vehicle.getRouteIndex(test_vehicle_id)
                speed = traci.vehicle.getSpeed(test_vehicle_id) * 3.6
                print(f"      ✅ Vehicle progressing: route index {route_idx}, speed {speed:.1f} km/h")
        
        # Clean up
        if test_vehicle_id in traci.vehicle.getIDList():
            traci.vehicle.remove(test_vehicle_id)
            print(f"   🗑️  Test vehicle removed")
        
        print(f"\n   ✅✅✅ ROUTE VALIDATED ✅✅✅")
        return spawn_position
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up
        try:
            if test_vehicle_id in traci.vehicle.getIDList():
                traci.vehicle.remove(test_vehicle_id)
        except:
            pass
        
        return None

# ============================================================================
# MAIN VERIFICATION LOOP
# ============================================================================

def verify_all_routes():
    """Verify all routes and collect spawn positions"""
    
    print("\n" + "="*80)
    print("STARTING VERIFICATION")
    print("="*80)
    
    # Start SUMO (headless)
    print("\n🚀 Starting SUMO (headless)...")
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
    
    # Initialize simulation
    print("\n⏳ Initializing simulation...")
    for _ in range(20):
        traci.simulationStep()
    print("   ✅ Ready")
    
    # Verify each route
    verified_routes = []
    failed_routes = []
    
    for i, route_info in enumerate(route_data['routes']):
        spawn_position = verify_route_and_get_spawn(route_info, i, total_routes)
        
        if spawn_position:
            # Add spawn position to route info
            route_info['actual_spawn_position'] = spawn_position
            route_info['verification_status'] = 'SUCCESS'
            route_info['verified_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            verified_routes.append(route_info)
        else:
            route_info['verification_status'] = 'FAILED'
            route_info['verified_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            failed_routes.append(route_info)
    
    # Close SUMO
    try:
        traci.close()
        print("\n   SUMO closed")
    except:
        pass
    
    # Save results
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    results = {
        'total_routes': total_routes,
        'verified_routes': len(verified_routes),
        'failed_routes': len(failed_routes),
        'success_rate': (len(verified_routes) / total_routes * 100) if total_routes > 0 else 0,
        'verification_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'routes': verified_routes + failed_routes
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Saved verification results to:")
    print(f"   {OUTPUT_FILE}")
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print(f"Total routes tested: {total_routes}")
    print(f"Successful: {len(verified_routes)} ✅")
    print(f"Failed: {len(failed_routes)} ❌")
    print(f"Success rate: {results['success_rate']:.1f}%")
    
    if verified_routes:
        print("\n📋 Verified Routes with Spawn Positions:")
        for route in verified_routes[:10]:  # Show first 10
            spawn = route['actual_spawn_position']
            print(f"\n   [{route['source_index']} → {route['dest_index']}] {route['source_name'][:30]}")
            print(f"      Spawn: ({spawn['lat']}, {spawn['lon']})")
            print(f"      Edge: {spawn['edge']}")
        
        if len(verified_routes) > 10:
            print(f"\n   ... and {len(verified_routes) - 10} more routes")
    
    if failed_routes:
        print("\n❌ Failed Routes:")
        for route in failed_routes:
            print(f"   [{route['source_index']} → {route['dest_index']}] {route['source_name']} → {route['dest_name']}")
    
    print("\n" + "="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80)

# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    start_time = time.time()
    verify_all_routes()
    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.1f} seconds")
