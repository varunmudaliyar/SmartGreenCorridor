#!/usr/bin/env python3
"""
PHASE 2 - Ultra-Light Anti-Deadlock Traffic (75% Total Reduction)
==================================================================
Minimal traffic for smooth visualization
"""

import os
import sys
import xml.etree.ElementTree as ET
import random

SUMO_HOME = os.environ.get('SUMO_HOME', r'C:\SUMO\sumo-1.25.0')
DATA_DIR = 'sumo_data'
NET_FILE = os.path.join(DATA_DIR, 'mumbai.net.xml')
ROUTES_FILE = os.path.join(DATA_DIR, 'traffic.rou.xml')
SIMULATION_END = 36000

print("=" * 80)
print("PHASE 2 - ULTRA-LIGHT TRAFFIC (Minimal Density)")
print("=" * 80)

# ============================================================================
# LOAD NETWORK
# ============================================================================

print("\n📊 Analyzing network...")

try:
    import sumolib
    net = sumolib.net.readNet(NET_FILE)
    edges = list(net.getEdges())
    
    suitable_edges = [e for e in edges if e.getLength() >= 200 and e.getLaneNumber() <= 4]
    print(f"   Suitable edges: {len(suitable_edges)}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

# ============================================================================
# BUILD ROUTES
# ============================================================================

print("\n🔄 Creating ultra-light traffic flows...")

root = ET.Element('routes')
root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

vehicle_types = {
    'car': {'vClass': 'passenger', 'color': '1,0,0', 'shape': 'passenger', 'prob': 0.70},
    'taxi': {'vClass': 'taxi', 'color': '1,1,0', 'shape': 'taxi', 'prob': 0.20},
    'bus': {'vClass': 'bus', 'color': '0,0,1', 'shape': 'bus', 'prob': 0.07},
    'truck': {'vClass': 'delivery', 'color': '0.5,0.5,0.5', 'shape': 'truck', 'prob': 0.03}
}

# Add vehicle types
for vtype_id, props in vehicle_types.items():
    vtype = ET.SubElement(root, 'vType')
    vtype.set('id', vtype_id)
    vtype.set('vClass', props['vClass'])
    vtype.set('color', props['color'])
    vtype.set('guiShape', props['shape'])
    vtype.set('speedFactor', 'normc(1.0,0.08,0.85,1.15)')
    vtype.set('accel', '2.6')
    vtype.set('decel', '4.5')
    vtype.set('sigma', '0.3')
    vtype.set('impatience', '0.5')
    vtype.set('minGap', '2.5')

print(f"   ✅ {len(vehicle_types)} vehicle types")

random.seed(42)
valid_routes = 0
route_id_counter = 0
flow_counter = 0
total_vph = 0
departure_offset = 0

# ULTRA-LIGHT: Only 60 source edges (was 80)
source_edges = random.sample(suitable_edges, min(60, len(suitable_edges)))

for idx, source_edge in enumerate(source_edges):
    for dest_idx in range(random.randint(1, 2)):
        dest_candidates = [e for e in suitable_edges 
                          if abs(suitable_edges.index(e) - suitable_edges.index(source_edge)) > 30]
        
        if not dest_candidates:
            continue
            
        dest_edge = random.choice(dest_candidates)
        
        try:
            route_result = net.getOptimalPath(source_edge, dest_edge)
            
            if not route_result or not route_result[0]:
                continue
            
            edge_list = route_result[0]
            
            if len(edge_list) < 5 or len(edge_list) > 50:
                continue
            
            edge_ids = [e.getID() for e in edge_list]
            
            # Validate
            valid_route = True
            for i in range(len(edge_list) - 1):
                current_edge = edge_list[i]
                next_edge = edge_list[i + 1]
                outgoing = [e.getID() for e in current_edge.getOutgoing().keys()]
                if next_edge.getID() not in outgoing:
                    valid_route = False
                    break
            
            if not valid_route:
                continue
            
            route_id = f"route_{route_id_counter}"
            route_id_counter += 1
            
            route = ET.SubElement(root, 'route')
            route.set('id', route_id)
            route.set('edges', ' '.join(edge_ids))
            
            valid_routes += 1
            
            for vtype_id, props in vehicle_types.items():
                if random.random() < props['prob']:
                    flow_id = f"flow_{flow_counter}"
                    flow_counter += 1
                    
                    flow = ET.SubElement(root, 'flow')
                    flow.set('id', flow_id)
                    flow.set('type', vtype_id)
                    flow.set('route', route_id)
                    
                    flow_begin = departure_offset % 300
                    flow.set('begin', str(flow_begin))
                    flow.set('end', str(SIMULATION_END))
                    
                    # ULTRA-LIGHT: Very low flow rate (25-60 veh/hour)
                    vph = random.randint(25, 60)
                    flow.set('vehsPerHour', str(vph))
                    flow.set('departSpeed', 'random')
                    flow.set('departLane', 'best')
                    flow.set('departPos', 'random')
                    
                    total_vph += vph
                    departure_offset += 5
        
        except Exception:
            continue
    
    if (idx + 1) % 15 == 0:
        print(f"   Progress: {idx + 1}/{len(source_edges)}, {valid_routes} routes, {flow_counter} flows...")

print(f"\n✅ Ultra-light traffic complete:")
print(f"   Routes: {valid_routes}")
print(f"   Flows: {flow_counter}")
print(f"   Expected vehicles: ~{int(total_vph * 0.05)} on road")
print(f"   Throughput: {total_vph} veh/hour")

# ============================================================================
# SAVE
# ============================================================================

print("\n💾 Saving...")

tree = ET.ElementTree(root)
ET.indent(tree, space="    ")

with open(ROUTES_FILE, 'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(f, encoding='utf-8', xml_declaration=False)

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
        <time-to-teleport value="300"/>
        <max-depart-delay value="600"/>
        <ignore-route-errors value="true"/>
        <routing-algorithm value="astar"/>
        <lateral-resolution value="0.8"/>
    </processing>
    <routing>
        <device.rerouting.probability value="0.5"/>
        <device.rerouting.period value="180"/>
    </routing>
    <report>
        <no-step-log value="true"/>
        <no-warnings value="false"/>
    </report>
</configuration>
"""

with open(os.path.join(DATA_DIR, 'simulation.sumocfg'), 'w') as f:
    f.write(sumocfg)

print(f"   ✅ Saved")

print("\n" + "=" * 80)
print("✅✅✅ ULTRA-LIGHT TRAFFIC READY ✅✅✅")
print("=" * 80)

print(f"\n📊 Summary:")
print(f"   • {flow_counter} flows (75% total reduction)")
print(f"   • ~{int(total_vph * 0.05)} vehicles on road")
print(f"   • Perfect for visualization")

print(f"\n🔍 Test:")
print(f"   > sumo-gui -c sumo_data\\simulation.sumocfg")
print("=" * 80)
