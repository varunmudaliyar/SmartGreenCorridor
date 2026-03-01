#!/usr/bin/env python3
"""
GREEN CORRIDOR - Phase 0: Network Setup (WINDOWS FIXED VERSION)
=================================================================
Fixes SUMO_HOME path issues on Windows
"""

import os
import sys
import subprocess
import requests
import json
import xml.etree.ElementTree as ET

# ============================================================================
# WINDOWS PATH FIX
# ============================================================================

def fix_sumo_paths():
    """
    Find and fix SUMO installation paths on Windows
    Returns: (netconvert_path, typemap_path)
    """
    
    print("\n🔍 Searching for SUMO installation...")
    
    # Common SUMO installation locations on Windows
    possible_locations = [
        r"C:\Program Files (x86)\Eclipse\Sumo",
        r"C:\Program Files\Eclipse\Sumo",
        r"C:\Eclipse\Sumo",
        r"C:\Sumo",
        os.environ.get('SUMO_HOME', ''),
    ]
    
    for sumo_home in possible_locations:
        if not sumo_home or not os.path.exists(sumo_home):
            continue
        
        netconvert = os.path.join(sumo_home, 'bin', 'netconvert.exe')
        typemap = os.path.join(sumo_home, 'data', 'typemap', 'osmNetconvert.typ.xml')
        
        if os.path.exists(netconvert) and os.path.exists(typemap):
            print(f"✅ Found SUMO at: {sumo_home}")
            print(f"   netconvert: {netconvert}")
            print(f"   typemap: {typemap}")
            
            # Set SUMO_HOME properly
            os.environ['SUMO_HOME'] = sumo_home
            
            return netconvert, typemap
    
    # Not found - provide installation instructions
    print("❌ SUMO not found in common locations!")
    print("\n📥 Install SUMO:")
    print("   1. Download from: https://www.eclipse.org/sumo/")
    print("   2. Run installer (sumo-win64-x.xx.x.msi)")
    print("   3. Default location: C:\\Program Files (x86)\\Eclipse\\Sumo")
    print("\n   After install, run this script again.")
    sys.exit(1)

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
print("GREEN CORRIDOR - PHASE 0: NETWORK SETUP (WINDOWS FIXED)")
print("=" * 80)
print(f"\n📍 Location: {CITY_NAME}")
print(f"📦 Bounding Box: ({SOUTH}, {WEST}) to ({NORTH}, {EAST})")

# Find SUMO installation
NETCONVERT_PATH, TYPEMAP_PATH = fix_sumo_paths()

# ============================================================================
# STEP 1: DOWNLOAD OSM (Same as before)
# ============================================================================

