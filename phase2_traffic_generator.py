#!/usr/bin/env python3
"""
PHASE 2 - High-Density Traffic Generation
==========================================
Generates random vehicles across the entire Mumbai network
Uses SUMO's randomTrips.py and duarouter
"""

import os
import sys
import subprocess
import random

# ============================================================================
# CONFIGURATION
# ============================================================================

SUMO_HOME = os.environ.get('SUMO_HOME', r'C:\SUMO\sumo-1.25.0')
DATA_DIR = 'sumo_data'

NET_FILE = os.path.join(DATA_DIR, 'mumbai.net.xml')
TRIPS_FILE = os.path.join(DATA_DIR, 'traffic.trips.xml')
ROUTES_FILE = os.path.join(DATA_DIR, 'traffic.rou.xml')

# Traffic generation parameters
VEHICLE_COUNT = 500  # High density: 500 vehicles
SIMULATION_TIME = 3600  # 1 hour simulation
BEGIN_TIME = 0
END_TIME = SIMULATION_TIME

print("=" * 80)
print("PHASE 2 - HIGH-DENSITY TRAFFIC GENERATION")
print("=" * 80)
print(f"\n🚗 Generating {VEHICLE_COUNT} vehicles")
print(f"⏱️  Simulation time: {SIMULATION_TIME}s ({SIMULATION_TIME/60:.0f} minutes)")

# ============================================================================
# VERIFY SUMO TOOLS
# ============================================================================

randomTrips = os.path.join(SUMO_HOME, 'tools', 'randomTrips.py')
duarouter = os.path.join(SUMO_HOME, 'bin', 'duarouter.exe')

if not os.path.exists(randomTrips):
    print(f"\n❌ randomTrips.py not found at: {randomTrips}")
    print("   Set SUMO_HOME correctly")
    sys.exit(1)

if not os.path.exists(duarouter):
    print(f"\n❌ duarouter not found at: {duarouter}")
    sys.exit(1)

print(f"\n✅ SUMO tools found")
print(f"   randomTrips: {randomTrips}")
print(f"   duarouter: {duarouter}")

# ============================================================================
# STEP 1: GENERATE RANDOM TRIPS
# ============================================================================

print("\n" + "=" * 80)
print("STEP 1: Generating Random Trips")
print("=" * 80)

cmd_trips = [
    'python',
    randomTrips,
    '--net-file', NET_FILE,
    '--output-trip-file', TRIPS_FILE,
    '--begin', str(BEGIN_TIME),
    '--end', str(END_TIME),
    '--period', str(SIMULATION_TIME / VEHICLE_COUNT),  # Even distribution
    '--fringe-factor', '10',  # Start from network edges
    '--min-distance', '500',  # Minimum 500m trips
    '--max-distance', '5000',  # Maximum 5km trips
    '--random',
    '--validate'
]

print(f"\n🚗 Generating {VEHICLE_COUNT} random trips...")
print("   Distribution: Even across simulation time")
print("   Trip length: 500m - 5km")

try:
    result = subprocess.run(cmd_trips, capture_output=True, text=True, check=True)
    
    print(f"\n✅ Random trips generated: {TRIPS_FILE}")
    
    # Count vehicles in trips file
    with open(TRIPS_FILE, 'r', encoding='utf-8') as f:
        trip_count = f.read().count('<trip ')
    
    print(f"   Total trips: {trip_count}")
    
except subprocess.CalledProcessError as e:
    print(f"\n❌ randomTrips failed:")
    print(e.stderr if e.stderr else "Unknown error")
    sys.exit(1)

# ============================================================================
# STEP 2: ROUTE TRIPS WITH DUAROUTER
# ============================================================================

print("\n" + "=" * 80)
print("STEP 2: Computing Routes with duarouter")
print("=" * 80)

cmd_router = [
    duarouter,
    '--trip-files', TRIPS_FILE,
    '--net-file', NET_FILE,
    '--output-file', ROUTES_FILE,
    '--ignore-errors',  # Continue even if some routes fail
    '--repair',  # Try to repair broken routes
    '--no-step-log',
    '--no-warnings',
    '--routing-algorithm', 'dijkstra',
    '--routing-threads', '4'  # Use multiple threads
]

print("\n🛣️  Computing optimal routes...")
print("   Algorithm: Dijkstra")
print("   This may take 30-60 seconds for 500 vehicles...")

