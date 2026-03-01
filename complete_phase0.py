#!/usr/bin/env python3
"""
Complete Phase 0 with Existing OSM and Network Files
======================================================
Extracts: Traffic Lights, Hospitals, Valid Routes
"""

import os
import sys
import json
import xml.etree.ElementTree as ET

# ============================================================================
# CONFIGURATION
# ============================================================================

OSM_DIR = "sumo_data"
OSM_FILE = os.path.join(OSM_DIR, "mumbai_andheri.osm")
NET_FILE = os.path.join(OSM_DIR, "mumbai.net.xml")
TLS_JSON = os.path.join(OSM_DIR, "traffic_lights.json")
HOSPITALS_JSON = os.path.join(OSM_DIR, "hospitals.json")
ROUTES_JSON = os.path.join(OSM_DIR, "valid_routes.json")

print("=" * 80)
print("COMPLETE PHASE 0 - DATA EXTRACTION")
print("=" * 80)

# ============================================================================
# VERIFY FILES EXIST
# ============================================================================

print("\n📂 Checking existing files...")

if not os.path.exists(OSM_FILE):
    print(f"❌ OSM file not found: {OSM_FILE}")
    sys.exit(1)

if not os.path.exists(NET_FILE):
    print(f"❌ Network file not found: {NET_FILE}")
    sys.exit(1)

osm_size = os.path.getsize(OSM_FILE) / 1024
net_size = os.path.getsize(NET_FILE) / 1024

print(f"✅ OSM file: {OSM_FILE} ({osm_size:.1f} KB)")
print(f"✅ Network file: {NET_FILE} ({net_size:.1f} KB)")

# ============================================================================
# STEP 1: EXTRACT TRAFFIC LIGHTS FROM NETWORK
# ============================================================================

