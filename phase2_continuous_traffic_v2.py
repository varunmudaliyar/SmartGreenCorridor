#!/usr/bin/env python3
"""
PHASE 2 - Continuous High-Density Traffic (Fixed - No Duplicates)
==================================================================
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
print("PHASE 2 - CONTINUOUS HIGH-DENSITY TRAFFIC (v2)")
print("=" * 80)

# ============================================================================
# LOAD NETWORK
# ============================================================================

print("\n📊 Analyzing network...")

try:
    import sumolib
    net = sumolib.net.readNet(NET_FILE)
    
    edges = list(net.getEdges())
    print(f"   Total edges: {len(edges)}")
    
    suitable_edges = [e for e in edges if e.getLength() >= 100]
    print(f"   Suitable edges: {len(suitable_edges)}")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

# ============================================================================
# BUILD ROUTES XML
# ============================================================================

print("\n🔄 Creating traffic flows...")

root = ET.Element('routes')
root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

# Vehicle types
vehicle_types = {
    'car': {'vClass': 'passenger', 'color': '1,0,0', 'shape': 'passenger', 'prob': 0.60},
    'taxi': {'vClass': 'taxi', 'color': '1,1,0', 'shape': 'taxi', 'prob': 0.15},
    'bus': {'vClass': 'bus', 'color': '0,0,1', 'shape': 'bus', 'prob': 0.10},
    'truck': {'vClass': 'delivery', 'color': '0.5,0.5,0.5', 'shape': 'truck', 'prob': 0.10},
    'motorcycle': {'vClass': 'motorcycle', 'color': '0,1,0', 'shape': 'motorcycle', 'prob': 0.05}
}

# Add vehicle types
for vtype_id, props in vehicle_types.items():
    vtype = ET.SubElement(root, 'vType')
    vtype.set('id', vtype_id)
    vtype.set('vClass', props['vClass'])
    vtype.set('color', props['color'])
    vtype.set('guiShape', props['shape'])
    vtype.set('speedFactor', 'normc(1.0,0.1,0.8,1.2)')
    vtype.set('accel', '2.6')
    vtype.set('decel', '4.5')

print(f"   ✅ Added {len(vehicle_types)} vehicle types")

# Create flows
random.seed(42)
num_flows = min(300, len(suitable_edges))
flow_edges = random.sample(suitable_edges, num_flows)

route_id_counter = 0
flow_counter = 0
total_vph = 0

for idx, source_edge in enumerate(flow_edges):
    # Pick random destination
    dest_edge = random.choice(suitable_edges)
    
    if source_edge.getID() == dest_edge.getID():
        continue
    
    try:
        # Find route
        route_result = net.getOptimalPath(source_edge, dest_edge)
        
        if not route_result or not route_result[0]:
            continue
        
        edge_ids = [e.getID() for e in route_result[0]]
        
        # Create UNIQUE route
        route_id = f"route_{route_id_counter}"
        route_id_counter += 1
        
        route = ET.SubElement(root, 'route')
        route.set('id', route_id)
        route.set('edges', ' '.join(edge_ids))
        
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
                
                vph = random.randint(80, 200)
                flow.set('vehsPerHour', str(vph))
                flow.set('departSpeed', 'max')
                flow.set('departLane', 'best')
                
                total_vph += vph
    
    except:
        continue
    
    if (idx + 1) % 50 == 0:
        print(f"   Progress: {idx + 1}/{num_flows}, {flow_counter} flows created...")

print(f"\n✅ Created {flow_counter} flows, {route_id_counter} unique routes")
print(f"   Expected vehicles: ~{int(total_vph * 0.03)} on road at any time")
print(f"   Throughput: {total_vph} veh/hour")

# ============================================================================
# SAVE FILES
# ============================================================================

print("\n💾 Saving files...")

tree = ET.ElementTree(root)
ET.indent(tree, space="    ")

with open(ROUTES_FILE, 'wb') as f:
    f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(f, encoding='utf-8', xml_declaration=False)

print(f"   ✅ Routes: {ROUTES_FILE} ({os.path.getsize(ROUTES_FILE)/1024:.1f} KB)")

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
print("✅✅✅ PHASE 2 COMPLETE - CONTINUOUS TRAFFIC READY ✅✅✅")
print("=" * 80)

print(f"\n📊 Summary:")
print(f"   • {flow_counter} traffic flows")
print(f"   • {route_id_counter} unique routes")
print(f"   • ~{int(total_vph * 0.03)} vehicles on road simultaneously")
print(f"   • {SIMULATION_END/3600:.0f} hour continuous simulation")

print(f"\n🔍 Test in SUMO-GUI:")
print(f"   > sumo-gui -c sumo_data\\simulation.sumocfg")
print(f"   Click Play ▶️ - traffic flows continuously!")

print(f"\n➡️  Next: Real-time web visualization with TraCI")
print("=" * 80)