try:
    result = subprocess.run(cmd_router, capture_output=True, text=True, check=True)
    
    print(f"\n✅ Routes computed: {ROUTES_FILE}")
    
    # Parse statistics from duarouter output
    if result.stderr:
        # Count routed vehicles
        routed_count = result.stderr.count('Success')
    
    # Verify output file
    file_size = os.path.getsize(ROUTES_FILE) / 1024
    print(f"   File size: {file_size:.1f} KB")
    
    # Count vehicles in route file
    with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        vehicle_count = content.count('<vehicle ')
    
    print(f"   Routed vehicles: {vehicle_count}")
    
    if vehicle_count == 0:
        print("\n❌ No vehicles routed! Network might be disconnected")
        sys.exit(1)
    
except subprocess.CalledProcessError as e:
    print(f"\n❌ duarouter failed:")
    print(e.stderr if e.stderr else "Unknown error")
    sys.exit(1)

# ============================================================================
# STEP 3: ADD VEHICLE TYPES (Different colors/types)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 3: Adding Vehicle Type Definitions")
print("=" * 80)

# Read current routes
with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
    routes_content = f.read()

# Define vehicle types with different characteristics
vehicle_types = """
    <!-- Vehicle Type Definitions for Visual Variety -->
    <vType id="car" vClass="passenger" color="1,0,0" guiShape="passenger" length="4.5" minGap="2.5" maxSpeed="50" accel="2.6" decel="4.5"/>
    <vType id="taxi" vClass="taxi" color="1,1,0" guiShape="taxi" length="4.3" minGap="2.0" maxSpeed="45" accel="2.4" decel="4.5"/>
    <vType id="bus" vClass="bus" color="0,0,1" guiShape="bus" length="12.0" minGap="3.0" maxSpeed="40" accel="1.2" decel="3.5"/>
    <vType id="truck" vClass="delivery" color="0.5,0.5,0.5" guiShape="truck" length="7.5" minGap="3.0" maxSpeed="35" accel="1.5" decel="4.0"/>
    <vType id="motorcycle" vClass="motorcycle" color="0,1,0" guiShape="motorcycle" length="2.2" minGap="1.5" maxSpeed="60" accel="3.5" decel="5.0"/>
"""

# Insert vehicle types after opening <routes> tag
routes_content = routes_content.replace('<routes', '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd"', 1)
routes_content = routes_content.replace('<routes', f'<routes>\n{vehicle_types}\n<!-- Random Traffic Vehicles -->', 1)

# Randomly assign types to vehicles
import xml.etree.ElementTree as ET

try:
    root = ET.fromstring(routes_content)
    
    type_distribution = {
        'car': 0.60,      # 60% cars
        'taxi': 0.15,     # 15% taxis
        'bus': 0.10,      # 10% buses
        'truck': 0.10,    # 10% trucks
        'motorcycle': 0.05 # 5% motorcycles
    }
    
    type_choices = []
    for vtype, prob in type_distribution.items():
        type_choices.extend([vtype] * int(prob * 100))
    
    vehicle_count = 0
    for vehicle in root.findall('vehicle'):
        # Randomly assign type
        vehicle.set('type', random.choice(type_choices))
        vehicle_count += 1
    
    # Write back
    routes_content = ET.tostring(root, encoding='unicode')
    
    with open(ROUTES_FILE, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(routes_content)
    
    print(f"\n✅ Vehicle types assigned")
    print(f"   Total vehicles: {vehicle_count}")
    print(f"   Distribution:")
    print(f"      🚗 Cars: 60%")
    print(f"      🚕 Taxis: 15%")
    print(f"      🚌 Buses: 10%")
    print(f"      🚚 Trucks: 10%")
    print(f"      🏍️  Motorcycles: 5%")

except Exception as e:
    print(f"\n⚠️  Could not assign vehicle types: {e}")
    print("   Continuing with default types...")

# ============================================================================
# SUCCESS
# ============================================================================

print("\n" + "=" * 80)
print("✅✅✅ HIGH-DENSITY TRAFFIC GENERATED ✅✅✅")
print("=" * 80)

print("\n📁 Generated Files:")
print(f"   ✅ {TRIPS_FILE}")
print(f"   ✅ {ROUTES_FILE}")

print("\n📊 Traffic Statistics:")
print(f"   Vehicles: {vehicle_count}")
print(f"   Simulation: {SIMULATION_TIME}s ({SIMULATION_TIME/60:.0f} min)")
print(f"   Density: High (city-scale traffic)")

print("\n🔍 Preview in SUMO-GUI:")
print(f"   > sumo-gui -n {NET_FILE} -r {ROUTES_FILE}")

print("\n➡️  Next: Update backend with TraCI integration")
print("   File: phase2_backend.py")
print("=" * 80)
