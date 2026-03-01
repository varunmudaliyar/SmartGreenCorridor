#!/usr/bin/env python3
"""
GREEN CORRIDOR - Phase 0: Network Setup (SUMO 1.25.0 Compatible)
==================================================================
Fixed for SUMO 1.25.0 - Removed unsupported flags
"""

import os
import sys
import subprocess
import requests
import json
import xml.etree.ElementTree as ET

# ============================================================================
# CONFIGURATION
# ============================================================================

CITY_NAME = "Mumbai Andheri-Jogeshwari"
NORTH = 19.1300
SOUTH = 19.1050
EAST  = 72.8650
WEST  = 72.8250

OSM_DIR = "sumo_data"
os.makedirs(OSM_DIR, exist_ok=True)

OSM_FILE = os.path.join(OSM_DIR, "mumbai_andheri.osm")
NET_FILE = os.path.join(OSM_DIR, "mumbai.net.xml")
TLS_JSON = os.path.join(OSM_DIR, "traffic_lights.json")
HOSPITALS_JSON = os.path.join(OSM_DIR, "hospitals.json")

print("=" * 80)
print("GREEN CORRIDOR - PHASE 0 (SUMO 1.25.0 COMPATIBLE)")
print("=" * 80)
print(f"\n📍 Location: {CITY_NAME}")
print(f"📦 Bounding Box: ({SOUTH}, {WEST}) to ({NORTH}, {EAST})")

# ============================================================================
# FIND SUMO
# ============================================================================

def fix_sumo_paths():
    """Find SUMO installation"""
    print("\n🔍 Searching for SUMO...")
    
    possible_locations = [
        r"C:\SUMO\sumo-1.25.0",  # Your actual location
        r"C:\Program Files (x86)\Eclipse\Sumo",
        r"C:\Program Files\Eclipse\Sumo",
        os.environ.get('SUMO_HOME', ''),
    ]
    
    for sumo_home in possible_locations:
        if not sumo_home or not os.path.exists(sumo_home):
            continue
        
        netconvert = os.path.join(sumo_home, 'bin', 'netconvert.exe')
        typemap = os.path.join(sumo_home, 'data', 'typemap', 'osmNetconvert.typ.xml')
        
        if os.path.exists(netconvert) and os.path.exists(typemap):
            print(f"✅ Found SUMO at: {sumo_home}")
            os.environ['SUMO_HOME'] = sumo_home
            return netconvert, typemap
    
    print("❌ SUMO not found!")
    sys.exit(1)

NETCONVERT_PATH, TYPEMAP_PATH = fix_sumo_paths()

# ============================================================================
# STEP 1: DOWNLOAD OSM
# ============================================================================

