#!/usr/bin/env python3
"""
PHASE 2 - Continuous High-Density Traffic Generator (Fixed)
============================================================
Creates continuous flowing traffic - Compatible with all SUMO versions
"""

import os
import sys
import subprocess
import xml.etree.ElementTree as ET

# ============================================================================
# CONFIGURATION
# ============================================================================

SUMO_HOME = os.environ.get('SUMO_HOME', r'C:\SUMO\sumo-1.25.0')
DATA_DIR = 'sumo_data'

NET_FILE = os.path.join(DATA_DIR, 'mumbai.net.xml')
ROUTES_FILE = os.path.join(DATA_DIR, 'traffic.rou.xml')

# CONTINUOUS TRAFFIC PARAMETERS
SIMULATION_END = 36000  # 10 hours (effectively continuous)

print("=" * 80)
print("PHASE 2 - CONTINUOUS HIGH-DENSITY TRAFFIC")
print("=" * 80)
print(f"\n🚗 Creating continuous traffic flows")
print(f"⏱️  Simulation: {SIMULATION_END}s ({SIMULATION_END/3600:.1f} hours)")
print(f"🔄 Traffic regenerates continuously")

# ============================================================================
# LOAD NETWORK AND ANALYZE EDGES
# ============================================================================

print("\n📊 Analyzing network...")

try:
    import sumolib
    net = sumolib.net.readNet(NET_FILE)
    
    edges = list(net.getEdges())
    print(f"   Total edges: {len(edges)}")
    
    # Filter edges suitable for traffic
    suitable_edges = []
    for edge in edges:
        # Check if edge allows vehicles (not pedestrian-only)
        # Use simple length filter - edges over 100m are usually roads
        if edge.getLength() >= 100:
            # Check if not a pedestrian way or footpath
            edge_id = edge.getID()
            if not any(x in edge_id.lower() for x in ['footway', 'path', 'steps', 'pedestrian']):
                suitable_edges.append(edge)
    
    print(f"   Suitable edges for traffic: {len(suitable_edges)}")
    
    if len(suitable_edges) < 50:
        print("   ⚠️  Few suitable edges, using all edges")
        suitable_edges = edges
    
except Exception as e:
    print(f"❌ Failed to analyze network: {e}")
    sys.exit(1)

# ============================================================================
# CREATE CONTINUOUS TRAFFIC FLOWS
# ============================================================================

print("\n" + "=" * 80)
print("CREATING CONTINUOUS TRAFFIC FLOWS")
print("=" * 80)

# Vehicle type definitions
vehicle_types = {
    'car': {
        'vClass': 'passenger',
        'color': '1,0,0',
        'shape': 'passenger',
        'probability': 0.60,
        'speedFactor': 'normc(1.0,0.1,0.8,1.2)',
        'maxSpeed': '50',
        'length': '4.5'
    },
    'taxi': {
        'vClass': 'taxi',
        'color': '1,1,0',
        'shape': 'taxi',
        'probability': 0.15,
        'speedFactor': 'normc(1.0,0.1,0.8,1.2)',
        'maxSpeed': '45',
        'length': '4.3'
    },
    'bus': {
        'vClass': 'bus',
        'color': '0,0,1',
        'shape': 'bus',
        'probability': 0.10,
        'speedFactor': 'normc(0.9,0.1,0.7,1.1)',
        'maxSpeed': '40',
        'length': '12.0'
    },
    'truck': {
        'vClass': 'delivery',
        'color': '0.5,0.5,0.5',
        'shape': 'truck',
        'probability': 0.10,
        'speedFactor': 'normc(0.85,0.1,0.7,1.0)',
        'maxSpeed': '35',
        'length': '7.5'
    },
    'motorcycle': {
        'vClass': 'motorcycle',
        'color': '0,1,0',
        'shape': 'motorcycle',
        'probability': 0.05,
        'speedFactor': 'normc(1.1,0.1,0.9,1.3)',
        'maxSpeed': '60',
        'length': '2.2'
    }
}

# Build XML
root = ET.Element('routes')
root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

# Add vehicle types
print("\n🚗 Adding vehicle type definitions...")
for vtype_id, props in vehicle_types.items():
    vtype = ET.SubElement(root, 'vType')
    vtype.set('id', vtype_id)
    vtype.set('vClass', props['vClass'])
    vtype.set('color', props['color'])
    vtype.set('guiShape', props['shape'])
    vtype.set('speedFactor', props['speedFactor'])
    vtype.set('maxSpeed', props['maxSpeed'])
    vtype.set('length', props['length'])
    vtype.set('accel', '2.6')
    vtype.set('decel', '4.5')
    vtype.set('sigma', '0.5')

print(f"   ✅ Added {len(vehicle_types)} vehicle types")

# Create flow definitions
print("\n🔄 Creating continuous traffic flows...")

import random
random.seed(42)  # Reproducible

# Select random edges for flow origins
num_flows = min(300, len(suitable_edges))  # Up to 300 flows
flow_edges = random.sample(suitable_edges, num_flows)

flow_count = 0
total_vph = 0  # Vehicles per hour
route_cache = {}  # Cache routes to avoid recomputation