def download_osm(bbox, out_file):
    """Downloads OSM data using Overpass API"""
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
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    print("\n" + "=" * 80)
    print("STEP 1: Downloading OSM Data")
    print("=" * 80)
    print("📡 Fetching: Roads + Hospitals + Traffic Signals")
    print("⏱️  Estimated time: 20-40 seconds...")
    
    try:
        response = requests.post(
            overpass_url,
            data=overpass_query.strip().encode("utf-8"),
            timeout=120
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Overpass API HTTP {response.status_code}")
        
        with open(out_file, "wb") as f:
            f.write(response.content)
        
        file_size_kb = len(response.content) / 1024
        
        if file_size_kb < 1:
            raise RuntimeError("Downloaded file too small")
        
        print(f"\n✅ OSM data downloaded successfully")
        print(f"   File: {out_file}")
        print(f"   Size: {file_size_kb:.1f} KB")
        
        # Count elements
        root = ET.fromstring(response.content)
        roads = len([w for w in root.findall('way') if any(t.get('k') == 'highway' for t in w.findall('tag'))])
        hospitals = len([n for n in root.findall('node') if any(t.get('k') == 'amenity' and t.get('v') == 'hospital' for t in n.findall('tag'))])
        
        print(f"   Roads: {roads}")
        print(f"   Hospitals: {hospitals}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return False

# ============================================================================
# STEP 2: CONVERT TO SUMO (WINDOWS FIXED VERSION)
# ============================================================================

def run_netconvert(osm_file, net_file, netconvert_exe, typemap_file):
    """
    Convert OSM to SUMO network - Windows compatible version
    Explicitly specifies typemap file to avoid path issues
    """
    print("\n" + "=" * 80)
    print("STEP 2: Building SUMO Network with Traffic Lights")
    print("=" * 80)
    
    print(f"🔧 Using netconvert: {netconvert_exe}")
    print(f"🗺️  Using typemap: {typemap_file}")
    
    # Build command with explicit paths
    cmd = [
        netconvert_exe,
        
        # Input/Output
        "--osm-files", osm_file,
        "--output-file", net_file,
        "--type-files", typemap_file,  # EXPLICIT TYPEMAP (fixes the error!)
        
        # Geometry
        "--geometry.remove", "false",
        "--junctions.corner-detail", "5",
        
        # Junctions
        "--junctions.join", "true",
        "--roundabouts.guess", "true",
        
        # Traffic Lights (CRITICAL)
        "--tls.guess", "true",
        "--tls.default-type", "actuated",
        "--tls.guess-signals", "true",
        "--tls.guess-threshold", "50",
        "--tls.green.time", "31",
        "--tls.yellow.time", "6",
        
        # Cleanup
        "--remove-edges.isolated",
        "--keep-edges.by-vclass", "passenger,emergency",
        
        # Error handling
        "--ignore-errors.edge-type",
        "--no-warnings",
        
        # Disable XML validation (not needed)
        "--xml-validation", "never"
    ]
    
    print("\n⚙️  Running netconvert...")
    print("   Converting OSM → SUMO network...")
    print("   This may take 30-90 seconds...")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=os.getcwd()  # Explicit working directory
        )
        
        file_size_kb = os.path.getsize(net_file) / 1024
        
        print(f"\n✅ SUMO network created successfully")
        print(f"   File: {net_file}")
        print(f"   Size: {file_size_kb:.1f} KB")
        
        # Parse network statistics
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
            print("\n   ⚠️  WARNING: No traffic lights!")
            print("      Try a larger area or different location")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ netconvert failed!")
        print("\nError output:")
        print(e.stderr if e.stderr else "No error details")
        
        print("\n🔧 Troubleshooting:")
        print("   1. Check if OSM file is valid:")
        print(f"      > notepad {osm_file}")
        print("   2. Try opening network file directly:")
        print(f"      > sumo-gui")
        print("   3. Check SUMO installation:")
        print(f"      > {netconvert_exe} --version")
        
        return False

# ============================================================================
# STEP 3: EXTRACT TRAFFIC LIGHTS
# ============================================================================

def extract_traffic_lights(net_file, output_json):
    """Extract traffic light positions from SUMO network"""
    print("\n" + "=" * 80)
    print("STEP 3: Extracting Traffic Light Data")
    print("=" * 80)
    
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        
        traffic_lights = []
        
        for junction in root.findall('.//junction[@type="traffic_light"]'):
            tls_id = junction.get('id')
            x = float(junction.get('x'))
            y = float(junction.get('y'))
            
            traffic_lights.append({
                'id': tls_id,
                'x': x,
                'y': y,
                'incLanes': junction.get('incLanes', '').split(),
                'shape': junction.get('shape', '')
            })
        
        print(f"\n✅ Found {len(traffic_lights)} traffic lights")
        
        if len(traffic_lights) == 0:
            print("   ⚠️  No traffic lights in network")
            print("      The area may have no major intersections")
            return False
        
        # Save to JSON
        with open(output_json, 'w') as f:
            json.dump(traffic_lights, f, indent=2)
        
        print(f"   Saved to: {output_json}")
        
        # Show samples
        print(f"\n📋 Sample traffic lights:")
        for tl in traffic_lights[:5]:
            print(f"   • {tl['id']}: ({tl['x']:.1f}, {tl['y']:.1f})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

# ============================================================================
# STEP 4: EXTRACT HOSPITALS
# ============================================================================

def extract_hospitals(osm_file, net_file, output_json):
    """Extract hospital locations and map to SUMO edges"""
    print("\n" + "=" * 80)
    print("STEP 4: Extracting Hospitals")
    print("=" * 80)
    
    try:
        # Parse OSM
        tree = ET.parse(osm_file)
        root = tree.getroot()
        
        hospitals = []
        
        for node in root.findall('.//node'):
            tags = {tag.get('k'): tag.get('v') for tag in node.findall('tag')}
            
            if tags.get('amenity') == 'hospital':
                lat = float(node.get('lat'))
                lon = float(node.get('lon'))
                name = tags.get('name', f'Hospital {len(hospitals) + 1}')
                
                hospitals.append({
                    'id': len(hospitals) + 1,
                    'osm_id': node.get('id'),
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'nearest_edge': None
                })
        
        print(f"\n✅ Found {len(hospitals)} hospitals in OSM data")
        
        if len(hospitals) == 0:
            print("   ⚠️  No hospitals found, creating dummy locations...")
            hospitals = create_dummy_hospitals(net_file)
        
        # Map to SUMO edges
        print("\n🗺️  Mapping hospitals to SUMO network...")
        
        try:
            import sumolib
            net = sumolib.net.readNet(net_file)
            
            for hospital in hospitals:
                x, y = net.convertLonLat2XY(hospital['lon'], hospital['lat'])
                
                edges = net.getNeighboringEdges(x, y, r=200)
                
                if edges:
                    best_edge, dist = min(edges, key=lambda e: e[1])
                    hospital['nearest_edge'] = best_edge.getID()
                    hospital['sumo_x'] = x
                    hospital['sumo_y'] = y
                    print(f"   • {hospital['name']}: {best_edge.getID()} ({dist:.0f}m)")
                else:
                    print(f"   ⚠️  {hospital['name']}: No nearby edge")
        
        except ImportError:
            print("   ⚠️  sumolib not available, skipping edge mapping")
            print("      Install: pip install eclipse-sumo")
        
        # Save
        with open(output_json, 'w') as f:
            json.dump(hospitals, f, indent=2)
        
        print(f"\n✅ Hospitals saved to: {output_json}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

def create_dummy_hospitals(net_file):
    """Create dummy hospitals from network edges"""
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
        
    except Exception as e:
        print(f"   Failed to create dummies: {e}")
        return []

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    bbox = (SOUTH, WEST, NORTH, EAST)
    
    try:
        # Step 1: Download OSM
        if not download_osm(bbox, OSM_FILE):
            print("\n❌ Failed at Step 1 (download)")
            sys.exit(1)
        
        # Step 2: Convert to SUMO (with fixed paths)
        if not run_netconvert(OSM_FILE, NET_FILE, NETCONVERT_PATH, TYPEMAP_PATH):
            print("\n❌ Failed at Step 2 (conversion)")
            sys.exit(1)
        
        # Step 3: Extract traffic lights
        if not extract_traffic_lights(NET_FILE, TLS_JSON):
            print("\n❌ Failed at Step 3 (traffic lights)")
            sys.exit(1)
        
        # Step 4: Extract hospitals
        if not extract_hospitals(OSM_FILE, NET_FILE, HOSPITALS_JSON):
            print("\n❌ Failed at Step 4 (hospitals)")
            sys.exit(1)
        
        # SUCCESS
        print("\n" + "=" * 80)
        print("✅✅✅ PHASE 0 COMPLETE ✅✅✅")
        print("=" * 80)
        
        print("\n📁 Generated Files:")
        for f in [OSM_FILE, NET_FILE, TLS_JSON, HOSPITALS_JSON]:
            size = os.path.getsize(f) / 1024
            print(f"   ✅ {f} ({size:.1f} KB)")
        
        print("\n🔍 Verify Network:")
        print(f"   > sumo-gui {NET_FILE}")
        
        print("\n📊 Quick Stats:")
        with open(TLS_JSON, 'r') as f:
            print(f"   Traffic Lights: {len(json.load(f))}")
        with open(HOSPITALS_JSON, 'r') as f:
            print(f"   Hospitals: {len(json.load(f))}")
        
        print("\n➡️  Next Step:")
        print("   > python phase0_route_extractor.py")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
