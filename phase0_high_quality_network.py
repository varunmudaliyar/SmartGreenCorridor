#!/usr/bin/env python3
"""
Phase 0 Enhanced - High Quality Network Generation
===================================================
Optimized netconvert parameters for better traffic light detection
"""

import os
import sys
import subprocess
import requests
import json
import xml.etree.ElementTree as ET

# ============================================================================
# HIGH QUALITY CONFIGURATION
# ============================================================================

CITY_NAME = "Mumbai Bandra-Kurla Complex"

# LARGER, BETTER AREA
NORTH = 19.0750
SOUTH = 19.0500
EAST  = 72.8750
WEST  = 72.8500

OSM_DIR = "sumo_data"
os.makedirs(OSM_DIR, exist_ok=True)

OSM_FILE = os.path.join(OSM_DIR, "mumbai_bkc.osm")
NET_FILE = os.path.join(OSM_DIR, "mumbai.net.xml")
TLS_JSON = os.path.join(OSM_DIR, "traffic_lights.json")
HOSPITALS_JSON = os.path.join(OSM_DIR, "hospitals.json")

print("=" * 80)
print("PHASE 0 ENHANCED - HIGH QUALITY NETWORK")
print("=" * 80)
print(f"\n📍 Location: {CITY_NAME}")
print(f"📦 Bounding Box: ({SOUTH}, {WEST}) to ({NORTH}, {EAST})")
print(f"   Area: ~{(NORTH-SOUTH)*111:.1f} km x {(EAST-WEST)*111*0.88:.1f} km")

# ============================================================================
# FIND SUMO
# ============================================================================

def fix_sumo_paths():
    possible_locations = [
        r"C:\SUMO\sumo-1.25.0",
        r"C:\Program Files (x86)\Eclipse\Sumo",
        os.environ.get('SUMO_HOME', ''),
    ]
    
    for sumo_home in possible_locations:
        if not sumo_home or not os.path.exists(sumo_home):
            continue
        
        netconvert = os.path.join(sumo_home, 'bin', 'netconvert.exe')
        typemap = os.path.join(sumo_home, 'data', 'typemap', 'osmNetconvert.typ.xml')
        
        if os.path.exists(netconvert):
            os.environ['SUMO_HOME'] = sumo_home
            return netconvert, typemap if os.path.exists(typemap) else None
    
    print("❌ SUMO not found!")
    sys.exit(1)

NETCONVERT_PATH, TYPEMAP_PATH = fix_sumo_paths()

# ============================================================================
# ENHANCED OSM DOWNLOAD - MORE DATA
# ============================================================================

