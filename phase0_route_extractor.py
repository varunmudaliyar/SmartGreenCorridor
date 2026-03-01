#!/usr/bin/env python3
"""
GREEN CORRIDOR - Phase 0 Part 2: Valid Route Extraction
=========================================================
Computes all possible hospital-to-hospital routes
Pre-calculates paths to avoid runtime routing failures

WHY: 
- SUMO routing can fail during simulation
- Pre-computed routes guarantee ambulance can reach destination
- Allows frontend to show only valid route combinations

OUTPUT: valid_routes.json with all hospital pairs that have valid paths
"""

import os
import sys
import json

try:
    import sumolib
except ImportError:
    print("❌ sumolib not installed!")
    print("   Install with: pip install eclipse-sumo")
    sys.exit(1)

# Configuration
SUMO_DIR = "sumo_data"
NET_FILE = os.path.join(SUMO_DIR, "mumbai.net.xml")
HOSPITALS_FILE = os.path.join(SUMO_DIR, "hospitals.json")
OUTPUT_FILE = os.path.join(SUMO_DIR, "valid_routes.json")

print("=" * 80)
print("PHASE 0 PART 2: VALID ROUTE EXTRACTION")
print("=" * 80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n📂 Loading network and hospitals...")

try:
    net = sumolib.net.readNet(NET_FILE)
    print(f"   ✅ Network loaded: {len(list(net.getEdges()))} edges")
    
    with open(HOSPITALS_FILE, 'r') as f:
        hospitals = json.load(f)
    print(f"   ✅ Hospitals loaded: {len(hospitals)}")
    
except Exception as e:
    print(f"   ❌ Failed to load data: {e}")
    sys.exit(1)

# ============================================================================
# COMPUTE VALID ROUTES
# ============================================================================

print("\n🛣️  Computing valid routes between all hospital pairs...")
print("   (This checks which routes are actually possible)")

valid_routes = []
failed_routes = []

for i, source in enumerate(hospitals):
    for j, dest in enumerate(hospitals):
        if i == j:
            continue  # Skip same hospital
        
        # Get edges
        source_edge_id = source.get('nearest_edge')
        dest_edge_id = dest.get('nearest_edge')
        
        if not source_edge_id or not dest_edge_id:
            print(f"   ⚠️  Skipping {source['name']} → {dest['name']}: No edge mapping")
            continue
        
        try:
            source_edge = net.getEdge(source_edge_id)
            dest_edge = net.getEdge(dest_edge_id)
            
            # Find route using Dijkstra
            route = net.getOptimalPath(
                source_edge,
                dest_edge,
                vClass='emergency'  # Emergency vehicles can use more roads
            )
            
            if route and route[0]:  # route[0] is list of edges
                edges = route[0]
                edge_ids = [e.getID() for e in edges]
                
                # Calculate metrics
                distance_m = sum(e.getLength() for e in edges)
                avg_speed = sum(e.getSpeed() for e in edges) / len(edges)
                est_time_s = distance_m / avg_speed
                
                # Count traffic lights on route
                tls_count = 0
                for edge in edges:
                    to_node = edge.getToNode()
                    if to_node.getType() == 'traffic_light':
                        tls_count += 1
                
                route_data = {
                    'id': len(valid_routes) + 1,
                    'source_hospital': source['name'],
                    'dest_hospital': dest['name'],
                    'source_id': source['id'],
                    'dest_id': dest['id'],
                    'source_edge': source_edge_id,
                    'dest_edge': dest_edge_id,
                    'edges': edge_ids,
                    'num_edges': len(edge_ids),
                    'distance_m': round(distance_m, 2),
                    'estimated_time_s': round(est_time_s, 2),
                    'estimated_time_min': round(est_time_s / 60, 2),
                    'traffic_lights_count': tls_count,
                    'avg_speed_kmh': round(avg_speed * 3.6, 2)
                }
                
                valid_routes.append(route_data)
                
                print(f"   ✅ Route {len(valid_routes)}: {source['name']} → {dest['name']}")
                print(f"      Distance: {distance_m:.0f}m, Time: {est_time_s/60:.1f}min, TLS: {tls_count}")
            
            else:
                failed_routes.append(f"{source['name']} → {dest['name']}")
                print(f"   ❌ No path: {source['name']} → {dest['name']}")
        
        except Exception as e:
            failed_routes.append(f"{source['name']} → {dest['name']}: {str(e)}")
            print(f"   ❌ Error: {source['name']} → {dest['name']}: {e}")

# ============================================================================
# SAVE RESULTS
# ============================================================================

print("\n" + "=" * 80)
print("ROUTE EXTRACTION COMPLETE")
print("=" * 80)

print(f"\n📊 Statistics:")
print(f"   Total hospitals: {len(hospitals)}")
print(f"   Possible pairs: {len(hospitals) * (len(hospitals) - 1)}")
print(f"   Valid routes: {len(valid_routes)}")
print(f"   Failed routes: {len(failed_routes)}")

if len(valid_routes) == 0:
    print("\n❌ ERROR: No valid routes found!")
    print("   Possible reasons:")
    print("   • Hospitals are outside the network boundary")
    print("   • Network is disconnected (has isolated components)")
    print("   • Bounding box is too small")
    sys.exit(1)

# Save valid routes
with open(OUTPUT_FILE, 'w') as f:
    json.dump(valid_routes, f, indent=2)

print(f"\n✅ Valid routes saved to: {OUTPUT_FILE}")

print("\n📋 Sample Routes:")
for route in valid_routes[:5]:
    print(f"\n   Route {route['id']}:")
    print(f"      {route['source_hospital']} → {route['dest_hospital']}")
    print(f"      Distance: {route['distance_m']}m ({route['estimated_time_min']}min)")
    print(f"      Traffic Lights: {route['traffic_lights_count']}")
    print(f"      Edges: {route['num_edges']}")

print("\n" + "=" * 80)
print("✅✅✅ PHASE 0 FULLY COMPLETE ✅✅✅")
print("=" * 80)
print("\n📁 All required files generated:")
print("   ✅ mumbai.net.xml - SUMO network")
print("   ✅ traffic_lights.json - TLS coordinates")
print("   ✅ hospitals.json - Valid endpoints")
print("   ✅ valid_routes.json - Pre-computed paths")

print("\n➡️  Next: Start Phase 1 (Web Visualization)")
print("   Run: python phase1_backend.py")
print("=" * 80)
