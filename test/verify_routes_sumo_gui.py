#!/usr/bin/env python3
"""
Verify Routes in SUMO GUI - Visual Verification
===============================================
Spawns ambulances on assigned routes in SUMO GUI
See them spawn at correct positions and travel routes
"""

import traci
import json
import os
import time
import sys

# Fix paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR) == 'test':
    PARENT_DIR = os.path.dirname(SCRIPT_DIR)
else:
    PARENT_DIR = SCRIPT_DIR

DATA_DIR = os.path.join(PARENT_DIR, 'sumo_data')
SUMO_CONFIG = os.path.join(DATA_DIR, 'simulation.sumocfg')
SUMO_GUI = 'sumo-gui'
INPUT_FILE = os.path.join(DATA_DIR, 'hospital_routes_validated.json')

print("=" * 80)
print("VERIFY ROUTES IN SUMO GUI")
print("=" * 80)

# Check files
if not os.path.exists(INPUT_FILE):
    print(f"\n❌ Error: {INPUT_FILE} not found!")
    sys.exit(1)

# Load route data
print("\n📂 Loading route assignments...")
with open(INPUT_FILE, 'r') as f:
    route_data = json.load(f)

print(f"✅ Loaded {len(route_data['routes'])} route assignments")

# Show available routes
print("\n🏥 Available Routes:")
for i, route in enumerate(route_data['routes'][:10]):
    print(f"   {i}. Hospital {route['source_index']} → {route['dest_index']}: "
          f"{route['source_name'][:25]} → {route['dest_name'][:25]}")
print(f"   ... and {len(route_data['routes']) - 10} more routes")

# User selection
print("\n📍 SELECT TEST:")
print("   1. Test specific route (choose hospital pair)")
print("   2. Test all routes sequentially (spawn all ambulances)")
print("   3. Test first 5 routes")
print("\nEnter choice (1/2/3): ", end='')
choice = input().strip()

routes_to_test = []

if choice == '1':
    # Single route
    print("\n📍 Enter source hospital (0-5): ", end='')
    source = int(input().strip())
    print("📍 Enter destination hospital (0-5): ", end='')
    dest = int(input().strip())
    
    # Find route
    for route in route_data['routes']:
        if route['source_index'] == source and route['dest_index'] == dest:
            routes_to_test.append(route)
            break
    
    if not routes_to_test:
        print(f"❌ No route found for {source} → {dest}")
        sys.exit(1)

elif choice == '2':
    # All routes
    routes_to_test = route_data['routes']
    print(f"\n✅ Will test all {len(routes_to_test)} routes")

elif choice == '3':
    # First 5 routes
    routes_to_test = route_data['routes'][:5]
    print(f"\n✅ Will test first 5 routes")

else:
    print("❌ Invalid choice")
    sys.exit(1)

# Mode selection
print("\n🚨 SELECT MODE:")
print("   1. NORMAL MODE - Red ambulances, stop at red lights 🔴")
print("   2. GREEN CORRIDOR - Green ambulances, ignore red lights 🟢")
print("\nEnter choice (1 or 2): ", end='')
mode = input().strip()

if mode not in ['1', '2']:
    print("❌ Invalid choice")
    sys.exit(1)

mode_name = "NORMAL MODE" if mode == '1' else "GREEN CORRIDOR MODE"
print(f"\n✅ Selected: {mode_name}")

# Start SUMO
print("\n🚀 Starting SUMO GUI...")
try:
    traci.start([
        SUMO_GUI,
        '-c', SUMO_CONFIG,
        '--start',
        '--quit-on-end',
        '--step-length', '0.1',
        '--delay', '50'  # Adjust delay for speed
    ])
    print("   ✅ SUMO GUI started")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)

# Wait for traffic
print("\n⏳ Waiting for 100 vehicles...")
step = 0
while True:
    traci.simulationStep()
    step += 1
    vehicle_count = traci.vehicle.getIDCount()
    
    if step % 100 == 0:
        print(f"   Vehicles: {vehicle_count}/100")
    
    if vehicle_count >= 100:
        print(f"   ✅ Ready with {vehicle_count} vehicles")
        break
    
    if step > 10000:
        print(f"   ⚠️  Timeout, proceeding with {vehicle_count} vehicles")
        break

# Spawn ambulances
print("\n" + "="*80)
print(f"SPAWNING {len(routes_to_test)} AMBULANCE(S)")
print("="*80)

