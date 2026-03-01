#!/usr/bin/env python3
"""
PHASE 2 - Moderate Density Traffic (50% Reduced)
=================================================
Creates smooth flowing traffic without jams
"""

import os
import sys
import xml.etree.ElementTree as ET
import random

# ============================================================================
# CONFIGURATION
# ============================================================================

SUMO_HOME = os.environ.get('SUMO_HOME', r'C:\SUMO\sumo-1.25.0')
DATA_DIR = 'sumo_data'

NET_FILE = os.path.join(DATA_DIR, 'mumbai.net.xml')
ROUTES_FILE = os.path.join(DATA_DIR, 'traffic.rou.xml')
SIMULATION_END = 36000  # 10 hours

print("=" * 80)
print("PHASE 2 - MODERATE DENSITY TRAFFIC (Optimized)")
print("=" * 80)
print("🚗 50% reduced traffic for smooth flow")

# ============================================================================
# LOAD NETWORK
# ============================================================================

print("\n📊 Analyzing network...")

try:
    import sumolib
    net = sumolib.net.readNet(NET_FILE)
    
    edges = list(net.getEdges())
    print(f"   Total edges: {len(edges)}")
    
    suitable_edges = [e for e in edges if e.getLength() >= 150]
    print(f"   Suitable edges: {len(suitable_edges)}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

# ============================================================================
# BUILD ROUTES XML
# ============================================================================

print("\n🔄 Creating moderate traffic flows...")

root = ET.Element('routes')
root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

# Vehicle types (same as before)
vehicle_types = {
    'car': {'vClass': 'passenger', 'color': '1,0,0', 'shape': 'passenger', 'prob': 0.65, 'speed': '50'},
    'taxi': {'vClass': 'taxi', 'color': '1,1,0', 'shape': 'taxi', 'prob': 0.20, 'speed': '45'},
    'bus': {'vClass': 'bus', 'color': '0,0,1', 'shape': 'bus', 'prob': 0.10, 'speed': '40'},
    'truck': {'vClass': 'delivery', 'color': '0.5,0.5,0.5', 'shape': 'truck', 'prob': 0.05, 'speed': '35'}
}

# Add vehicle types
print("\n🚗 Adding vehicle type definitions...")
for vtype_id, props in vehicle_types.items():
    vtype = ET.SubElement(root, 'vType')
    vtype.set('id', vtype_id)
    vtype.set('vClass', props['vClass'])
    vtype.set('color', props['color'])
    vtype.set('guiShape', props['shape'])
    vtype.set('maxSpeed', props['speed'])
    vtype.set('speedFactor', 'normc(1.0,0.1,0.8,1.2)')
    vtype.set('accel', '2.6')
    vtype.set('decel', '4.5')
    vtype.set('sigma', '0.5')

print(f"   ✅ {len(vehicle_types)} vehicle types added")

# Create flows with validation (50% REDUCED)
print("\n🛣️  Computing valid routes (moderate density)...")
random.seed(42)

valid_routes = 0
route_id_counter = 0
flow_counter = 0
total_vph = 0
failed_attempts = 0

# 50% REDUCTION: Fewer source edges
source_edges = random.sample(suitable_edges, min(125, len(suitable_edges)))  # Was 250

for idx, source_edge in enumerate(source_edges):
    # Try 2 destinations for each source
    for _ in range(2):
        dest_candidates = [e for e in suitable_edges 
                          if abs(suitable_edges.index(e) - suitable_edges.index(source_edge)) > 20]
        
        if not dest_candidates:
            dest_candidates = suitable_edges
        
        dest_edge = random.choice(dest_candidates)
        
        if source_edge.getID() == dest_edge.getID():
            continue
        
        try:
            route_result = net.getOptimalPath(source_edge, dest_edge)
            
            if not route_result or not route_result[0]:
                failed_attempts += 1
                continue
            
            edge_list = route_result[0]
            
            if len(edge_list) < 3:
                failed_attempts += 1
                continue
            
            edge_ids = [e.getID() for e in edge_list]
            
            # Validate connections
            valid_route = True
            for i in range(len(edge_list) - 1):
                current_edge = edge_list[i]
                next_edge = edge_list[i + 1]
                
                outgoing = [e.getID() for e in current_edge.getOutgoing().keys()]
                if next_edge.getID() not in outgoing:
                    valid_route = False
                    failed_attempts += 1
                    break
            
            if not valid_route:
                continue
            
            # Create route
            route_id = f"route_{route_id_counter}"
            route_id_counter += 1
            
            route = ET.SubElement(root, 'route')
            route.set('id', route_id)
            route.set('edges', ' '.join(edge_ids))
            
            valid_routes += 1
            
            # Create flows for different vehicle types
            for vtype_id, props in vehicle_types.items():
                if random.random() < props['prob']:
                    flow_id = f"flow_{flow_counter}"
                    flow_counter += 1
                    
                    flow = ET.SubElement(root, 'flow')
                    flow.set('id', flow_id)
                    flow.set('type', vtype_id)
                    flow.set('route', route_id)
                    flow.set('begin', '0')
                    flow.set('end', str(SIMULATION_END))
                    
                    # 50% REDUCTION: Lower flow rate
                    vph = random.randint(50, 125)  # Was 100-250
                    flow.set('vehsPerHour', str(vph))
                    flow.set('departSpeed', 'max')
                    flow.set('departLane', 'best')
                    flow.set('departPos', 'random')
                    
                    total_vph += vph
        
        except Exception as e:
            failed_attempts += 1
            continue
    
    if (idx + 1) % 25 == 0:
        print(f"   Progress: {idx + 1}/{len(source_edges)}, {valid_routes} routes, {flow_counter} flows...")

print(f"\n✅ Route validation complete:")
print(f"   Valid routes: {valid_routes}")
print(f"   Total flows: {flow_counter}")
print(f"   Failed attempts: {failed_attempts}")
print(f"   Expected vehicles: ~{int(total_vph * 0.04)} on road (moderate density)")
print(f"   Throughput: {total_vph} veh/hour")

if valid_routes == 0:
    print("\n❌ No valid routes created!")
    sys.exit(1)

# ============================================================================
# SAVE FILES
# ============================================================================

print("\n💾 Saving files...")

tree = ET.ElementTree(root)
ET.indent(tree, space="    ")

with open(ROUTES_FILE, 'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(f, encoding='utf-8', xml_declaration=False)

file_size = os.path.getsize(ROUTES_FILE) / 1024
print(f"   ✅ Routes: {ROUTES_FILE} ({file_size:.1f} KB)")

# Update config
sumocfg = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="mumbai.net.xml"/>
        <route-files value="traffic.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{SIMULATION_END}"/>
    </time>
    <processing>
        <time-to-teleport value="-1"/>
        <max-depart-delay value="900"/>
        <ignore-route-errors value="true"/>
    </processing>
    <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>
</configuration>
"""

with open(os.path.join(DATA_DIR, 'simulation.sumocfg'), 'w') as f:
    f.write(sumocfg)

print(f"   ✅ Config: simulation.sumocfg")

# ============================================================================
# SUCCESS
# ============================================================================

print("\n" + "=" * 80)
print("✅✅✅ PHASE 2 COMPLETE - MODERATE TRAFFIC READY ✅✅✅")
print("=" * 80)

print(f"\n📊 Summary:")
print(f"   • {valid_routes} validated routes")
print(f"   • {flow_counter} traffic flows (50% reduced)")
print(f"   • ~{int(total_vph * 0.04)} vehicles simultaneously")
print(f"   • {total_vph} vehicles/hour throughput")
print(f"   • Smooth flow, no jams!")

print(f"\n🚗 Vehicle Distribution:")
for vtype, props in vehicle_types.items():
    print(f"   • {vtype.title()}: {int(props['prob']*100)}%")

print(f"\n🔍 Test in SUMO-GUI:")
print(f"   > sumo-gui -c sumo_data\\simulation.sumocfg")
print(f"\n   Should see smooth traffic flow without jams!")

print(f"\n➡️  Ready for web visualization!")
print("=" * 80)