def extract_traffic_lights(net_file, output_json):
    """Extract all traffic light junctions from SUMO network"""
    print("\n" + "=" * 80)
    print("STEP 1: Extracting Traffic Lights from Network")
    print("=" * 80)
    
    try:
        print("📊 Parsing network file...")
        tree = ET.parse(net_file)
        root = tree.getroot()
        
        traffic_lights = []
        
        # Find all traffic light junctions
        for junction in root.findall('.//junction[@type="traffic_light"]'):
            tls_id = junction.get('id')
            x = float(junction.get('x'))
            y = float(junction.get('y'))
            
            tls_data = {
                'id': tls_id,
                'x': x,
                'y': y,
                'lat': None,  # Will be computed if sumolib available
                'lon': None,
                'incLanes': junction.get('incLanes', '').split(),
                'shape': junction.get('shape', ''),
                'type': 'traffic_light'
            }
            
            traffic_lights.append(tls_data)
        
        print(f"\n✅ Found {len(traffic_lights)} traffic light junctions")
        
        if len(traffic_lights) == 0:
            print("\n   ⚠️  WARNING: No traffic lights found!")
            print("      Your network might not have traffic signals enabled")
            print("      This is still OK - simulation will work without them")
        
        # Try to convert coordinates to lat/lon
        try:
            import sumolib
            net = sumolib.net.readNet(net_file)
            
            print("🗺️  Converting to lat/lon coordinates...")
            
            for tl in traffic_lights:
                lon, lat = net.convertXY2LonLat(tl['x'], tl['y'])
                tl['lat'] = lat
                tl['lon'] = lon
            
            print("   ✅ Coordinates converted")
        
        except ImportError:
            print("   ⚠️  sumolib not available (pip install eclipse-sumo)")
            print("      Traffic lights will still work, just without lat/lon")
        
        # Save to JSON
        with open(output_json, 'w') as f:
            json.dump(traffic_lights, f, indent=2)
        
        print(f"\n✅ Saved to: {output_json}")
        
        # Show samples
        if len(traffic_lights) > 0:
            print(f"\n📋 Sample Traffic Lights:")
            for tl in traffic_lights[:5]:
                coord_str = f"({tl['lat']:.4f}, {tl['lon']:.4f})" if tl['lat'] else f"({tl['x']:.0f}, {tl['y']:.0f})"
                print(f"   • {tl['id']}: {coord_str}")
        
        return len(traffic_lights) > 0
        
    except Exception as e:
        print(f"\n❌ Failed to extract traffic lights: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# STEP 2: EXTRACT HOSPITALS FROM OSM
# ============================================================================

def extract_hospitals(osm_file, net_file, output_json):
    """Extract hospital locations from OSM and map to network edges"""
    print("\n" + "=" * 80)
    print("STEP 2: Extracting Hospitals from OSM")
    print("=" * 80)
    
    try:
        print("🏥 Parsing OSM file...")
        tree = ET.parse(osm_file)
        root = tree.getroot()
        
        hospitals = []
        
        # Extract all hospitals and clinics
        for node in root.findall('.//node'):
            tags = {tag.get('k'): tag.get('v') for tag in node.findall('tag')}
            
            amenity = tags.get('amenity')
            if amenity in ['hospital', 'clinic', 'doctors']:
                lat = float(node.get('lat'))
                lon = float(node.get('lon'))
                name = tags.get('name', f'{amenity.title()} {len(hospitals) + 1}')
                
                hospital_data = {
                    'id': len(hospitals) + 1,
                    'osm_id': node.get('id'),
                    'name': name,
                    'type': amenity,
                    'lat': lat,
                    'lon': lon,
                    'nearest_edge': None,
                    'sumo_x': None,
                    'sumo_y': None
                }
                
                hospitals.append(hospital_data)
        
        print(f"\n✅ Found {len(hospitals)} medical facilities in OSM")
        
        if len(hospitals) == 0:
            print("\n   ⚠️  No hospitals found in OSM data")
            print("      Creating dummy hospital locations from network...")
            hospitals = create_dummy_hospitals(net_file)
        else:
            # Show what we found
            print("\n📋 Medical Facilities Found:")
            for h in hospitals[:10]:  # Show first 10
                print(f"   • {h['name']} ({h['type']})")
        
        # Map hospitals to SUMO network edges
        print("\n🗺️  Mapping hospitals to SUMO network edges...")
        
        try:
            import sumolib
            net = sumolib.net.readNet(net_file)
            
            mapped_count = 0
            
            for hospital in hospitals:
                # Convert lat/lon to SUMO coordinates
                x, y = net.convertLonLat2XY(hospital['lon'], hospital['lat'])
                hospital['sumo_x'] = x
                hospital['sumo_y'] = y
                
                # Find nearest edge within 500m radius
                edges = net.getNeighboringEdges(x, y, r=500)
                
                if edges:
                    # Get closest edge
                    best_edge, distance = min(edges, key=lambda e: e[1])
                    hospital['nearest_edge'] = best_edge.getID()
                    mapped_count += 1
                    print(f"   ✅ {hospital['name']}: edge {best_edge.getID()} ({distance:.0f}m away)")
                else:
                    print(f"   ⚠️  {hospital['name']}: No nearby edge (might be outside network)")
            
            print(f"\n   Successfully mapped: {mapped_count}/{len(hospitals)} facilities")
            
            # Remove unmapped hospitals
            hospitals = [h for h in hospitals if h['nearest_edge']]
            
            if len(hospitals) == 0:
                print("\n   ⚠️  No hospitals could be mapped to network!")
                print("      Creating dummy hospitals from network edges...")
                hospitals = create_dummy_hospitals(net_file)
        
        except ImportError:
            print("\n   ⚠️  sumolib not installed (pip install eclipse-sumo)")
            print("      Cannot map hospitals to network edges")
            print("      Creating dummy hospitals instead...")
            hospitals = create_dummy_hospitals(net_file)
        
        # Save to JSON
        with open(output_json, 'w') as f:
            json.dump(hospitals, f, indent=2)
        
        print(f"\n✅ Saved {len(hospitals)} hospitals to: {output_json}")
        
        return len(hospitals) > 0
        
    except Exception as e:
        print(f"\n❌ Failed to extract hospitals: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_dummy_hospitals(net_file):
    """Create dummy hospital locations from network edges"""
    print("\n   🏥 Creating dummy hospital locations...")
    
    try:
        import sumolib
        net = sumolib.net.readNet(net_file)
        edges = list(net.getEdges())
        
        if len(edges) == 0:
            print("      ❌ Network has no edges!")
            return []
        
        hospitals = []
        num_hospitals = min(6, len(edges))  # Create up to 6 dummy hospitals
        
        # Distribute evenly across network
        for i in range(num_hospitals):
            idx = (i * len(edges)) // num_hospitals
            edge = edges[idx]
            
            # Get middle point of edge
            shape = edge.getShape()
            mid_idx = len(shape) // 2
            x, y = shape[mid_idx]
            
            # Convert to lat/lon
            lon, lat = net.convertXY2LonLat(x, y)
            
            hospital_data = {
                'id': i + 1,
                'name': f'Emergency Medical Center {chr(65 + i)}',  # A, B, C, ...
                'type': 'emergency',
                'lat': lat,
                'lon': lon,
                'nearest_edge': edge.getID(),
                'sumo_x': x,
                'sumo_y': y,
                'is_dummy': True
            }
            
            hospitals.append(hospital_data)
            print(f"      ✅ Created: {hospital_data['name']} on edge {edge.getID()}")
        
        return hospitals
        
    except Exception as e:
        print(f"      ❌ Failed to create dummy hospitals: {e}")
        return []

# ============================================================================
# STEP 3: COMPUTE VALID ROUTES
# ============================================================================

def compute_valid_routes(net_file, hospitals_file, output_json):
    """Compute all valid routes between hospital pairs"""
    print("\n" + "=" * 80)
    print("STEP 3: Computing Valid Routes Between Hospitals")
    print("=" * 80)
    
    try:
        # Load hospitals
        with open(hospitals_file, 'r') as f:
            hospitals = json.load(f)
        
        print(f"🏥 Loaded {len(hospitals)} hospitals")
        
        if len(hospitals) < 2:
            print("   ❌ Need at least 2 hospitals for routes!")
            return False
        
        # Check if sumolib is available
        try:
            import sumolib
        except ImportError:
            print("\n❌ sumolib is required for route computation!")
            print("   Install with: pip install eclipse-sumo")
            return False
        
        print("🗺️  Loading SUMO network...")
        net = sumolib.net.readNet(net_file)
        
        print(f"🛣️  Computing routes for {len(hospitals) * (len(hospitals) - 1)} hospital pairs...")
        
        valid_routes = []
        failed_routes = []
        
        for i, source in enumerate(hospitals):
            for j, dest in enumerate(hospitals):
                if i == j:
                    continue  # Skip same hospital
                
                source_edge_id = source.get('nearest_edge')
                dest_edge_id = dest.get('nearest_edge')
                
                if not source_edge_id or not dest_edge_id:
                    failed_routes.append(f"{source['name']} → {dest['name']}: Missing edge mapping")
                    continue
                
                try:
                    source_edge = net.getEdge(source_edge_id)
                    dest_edge = net.getEdge(dest_edge_id)
                    
                    # Compute optimal path (Dijkstra)
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
                        avg_speed_ms = sum(e.getSpeed() for e in edges) / len(edges)
                        est_time_s = distance_m / avg_speed_ms if avg_speed_ms > 0 else 0
                        
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
                            'distance_km': round(distance_m / 1000, 2),
                            'estimated_time_s': round(est_time_s, 2),
                            'estimated_time_min': round(est_time_s / 60, 2),
                            'traffic_lights_count': tls_count,
                            'avg_speed_kmh': round(avg_speed_ms * 3.6, 2)
                        }
                        
                        valid_routes.append(route_data)
                        
                        print(f"   ✅ Route {len(valid_routes)}: {source['name']} → {dest['name']}")
                        print(f"      Distance: {distance_m:.0f}m, Time: ~{est_time_s/60:.1f}min, Signals: {tls_count}")
                    
                    else:
                        failed_routes.append(f"{source['name']} → {dest['name']}: No path exists")
                        print(f"   ❌ No route: {source['name']} → {dest['name']}")
                
                except Exception as e:
                    failed_routes.append(f"{source['name']} → {dest['name']}: {str(e)}")
                    print(f"   ❌ Error: {source['name']} → {dest['name']}")
        
        # Save results
        with open(output_json, 'w') as f:
            json.dump(valid_routes, f, indent=2)
        
        print("\n" + "=" * 80)
        print("ROUTE COMPUTATION COMPLETE")
        print("=" * 80)
        
        print(f"\n📊 Statistics:")
        print(f"   Total hospital pairs: {len(hospitals) * (len(hospitals) - 1)}")
        print(f"   Valid routes found: {len(valid_routes)}")
        print(f"   Failed routes: {len(failed_routes)}")
        
        if len(valid_routes) == 0:
            print("\n   ❌ ERROR: No valid routes found!")
            print("      Possible reasons:")
            print("      • Network is disconnected (has isolated components)")
            print("      • Hospitals are on edges that don't connect")
            return False
        
        print(f"\n✅ Saved to: {output_json}")
        
        # Show sample routes
        print(f"\n📋 Sample Routes:")
        for route in valid_routes[:5]:
            print(f"\n   Route {route['id']}:")
            print(f"      {route['source_hospital']} → {route['dest_hospital']}")
            print(f"      Distance: {route['distance_km']}km ({route['estimated_time_min']:.1f}min)")
            print(f"      Traffic Lights: {route['traffic_lights_count']}")
            print(f"      Edges: {route['num_edges']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to compute routes: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    
    success = True
    
    # Step 1: Extract traffic lights
    if not extract_traffic_lights(NET_FILE, TLS_JSON):
        print("\n⚠️  Step 1 had issues, but continuing...")
    
    # Step 2: Extract hospitals
    if not extract_hospitals(OSM_FILE, NET_FILE, HOSPITALS_JSON):
        print("\n❌ Step 2 failed - cannot continue")
        success = False
    
    # Step 3: Compute routes (only if we have hospitals)
    if success and os.path.exists(HOSPITALS_JSON):
        if not compute_valid_routes(NET_FILE, HOSPITALS_JSON, ROUTES_JSON):
            print("\n⚠️  Step 3 had issues")
            success = False
    
    # Final summary
    print("\n" + "=" * 80)
    
    if success:
        print("✅✅✅ PHASE 0 COMPLETE ✅✅✅")
        print("=" * 80)
        
        print("\n📁 Generated Files:")
        for filename in [TLS_JSON, HOSPITALS_JSON, ROUTES_JSON]:
            if os.path.exists(filename):
                size = os.path.getsize(filename) / 1024
                with open(filename, 'r') as f:
                    count = len(json.load(f))
                print(f"   ✅ {filename} ({size:.1f} KB, {count} items)")
        
        print("\n🔍 Verify in SUMO-GUI:")
        print(f"   > sumo-gui {NET_FILE}")
        print("   Look for roads and traffic lights")
        
        print("\n📊 Quality Check:")
        with open(TLS_JSON, 'r') as f:
            tls_count = len(json.load(f))
        with open(HOSPITALS_JSON, 'r') as f:
            hosp_count = len(json.load(f))
        with open(ROUTES_JSON, 'r') as f:
            route_count = len(json.load(f))
        
        print(f"   Traffic Lights: {tls_count}")
        print(f"   Hospitals: {hosp_count}")
        print(f"   Valid Routes: {route_count}")
        
        if tls_count >= 10 and route_count >= 6:
            print("\n   ✅ EXCELLENT QUALITY - Ready for Phase 1!")
        elif tls_count >= 5 and route_count >= 4:
            print("\n   ✅ GOOD QUALITY - Ready for Phase 1!")
        else:
            print("\n   ⚠️  FAIR QUALITY - Will work but consider improving")
        
        print("\n➡️  Next: Start Phase 1 (Web Visualization)")
        print("   Install dependencies: pip install flask flask-socketio flask-cors")
        print("   Then I'll provide phase1_backend.py")
        print("=" * 80)
    
    else:
        print("❌ PHASE 0 INCOMPLETE - Fix errors above")
        print("=" * 80)
        sys.exit(1)