spawned_ambulances = []

for i, route_info in enumerate(routes_to_test):
    amb_id = f"ambulance_{route_info['source_index']}_{route_info['dest_index']}_{int(time.time())}"
    route_edges = route_info['route_edges']
    
    print(f"\n[{i+1}/{len(routes_to_test)}] Spawning ambulance: {amb_id}")
    print(f"   Route: Hospital {route_info['source_index']} → {route_info['dest_index']}")
    print(f"   {route_info['source_name'][:30]}")
    print(f"   → {route_info['dest_name'][:30]}")
    print(f"   Edges: {route_info['edge_count']}")
    print(f"   Spawn edge: {route_info['spawn_edge']}")
    
    try:
        # Add vehicle
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
        
        if mode == '1':
            # Normal mode: RED, respects lights
            traci.vehicle.setColor(amb_id, (255, 0, 0, 255))
            traci.vehicle.setMaxSpeed(amb_id, 25)
        else:
            # Green corridor: GREEN, ignores lights
            traci.vehicle.setColor(amb_id, (0, 255, 0, 255))
            traci.vehicle.setSpeedMode(amb_id, 32)
            traci.vehicle.setMaxSpeed(amb_id, 30)
        
        spawned_ambulances.append({
            'id': amb_id,
            'route_info': route_info
        })
        
        print(f"   ✅ Spawned successfully")
        
        # Step a bit to let it spawn
        for _ in range(10):
            traci.simulationStep()
        
        # If testing all routes, add delay between spawns
        if len(routes_to_test) > 1:
            print(f"   ⏳ Waiting 5 seconds before next spawn...")
            for _ in range(50):
                traci.simulationStep()
                time.sleep(0.1)
        
    except Exception as e:
        print(f"   ❌ Failed to spawn: {e}")

# Track ambulances
print("\n" + "="*80)
print(f"TRACKING {len(spawned_ambulances)} AMBULANCE(S)")
print("="*80)
print(f"Mode: {mode_name}")
print("Watch SUMO GUI - Ambulances are moving!")
print("Press Ctrl+C to stop\n")

try:
    last_print = time.time()
    active_ambulances = {amb['id']: amb for amb in spawned_ambulances}
    
    while active_ambulances:
        traci.simulationStep()
        time.sleep(0.02)  # Fast simulation
        
        vehicle_ids = traci.vehicle.getIDList()
        
        # Check which ambulances are still active
        completed = []
        for amb_id in list(active_ambulances.keys()):
            if amb_id not in vehicle_ids:
                completed.append(amb_id)
        
        # Remove completed ambulances
        for amb_id in completed:
            route_info = active_ambulances[amb_id]['route_info']
            print(f"\n🏁 Ambulance completed: Hospital {route_info['source_index']} → {route_info['dest_index']}")
            del active_ambulances[amb_id]
        
        # Print status every 3 seconds
        if time.time() - last_print > 3:
            sim_time = traci.simulation.getTime()
            vehicle_count = traci.vehicle.getIDCount()
            
            print(f"\n[{int(sim_time):4d}s] Total vehicles: {vehicle_count} | Active ambulances: {len(active_ambulances)}")
            
            for amb_id, amb_data in active_ambulances.items():
                try:
                    road = traci.vehicle.getRoadID(amb_id)
                    speed = traci.vehicle.getSpeed(amb_id) * 3.6
                    route_edges = amb_data['route_info']['route_edges']
                    route_index = traci.vehicle.getRouteIndex(amb_id)
                    
                    progress = (route_index + 1) / len(route_edges) * 100
                    route_info = amb_data['route_info']
                    
                    print(f"   {amb_id[-20:]}: [{route_info['source_index']}→{route_info['dest_index']}] "
                          f"{progress:5.1f}% | Speed: {speed:5.1f} km/h | Edge: {road[:20]}")
                    
                except:
                    pass
            
            last_print = time.time()

except KeyboardInterrupt:
    print(f"\n⏹️  Stopped by user")

finally:
    try:
        traci.close()
        print("\n   SUMO closed")
    except:
        pass

print("\n" + "="*80)
print("✅ VERIFICATION COMPLETE")
print("="*80)
print(f"\nYou saw:")
print(f"   • Ambulances spawning at assigned spawn edges")
print(f"   • Ambulances following their routes")
print(f"   • Mode: {mode_name}")
print("="*80)