for idx, edge in enumerate(flow_edges):
    # Get random destination edge (far from origin)
    dest_candidates = [e for e in suitable_edges if abs(suitable_edges.index(e) - suitable_edges.index(edge)) > 10]
    
    if not dest_candidates:
        dest_candidates = suitable_edges
    
    dest_edge = random.choice(dest_candidates)
    
    # Skip if same edge
    if edge.getID() == dest_edge.getID():
        continue
    
    # Try to find route
    try:
        # Check cache first
        cache_key = f"{edge.getID()}_{dest_edge.getID()}"
        
        if cache_key in route_cache:
            edge_ids = route_cache[cache_key]
        else:
            route_result = net.getOptimalPath(edge, dest_edge)
            
            if route_result and route_result[0]:
                edge_ids = [e.getID() for e in route_result[0]]
                route_cache[cache_key] = edge_ids
            else:
                continue
        
        # Create route
        route_id = f"route_{flow_count}"
        route = ET.SubElement(root, 'route')
        route.set('id', route_id)
        route.set('edges', ' '.join(edge_ids))
        
        # Create flow for each vehicle type (weighted by probability)
        for vtype_id, props in vehicle_types.items():
            if random.random() < props['probability']:
                flow_id = f"flow_{flow_count}_{vtype_id}"
                flow = ET.SubElement(root, 'flow')
                flow.set('id', flow_id)
                flow.set('type', vtype_id)
                flow.set('route', route_id)
                flow.set('begin', '0')
                flow.set('end', str(SIMULATION_END))
                
                # Random flow rate between 80-200 veh/hour
                vph = random.randint(80, 200)
                
                flow.set('vehsPerHour', str(vph))
                flow.set('departSpeed', 'max')
                flow.set('departLane', 'best')
                
                flow_count += 1
                total_vph += vph
        
    except Exception as e:
        # Skip problematic routes
        continue
    
    # Progress indicator
    if (idx + 1) % 50 == 0:
        print(f"   Progress: {idx + 1}/{num_flows} edges processed, {flow_count} flows created...")

print(f"\n✅ Created {flow_count} continuous traffic flows")

if flow_count == 0:
    print("❌ No flows created! Network might be disconnected")
    sys.exit(1)

expected_vehicles = int(total_vph * 0.03)  # Approx 3% of hourly throughput on road
print(f"   Expected vehicles on road: ~{expected_vehicles} at any time")
print(f"   Total throughput: {total_vph} vehicles/hour")

# ============================================================================
# SAVE ROUTES FILE
# ============================================================================

print("\n💾 Writing routes file...")

tree = ET.ElementTree(root)
ET.indent(tree, space="    ")

with open(ROUTES_FILE, 'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(f, encoding='utf-8', xml_declaration=False)

file_size = os.path.getsize(ROUTES_FILE) / 1024
print(f"   ✅ Saved: {ROUTES_FILE} ({file_size:.1f} KB)")

# ============================================================================
# UPDATE SIMULATION CONFIG
# ============================================================================

print("\n⚙️  Updating simulation configuration...")

sumocfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    
    <input>
        <net-file value="mumbai.net.xml"/>
        <route-files value="traffic.rou.xml"/>
    </input>

    <time>
        <begin value="0"/>
        <end value="{SIMULATION_END}"/>
        <step-length value="1"/>
    </time>

    <processing>
        <time-to-teleport value="-1"/>
        <max-depart-delay value="900"/>
        <routing-algorithm value="dijkstra"/>
        <lateral-resolution value="0.8"/>
    </processing>

    <report>
        <verbose value="false"/>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>

</configuration>
"""

sumocfg_path = os.path.join(DATA_DIR, 'simulation.sumocfg')
with open(sumocfg_path, 'w') as f:
    f.write(sumocfg_content)

print(f"   ✅ Updated: {sumocfg_path}")

# ============================================================================
# SUCCESS
# ============================================================================

print("\n" + "=" * 80)
print("✅✅✅ CONTINUOUS HIGH-DENSITY TRAFFIC READY ✅✅✅")
print("=" * 80)

print("\n📁 Generated Files:")
print(f"   ✅ {ROUTES_FILE}")
print(f"   ✅ {sumocfg_path}")

print("\n📊 Traffic Configuration:")
print(f"   Flows: {flow_count}")
print(f"   Throughput: {total_vph} vehicles/hour")
print(f"   Expected on road: ~{expected_vehicles} vehicles simultaneously")
print(f"   Simulation: {SIMULATION_END}s ({SIMULATION_END/3600:.1f} hours)")
print(f"   Vehicle mix: Cars 60%, Taxis 15%, Buses 10%, Trucks 10%, Motorcycles 5%")

print("\n🔍 Test in SUMO-GUI:")
print(f"   > sumo-gui -c {sumocfg_path}")
print("\n   Click Play ▶️ and watch continuous traffic flow!")
print("   Use View -> Viewport to zoom and pan")
print("   Use Time -> Delay to control simulation speed")

print("\n💡 Tips:")
print("   • If traffic looks sparse, re-run with higher num_flows (line 115)")
print("   • Simulation runs for 10 hours - plenty of time!")
print("   • Traffic flows continuously until you stop it")

print("\n➡️  Next: Update backend for real-time web streaming")
print("=" * 80)