def download_osm_enhanced(bbox, out_file):
    """Enhanced query - downloads more features"""
    south, west, north, east = bbox
    
    # ENHANCED QUERY - Gets more road types and features
    overpass_query = f"""
    [out:xml][timeout:120];
    (
      way["highway"]({south},{west},{north},{east});
      way["railway"="light_rail"]({south},{west},{north},{east});
      node["amenity"="hospital"]({south},{west},{north},{east});
      node["amenity"="clinic"]({south},{west},{north},{east});
      node["highway"="traffic_signals"]({south},{west},{north},{east});
      >;
    );
    out meta;
    """
    
    print("\n" + "=" * 80)
    print("STEP 1: Downloading Enhanced OSM Data")
    print("=" * 80)
    print("📡 Fetching: Roads + Hospitals + Clinics + Signals")
    print("⏱️  Estimated time: 30-60 seconds...")
    
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query.strip().encode("utf-8"),
            timeout=150
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        
        with open(out_file, "wb") as f:
            f.write(response.content)
        
        file_size_kb = len(response.content) / 1024
        
        print(f"\n✅ Downloaded: {file_size_kb:.1f} KB")
        
        # Count elements
        root = ET.fromstring(response.content)
        roads = len([w for w in root.findall('way') if any(t.get('k') == 'highway' for t in w.findall('tag'))])
        hospitals = len([n for n in root.findall('node') if any(t.get('k') == 'amenity' and t.get('v') in ['hospital', 'clinic'] for t in n.findall('tag'))])
        signals = len([n for n in root.findall('node') if any(t.get('k') == 'highway' and t.get('v') == 'traffic_signals' for t in n.findall('tag'))])
        
        print(f"   Roads: {roads}")
        print(f"   Hospitals/Clinics: {hospitals}")
        print(f"   OSM Traffic Signals: {signals}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

# ============================================================================
# ENHANCED NETCONVERT - AGGRESSIVE TRAFFIC LIGHT DETECTION
# ============================================================================

def run_netconvert_enhanced(osm_file, net_file, netconvert_exe, typemap_file):
    """Enhanced netconvert - more aggressive TLS detection"""
    print("\n" + "=" * 80)
    print("STEP 2: Building High-Quality Network")
    print("=" * 80)
    
    print(f"🔧 Using: {netconvert_exe}")
    
    # ENHANCED PARAMETERS FOR BETTER QUALITY
    cmd = [
        netconvert_exe,
        
        # Input/Output
        "--osm-files", osm_file,
        "--output-file", net_file,
    ]
    
    if typemap_file:
        cmd.extend(["--type-files", typemap_file])
    
    cmd.extend([
        # Geometry - KEEP MORE DETAIL
        "--geometry.remove", "false",
        "--geometry.min-radius.fix", "true",
        "--junctions.corner-detail", "10",  # More detail
        
        # Junctions - AGGRESSIVE MERGING
        "--junctions.join", "true",
        "--junctions.join-dist", "15",  # Merge junctions within 15m
        "--roundabouts.guess", "true",
        
        # Traffic Lights - AGGRESSIVE DETECTION
        "--tls.guess", "true",
        "--tls.guess-signals", "true",
        "--tls.join", "true",
        "--tls.join-dist", "20",  # Merge TLS within 20m
        "--tls.default-type", "actuated",
        
        # Phase timings
        "--tls.green.time", "31",
        "--tls.yellow.time", "6",
        "--tls.red.time", "5",
        
        # Road types - INCLUDE MORE ROADS
        "--keep-edges.by-vclass", "passenger,emergency,delivery",
        "--remove-edges.by-type", "highway.track,highway.path,highway.footway",
        
        # Cleanup
        "--remove-edges.isolated",
        "--junctions.limit-turn-speed", "5.5",
        
        # Output quality
        "--output.street-names", "true",
        "--output.original-names", "true",
        
        # Error handling
        "--ignore-errors", "true",
        "--no-warnings",
        "--xml-validation", "never"
    ])
    
    print("\n⚙️  Converting with enhanced parameters...")
    print("   • Aggressive traffic light detection")
    print("   • More road types included")
    print("   • Better junction merging")
    print("   This may take 60-120 seconds...")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        file_size_kb = os.path.getsize(net_file) / 1024
        
        print(f"\n✅ Network created: {file_size_kb:.1f} KB")
        
        # Detailed statistics
        with open(net_file, 'r', encoding='utf-8') as f:
            content = f.read()
            tls_count = content.count('<tlLogic')
            junction_count = content.count('<junction id=')
            edge_count = content.count('<edge id=')
            tl_junction_count = content.count('type="traffic_light"')
        
        print(f"\n📊 Network Quality Report:")
        print(f"   Junctions: {junction_count}")
        print(f"   Edges (Roads): {edge_count}")
        print(f"   Traffic Light Junctions: {tl_junction_count}")
        print(f"   Traffic Light Programs: {tls_count}")
        
        # Quality assessment
        if tl_junction_count >= 20:
            print(f"   ✅ EXCELLENT - {tl_junction_count} traffic lights")
        elif tl_junction_count >= 10:
            print(f"   ✅ GOOD - {tl_junction_count} traffic lights")
        elif tl_junction_count >= 5:
            print(f"   ⚠️  FAIR - {tl_junction_count} traffic lights (workable)")
        else:
            print(f"   ❌ POOR - Only {tl_junction_count} traffic lights")
            print("      Recommendation: Try a different area or larger bbox")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ netconvert failed!")
        if e.stderr:
            print("\nError (first 500 chars):")
            print(e.stderr[:500])
        return False

# ============================================================================
# EXTRACT TRAFFIC LIGHTS
# ============================================================================

def extract_traffic_lights(net_file, output_json):
    """Extract traffic lights with quality check"""
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
        
        print(f"\n✅ Extracted {len(traffic_lights)} traffic lights")
        
        with open(output_json, 'w') as f:
            json.dump(traffic_lights, f, indent=2)
        
        if len(traffic_lights) > 0:
            print(f"\n📋 Sample Traffic Lights:")
            for tl in traffic_lights[:5]:
                print(f"   • {tl['id']}: ({tl['x']:.0f}, {tl['y']:.0f})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

# ============================================================================
# EXTRACT HOSPITALS
# ============================================================================

def extract_hospitals(osm_file, net_file, output_json):
    """Extract hospitals and clinics"""
    print("\n" + "=" * 80)
    print("STEP 4: Extracting Medical Facilities")
    print("=" * 80)
    
    try:
        tree = ET.parse(osm_file)
        root = tree.getroot()
        
        hospitals = []
        
        for node in root.findall('.//node'):
            tags = {tag.get('k'): tag.get('v') for tag in node.findall('tag')}
            
            amenity = tags.get('amenity')
            if amenity in ['hospital', 'clinic']:
                hospitals.append({
                    'id': len(hospitals) + 1,
                    'name': tags.get('name', f'{amenity.title()} {len(hospitals) + 1}'),
                    'type': amenity,
                    'lat': float(node.get('lat')),
                    'lon': float(node.get('lon')),
                    'nearest_edge': None
                })
        
        print(f"\n✅ Found {len(hospitals)} medical facilities")
        
        if len(hospitals) == 0:
            print("   Creating dummy hospitals...")
            hospitals = create_dummy_hospitals(net_file)
        
        # Map to edges
        try:
            import sumolib
            net = sumolib.net.readNet(net_file)
            
            print("\n🗺️  Mapping to network edges...")
            mapped = 0
            
            for hospital in hospitals:
                x, y = net.convertLonLat2XY(hospital['lon'], hospital['lat'])
                edges = net.getNeighboringEdges(x, y, r=300)  # Increased search radius
                
                if edges:
                    best_edge, dist = min(edges, key=lambda e: e[1])
                    hospital['nearest_edge'] = best_edge.getID()
                    hospital['sumo_x'] = x
                    hospital['sumo_y'] = y
                    mapped += 1
                    print(f"   ✅ {hospital['name']}: {best_edge.getID()} ({dist:.0f}m)")
                else:
                    print(f"   ❌ {hospital['name']}: No nearby edge")
            
            print(f"\n   Mapped: {mapped}/{len(hospitals)} facilities")
        
        except ImportError:
            print("   ⚠️  sumolib not found")
            print("   Install: pip install eclipse-sumo")
        
        with open(output_json, 'w') as f:
            json.dump(hospitals, f, indent=2)
        
        print(f"\n✅ Saved: {output_json}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False

def create_dummy_hospitals(net_file):
    """Create 6 dummy hospitals at different network locations"""
    try:
        import sumolib
        net = sumolib.net.readNet(net_file)
        edges = list(net.getEdges())
        
        # Pick 6 evenly distributed locations
        hospitals = []
        num_dummies = 6
        
        for i in range(num_dummies):
            idx = (i * len(edges)) // num_dummies
            if idx < len(edges):
                edge = edges[idx]
                shape = edge.getShape()
                x, y = shape[len(shape)//2]  # Middle of edge
                lon, lat = net.convertXY2LonLat(x, y)
                
                hospitals.append({
                    'id': i + 1,
                    'name': f'Emergency Medical Center {chr(65+i)}',
                    'type': 'emergency',
                    'lat': lat,
                    'lon': lon,
                    'nearest_edge': edge.getID(),
                    'sumo_x': x,
                    'sumo_y': y,
                    'is_dummy': True
                })
        
        print(f"   Created {len(hospitals)} dummy medical facilities")
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
        if not download_osm_enhanced(bbox, OSM_FILE):
            sys.exit(1)
        
        # Step 2
        if not run_netconvert_enhanced(OSM_FILE, NET_FILE, NETCONVERT_PATH, TYPEMAP_PATH):
            sys.exit(1)
        
        # Step 3
        if not extract_traffic_lights(NET_FILE, TLS_JSON):
            sys.exit(1)
        
        # Step 4
        if not extract_hospitals(OSM_FILE, NET_FILE, HOSPITALS_JSON):
            sys.exit(1)
        
        # SUCCESS
        print("\n" + "=" * 80)
        print("✅✅✅ HIGH QUALITY NETWORK COMPLETE ✅✅✅")
        print("=" * 80)
        
        print("\n📁 Generated Files:")
        for f in [OSM_FILE, NET_FILE, TLS_JSON, HOSPITALS_JSON]:
            if os.path.exists(f):
                size = os.path.getsize(f) / 1024
                print(f"   ✅ {f} ({size:.1f} KB)")
        
        print("\n🔍 Open in SUMO-GUI to verify quality:")
        print(f"   > sumo-gui {NET_FILE}")
        
        print("\n➡️  Next: Generate valid routes")
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
