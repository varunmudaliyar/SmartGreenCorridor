#!/usr/bin/env python3
"""
Test Ambulance Routing in SUMO - Wait for Traffic & Speed Up
============================================================
Waits for 150+ vehicles before spawning ambulance
Runs simulation at faster speed
"""

import traci
import time
import json
import os
import sys
import math

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = 'sumo_data'
SUMO_CONFIG = os.path.join(DATA_DIR, 'simulation.sumocfg')
SUMO_GUI = 'sumo-gui'

MIN_VEHICLES = 10  # Wait for this many vehicles
SIMULATION_SPEED = 5  # Speed multiplier (higher = faster)

print("=" * 80)
print("AMBULANCE ROUTING TEST - WAIT FOR TRAFFIC & SPEED UP")
print("=" * 80)
print(f"⚙️  Configuration:")
print(f"   • Minimum vehicles required: {MIN_VEHICLES}")
print(f"   • Simulation speed: {SIMULATION_SPEED}x")
print("=" * 80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n📂 Loading data...")

with open(os.path.join(DATA_DIR, 'hospitals.json'), 'r') as f:
    HOSPITALS = json.load(f)
    print(f"✅ Loaded {len(HOSPITALS)} hospitals")

with open(os.path.join(DATA_DIR, 'valid_routes.json'), 'r') as f:
    VALID_ROUTES = json.load(f)
    print(f"✅ Loaded {len(VALID_ROUTES)} valid routes")

# Display hospitals
print("\n🏥 Available Hospitals:")
for i, h in enumerate(HOSPITALS):
    print(f"   {i}. {h['name']}")
    print(f"      ID: {h['id']}")
    print(f"      Location: ({h['lat']:.6f}, {h['lon']:.6f})")

# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def find_nearest_node(lat, lon):
    """Find nearest junction/node to coordinates"""
    print(f"\n   Finding nearest node to ({lat:.6f}, {lon:.6f})...")
    
    try:
        x, y = traci.simulation.convertGeo(lon, lat, fromGeo=True)
        print(f"      SUMO coords: ({x:.2f}, {y:.2f})")
        
        all_junctions = traci.junction.getIDList()
        print(f"      Searching through {len(all_junctions)} junctions...")
        
        min_distance = float('inf')
        nearest_junction = None
        
        for junction_id in all_junctions:
            try:
                if ':' in junction_id:
                    continue
                
                junc_x, junc_y = traci.junction.getPosition(junction_id)
                distance = math.sqrt((x - junc_x)**2 + (y - junc_y)**2)
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_junction = junction_id
                    
            except:
                continue
        
        if nearest_junction:
            print(f"      ✅ Found junction: {nearest_junction}")
            print(f"         Distance: {min_distance:.1f} meters")
            return nearest_junction, min_distance
        else:
            print(f"      ❌ No junction found")
            return None, None
            
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return None, None

def get_edges_from_junction(junction_id):
    """Get outgoing edges from a junction"""
    try:
        incoming_lanes = traci.junction.getIncoming(junction_id)
        outgoing_lanes = traci.junction.getOutgoing(junction_id)
        
        incoming_edges = list(set([lane.split('_')[0] for lane in incoming_lanes if '_' in lane]))
        outgoing_edges = list(set([lane.split('_')[0] for lane in outgoing_lanes if '_' in lane]))
        
        print(f"      Junction {junction_id}:")
        print(f"         Incoming edges: {len(incoming_edges)}")
        print(f"         Outgoing edges: {len(outgoing_edges)}")
        
        return incoming_edges, outgoing_edges
        
    except Exception as e:
        print(f"      ⚠️  Error getting edges: {e}")
        return [], []

def calculate_route_between_junctions(from_junction, to_junction):
    """Calculate route between two junctions"""
    print(f"\n   Routing between junctions...")
    print(f"      From: {from_junction}")
    print(f"      To: {to_junction}")
    
    try:
        from_edges_in, from_edges_out = get_edges_from_junction(from_junction)
        to_edges_in, to_edges_out = get_edges_from_junction(to_junction)
        
        if not from_edges_out:
            print(f"      ❌ No outgoing edges from source junction")
            return None
        
        if not to_edges_in:
            print(f"      ❌ No incoming edges to destination junction")
            return None
        
        print(f"\n      Trying {len(from_edges_out)} x {len(to_edges_in)} edge combinations...")
        
        best_route = None
        best_length = float('inf')
        
        for from_edge in from_edges_out[:5]:
            for to_edge in to_edges_in[:5]:
                try:
                    stage = traci.simulation.findRoute(from_edge, to_edge)
                    
                    if stage and hasattr(stage, 'edges') and len(stage.edges) > 0:
                        route = list(stage.edges)
                        
                        if len(route) < best_length:
                            best_route = route
                            best_length = len(route)
                            print(f"         ✅ Found route: {from_edge} → {to_edge} ({len(route)} edges)")
                            
                except:
                    continue
        
        if best_route:
            print(f"\n      ✅ Best route: {len(best_route)} edges")
            return best_route
        else:
            print(f"\n      ❌ No route found between junctions")
            return None
            
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return None

def find_route_in_valid_routes_fallback():
    """Use a valid route as fallback"""
    print(f"\n   Using fallback route from precomputed routes...")
    
    if VALID_ROUTES and len(VALID_ROUTES) > 0:
        route = VALID_ROUTES[0]['edges']
        print(f"      ✅ Using route with {len(route)} edges")
        return route
    
    return None

def spawn_ambulance(route, source_hospital, dest_hospital):
    """Spawn ambulance - respects traffic lights"""
    amb_id = f"ambulance_{int(time.time())}"
    
    print(f"\n🚑 Spawning ambulance: {amb_id}")
    print(f"   Route: {source_hospital['name']} → {dest_hospital['name']}")
    print(f"   Edges: {len(route)}")
    print(f"   First 5 edges: {route[:5]}")
    
    try:
        traci.vehicle.add(
            vehID=amb_id,
            routeID='',
            typeID='DEFAULT_VEHTYPE',
            depart='now',
            departLane='best',
            departSpeed='max'
        )
        
        traci.vehicle.setRoute(amb_id, route)
        traci.vehicle.setColor(amb_id, (255, 0, 0, 255))
        
        # Ambulance respects traffic lights
        traci.vehicle.setMaxSpeed(amb_id, 25)
        
        print(f"   ✅ Ambulance spawned - stops at RED lights 🚦")
        return amb_id
        
    except Exception as e:
        print(f"   ❌ Spawn failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def wait_for_vehicles(min_count):
    """Wait until vehicle count reaches minimum threshold"""
    print(f"\n⏳ Waiting for {min_count} vehicles to spawn...")
    print(f"   (This may take a few moments)")
    
    step = 0
    last_print = time.time()
    
    while True:
        traci.simulationStep()
        step += 1
        
        vehicle_count = traci.vehicle.getIDCount()
        
        # Print status every 3 seconds
        if time.time() - last_print > 3:
            sim_time = traci.simulation.getTime()
            print(f"   [{step:5d}] Time: {int(sim_time):4d}s | Vehicles: {vehicle_count:3d}/{min_count}")
            last_print = time.time()
        
        if vehicle_count >= min_count:
            print(f"\n   ✅ Target reached: {vehicle_count} vehicles in simulation!")
            return vehicle_count
        
        # Safety: Stop after 10 minutes
        if step > 36000:
            print(f"\n   ⚠️  Timeout reached with {vehicle_count} vehicles")
            return vehicle_count

def track_ambulance(amb_id, route):
    """Track ambulance progress - FAST"""
    print(f"\n📊 Tracking {amb_id}...")
    print(f"   Watch SUMO GUI - Ambulance is RED colored")
    print(f"   Simulation running at {SIMULATION_SPEED}x speed")
    print(f"   Press Ctrl+C to stop tracking\n")
    
    try:
        step = 0
        last_print = 0
        
        # Calculate sleep time for speed multiplier
        sleep_time = 0.05 / SIMULATION_SPEED
        
        while True:
            traci.simulationStep()
            step += 1
            time.sleep(sleep_time)  # Faster simulation
            
            vehicle_ids = traci.vehicle.getIDList()
            
            if amb_id not in vehicle_ids:
                print(f"\n🏁 Ambulance {amb_id} completed route!")
                break
            
            # Print status every 2 seconds
            if time.time() - last_print > 2:
                try:
                    road = traci.vehicle.getRoadID(amb_id)
                    speed = traci.vehicle.getSpeed(amb_id) * 3.6
                    route_index = traci.vehicle.getRouteIndex(amb_id)
                    sim_time = traci.simulation.getTime()
                    vehicle_count = traci.vehicle.getIDCount()
                    
                    progress = (route_index + 1) / len(route) * 100
                    
                    print(f"   [{int(sim_time):4d}s] Vehicles: {vehicle_count:3d} | Edge: {road:25s} | Speed: {speed:5.1f} km/h | Progress: {route_index+1:3d}/{len(route):3d} ({progress:5.1f}%)")
                    
                    last_print = time.time()
                    
                except Exception as e:
                    pass
                    
    except KeyboardInterrupt:
        print(f"\n⏹️  Tracking stopped by user")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test function"""
    
    print("\n" + "="*80)
    print("STARTING TEST")
    print("="*80)
    
    # User input
    print("\n📍 Select SOURCE hospital (0-{}): ".format(len(HOSPITALS)-1), end='')
    source_idx = int(input().strip())
    
    print("📍 Select DESTINATION hospital (0-{}): ".format(len(HOSPITALS)-1), end='')
    dest_idx = int(input().strip())
    
    if source_idx < 0 or source_idx >= len(HOSPITALS):
        print("❌ Invalid source index")
        return
    
    if dest_idx < 0 or dest_idx >= len(HOSPITALS):
        print("❌ Invalid destination index")
        return
    
    source_hospital = HOSPITALS[source_idx]
    dest_hospital = HOSPITALS[dest_idx]
    
    print("\n" + "="*80)
    print(f"🏥 SOURCE: {source_hospital['name']}")
    print(f"🏥 DESTINATION: {dest_hospital['name']}")
    print("="*80)
    
    # Start SUMO
    print("\n🚀 Starting SUMO GUI...")
    try:
        traci.start([
            SUMO_GUI,
            '-c', SUMO_CONFIG,
            '--start',
            '--quit-on-end',
            '--step-length', '0.1',
            '--delay', str(100 // SIMULATION_SPEED)  # Faster GUI update
        ])
        print("   ✅ SUMO started")
    except Exception as e:
        print(f"   ❌ Failed to start SUMO: {e}")
        return
    
    try:
        # STEP 1: Wait for traffic to build up
        print("\n" + "="*80)
        print(f"STEP 1: WAITING FOR {MIN_VEHICLES}+ VEHICLES")
        print("="*80)
        
        vehicle_count = wait_for_vehicles(MIN_VEHICLES)
        
        # STEP 2: Find nearest junctions
        print("\n" + "="*80)
        print("STEP 2: FINDING NEAREST JUNCTIONS TO HOSPITALS")
        print("="*80)
        
        source_junction, source_dist = find_nearest_node(
            source_hospital['lat'], 
            source_hospital['lon']
        )
        
        dest_junction, dest_dist = find_nearest_node(
            dest_hospital['lat'], 
            dest_hospital['lon']
        )
        
        if not source_junction:
            print("\n❌ Cannot find junction near source hospital")
            return
        
        if not dest_junction:
            print("\n❌ Cannot find junction near destination hospital")
            return
        
        # STEP 3: Calculate route
        print("\n" + "="*80)
        print("STEP 3: CALCULATING ROUTE BETWEEN JUNCTIONS")
        print("="*80)
        
        route = calculate_route_between_junctions(source_junction, dest_junction)
        
        if not route:
            print("\n   ⚠️  Junction routing failed, using fallback...")
            route = find_route_in_valid_routes_fallback()
        
        if not route:
            print("\n❌ No route available")
            return
        
        print(f"\n✅ ROUTE READY: {len(route)} edges")
        
        # STEP 4: Spawn ambulance
        print("\n" + "="*80)
        print("STEP 4: SPAWNING AMBULANCE IN TRAFFIC")
        print("="*80)
        
        amb_id = spawn_ambulance(route, source_hospital, dest_hospital)
        
        if not amb_id:
            print("\n❌ Failed to spawn ambulance")
            return
        
        # STEP 5: Track ambulance
        print("\n" + "="*80)
        print("STEP 5: TRACKING AMBULANCE IN SUMO GUI")
        print("="*80)
        
        track_ambulance(amb_id, route)
        
        print("\n" + "="*80)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test stopped by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            traci.close()
            print("\n   SUMO closed")
        except:
            pass

# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    main()