def download_osm(bbox, out_file):
    """Download OSM data"""
    south, west, north, east = bbox
    
    overpass_query = f"""
    [out:xml][timeout:90];
    (
      way["highway"]({south},{west},{north},{east});
      node["amenity"="hospital"]({south},{west},{north},{east});
      node["highway"="traffic_signals"]({south},{west},{north},{east});
      >;
    );
    out meta;
    """
    
    print("\n" + "=" * 80)
    print("STEP 1: Downloading OSM Data")
    print("=" * 80)
    print("📡 Fetching data...")
    
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query.strip().encode("utf-8"),
            timeout=120
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        
        with open(out_file, "wb") as f:
            f.write(response.content)
        
        file_size_kb = len(response.content) / 1024
        
        print(f"\n✅ Downloaded: {out_file}")
        print(f"   Size: {file_size_kb:.1f} KB")
        
        # Count elements
        root = ET.fromstring(response.content)
        roads = len([w for w in root.findall('way') if any(t.get('k') == 'highway' for t in w.findall('tag'))])
        hospitals = len([n for n in root.findall('node') if any(t.get('k') == 'amenity' and t.get('v') == 'hospital' for t in n.findall('tag'))])
        
        print(f"   Roads: {roads}")
        print(f"   Hospitals: {hospitals}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

# ============================================================================
# STEP 2: CONVERT TO SUMO (FIXED FOR SUMO 1.25.0)
# ============================================================================

def run_netconvert(osm_file, net_file, netconvert_exe, typemap_file):
    """Convert OSM to SUMO network - SUMO 1.25.0 compatible"""
    print("\n" + "=" * 80)
    print("STEP 2: Building SUMO Network")
    print("=" * 80)
    
    print(f"🔧 Using: {netconvert_exe}")
    
    # FIXED COMMAND - Removed --tls.guess-threshold (doesn't exist in 1.25.0)
    cmd = [
        netconvert_exe,
        
        # Input/Output
        "--osm-files", osm_file,
        "--output-file", net_file,
        "--type-files", typemap_file,
        
        # Geometry
        "--geometry.remove", "false",
        "--junctions.corner-detail", "5",
        
        # Junctions
        "--junctions.join", "true",
        "--roundabouts.guess", "true",
        
        # Traffic Lights (VALID FLAGS ONLY)
        "--tls.guess", "true",              # Detect TLS positions
        "--tls.guess-signals", "true",      # Guess signal phases
        "--tls.default-type", "actuated",   # Adaptive signals
        "--tls.join", "true",               # Merge nearby TLS
        "--tls.green.time", "31",           # Green duration
        "--tls.yellow.time", "6",           # Yellow duration
        
        # Cleanup
        "--remove-edges.isolated",
        "--keep-edges.by-vclass", "passenger,emergency",
        
        # Error handling
        "--ignore-errors.edge-type",
        "--no-warnings",
        "--xml-validation", "never"
    ]
    
    print("\n⚙️  Converting OSM → SUMO...")
    print("   This may take 30-90 seconds...")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        file_size_kb = os.path.getsize(net_file) / 1024
        
        print(f"\n✅ Network created: {net_file}")
        print(f"   Size: {file_size_kb:.1f} KB")
        
        # Count elements
        with open(net_file, 'r', encoding='utf-8') as f:
            content = f.read()
            tls_count = content.count('<tlLogic')
            junction_count = content.count('<junction id=')
            edge_count = content.count('<edge id=')
        
        print(f"\n📊 Network Statistics:")
        print(f"   Junctions: {junction_count}")
        print(f"   Edges: {edge_count}")
        print(f"   Traffic Lights: {tls_count}")
        
        if tls_count == 0:
            print("\n   ⚠️  WARNING: No traffic lights detected")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ netconvert failed!")
        print("\nError:")
        print(e.stderr if e.stderr else "Unknown error")
        return False

# ============================================================================
# STEP 3: EXTRACT TRAFFIC LIGHTS
# ============================================================================

def extract_traffic_lights(net_file, output_json):
    """Extract traffic light positions"""
    print("\n" + "=" * 80)
    print("STEP 3: Extracting Traffic Lights")
    print("=" * 80)
    
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        
        traffic_lights = []
        
        for junction in root.findall('.//junction[@type="traffic_light"]'):
            traffic_lights.append({
                'id': junction.get('id'),
                'x': float(junction.get('x')),
                'y': float(junction.get('y')),
                'incLanes': junction.get('incLanes', '').split(),
                'shape': junction.get('shape', '')
            })
        
        print(f"\n✅ Found {len(traffic_lights)} traffic lights")
        
        with open(output_json, 'w') as f:
            json.dump(traffic_lights, f, indent=2)
        
        print(f"   Saved: {output_json}")
        
        if len(traffic_lights) > 0:
            print(f"\n📋 Sample:")
            for tl in traffic_lights[:3]:
                print(f"   • {tl['id']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

# ============================================================================
# STEP 4: EXTRACT HOSPITALS
# ============================================================================

def extract_hospitals(osm_file, net_file, output_json):
    """Extract hospitals and map to network"""
    print("\n" + "=" * 80)
    print("STEP 4: Extracting Hospitals")
    print("=" * 80)
    
    try:
        tree = ET.parse(osm_file)
        root = tree.getroot()
        
        hospitals = []
        
        for node in root.findall('.//node'):
            tags = {tag.get('k'): tag.get('v') for tag in node.findall('tag')}
            
            if tags.get('amenity') == 'hospital':
                hospitals.append({
                    'id': len(hospitals) + 1,
                    'name': tags.get('name', f'Hospital {len(hospitals) + 1}'),
                    'lat': float(node.get('lat')),
                    'lon': float(node.get('lon')),
                    'nearest_edge': None
                })
        
        print(f"\n✅ Found {len(hospitals)} hospitals")
        
        if len(hospitals) == 0:
            print("   Creating dummy locations...")
            hospitals = create_dummy_hospitals(net_file)
        
        # Map to edges
        try:
            import sumolib
            net = sumolib.net.readNet(net_file)
            
            print("\n🗺️  Mapping to network edges...")
            
            for hospital in hospitals:
                x, y = net.convertLonLat2XY(hospital['lon'], hospital['lat'])
                edges = net.getNeighboringEdges(x, y, r=200)
                
                if edges:
                    best_edge, dist = min(edges, key=lambda e: e[1])
                    hospital['nearest_edge'] = best_edge.getID()
                    hospital['sumo_x'] = x
                    hospital['sumo_y'] = y
                    print(f"   • {hospital['name']}: {best_edge.getID()}")
        
        except ImportError:
            print("   ⚠️  sumolib not found, skipping edge mapping")
        
        with open(output_json, 'w') as f:
            json.dump(hospitals, f, indent=2)
        
        print(f"\n✅ Saved: {output_json}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

def create_dummy_hospitals(net_file):
    """Create dummy hospital locations"""
    try:
        import sumolib
        net = sumolib.net.readNet(net_file)
        edges = list(net.getEdges())
        
        hospitals = []
        indices = [0, len(edges)//4, len(edges)//2, 3*len(edges)//4]
        
        for i, idx in enumerate(indices[:4]):
            if idx < len(edges):
                edge = edges[idx]
                shape = edge.getShape()
                x, y = shape[0]
                lon, lat = net.convertXY2LonLat(x, y)
                
                hospitals.append({
                    'id': i + 1,
                    'name': f'Emergency Center {chr(65+i)}',
                    'lat': lat,
                    'lon': lon,
                    'nearest_edge': edge.getID(),
                    'sumo_x': x,
                    'sumo_y': y,
                    'is_dummy': True
                })
        
        print(f"   Created {len(hospitals)} dummy locations")
        return hospitals
        
    except:
        return []

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    bbox = (SOUTH, WEST, NORTH, EAST)
    
    try:
        # Step 1
        if not download_osm(bbox, OSM_FILE):
            sys.exit(1)
        
        # Step 2
        if not run_netconvert(OSM_FILE, NET_FILE, NETCONVERT_PATH, TYPEMAP_PATH):
            sys.exit(1)
        
        # Step 3
        if not extract_traffic_lights(NET_FILE, TLS_JSON):
            sys.exit(1)
        
        # Step 4
        if not extract_hospitals(OSM_FILE, NET_FILE, HOSPITALS_JSON):
            sys.exit(1)
        
        # SUCCESS
        print("\n" + "=" * 80)
        print("✅✅✅ PHASE 0 COMPLETE ✅✅✅")
        print("=" * 80)
        
        print("\n📁 Generated Files:")
        for f in [OSM_FILE, NET_FILE, TLS_JSON, HOSPITALS_JSON]:
            if os.path.exists(f):
                size = os.path.getsize(f) / 1024
                print(f"   ✅ {f} ({size:.1f} KB)")
        
        print("\n🔍 Verify Network:")
        print(f"   > sumo-gui {NET_FILE}")
        
        print("\n➡️  Next Step:")
        print("   > python phase0_route_extractor.py")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
