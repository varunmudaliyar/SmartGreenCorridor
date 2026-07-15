"""
TomTom Integration Service for SmartGreenCorridor
Fetches real-time traffic flow + incidents for Andheri area.
Called ONCE at simulation start, data cached for the session.
"""

import requests
import time
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TomTomService")

# ============================================================================
# TomTom API Configuration
# ============================================================================
TOMTOM_API_KEY = "YOUR_TOMTOM_API_KEY_HERE"  # <-- Paste your key here

# Andheri bounding box
BOUNDING_BOX = {
    "north": 19.1341,
    "south": 19.1017,
    "west": 72.8248,
    "east": 72.8685,
}

# TomTom API base URLs
TRAFFIC_FLOW_BASE = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
TRAFFIC_INCIDENTS_BASE = "https://api.tomtom.com/traffic/services/5/incidentDetails"
TRAFFIC_FLOW_TILE_BASE = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


class TomTomService:
    """
    Handles all TomTom API interactions.
    Fetches traffic flow data and incidents for the Andheri road network.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or TOMTOM_API_KEY
        self.bounding_box = BOUNDING_BOX
        self.traffic_flow_data = []       # List of flow segments
        self.traffic_incidents = []        # List of incidents (blocked roads, etc.)
        self.fetch_timestamp = None        # When data was last fetched
        self._raw_flow_response = None
        self._raw_incidents_response = None

    # ========================================================================
    # PUBLIC: Fetch all traffic data (called once at simulation start)
    # ========================================================================
    def fetch_all_traffic_data(self):
        """
        Main entry point. Fetches both traffic flow and incidents.
        Returns dict with 'flow' and 'incidents' keys.
        """
        logger.info("=" * 60)
        logger.info("🌐 FETCHING TOMTOM TRAFFIC DATA FOR ANDHERI")
        logger.info("=" * 60)

        flow_data = self._fetch_traffic_flow_grid()
        incidents = self._fetch_traffic_incidents()

        self.fetch_timestamp = time.time()

        summary = {
            "flow_segments": len(flow_data),
            "incidents": len(incidents),
            "timestamp": self.fetch_timestamp,
            "bounding_box": self.bounding_box,
        }

        logger.info(f"✅ Fetched {len(flow_data)} flow segments, {len(incidents)} incidents")
        return {
            "flow": flow_data,
            "incidents": incidents,
            "summary": summary,
        }

    # ========================================================================
    # TRAFFIC FLOW: Grid-based sampling across Andheri
    # ========================================================================
    def _fetch_traffic_flow_grid(self):
        """
        Samples traffic flow at a grid of points across the bounding box.
        TomTom Flow Segment API returns the nearest road segment's data
        for each query point.
        """
        logger.info("📊 Fetching traffic flow data (grid sampling)...")

        # Create grid of sample points across Andheri
        # ~200m spacing gives good coverage without too many API calls
        lat_step = 0.002   # ~220m
        lon_step = 0.0025  # ~230m

        lat = self.bounding_box["south"]
        sample_points = []
        while lat <= self.bounding_box["north"]:
            lon = self.bounding_box["west"]
            while lon <= self.bounding_box["east"]:
                sample_points.append((lat, lon))
                lon += lon_step
            lat += lat_step

        logger.info(f"  📍 Sampling {len(sample_points)} grid points...")

        flow_segments = []
        seen_coords = set()  # Deduplicate segments

        for idx, (lat, lon) in enumerate(sample_points):
            try:
                segment = self._fetch_flow_at_point(lat, lon)
                if segment:
                    # Deduplicate by road coordinates
                    coord_key = (
                        round(segment["coordinates"][0]["latitude"], 5),
                        round(segment["coordinates"][0]["longitude"], 5),
                    )
                    if coord_key not in seen_coords:
                        seen_coords.add(coord_key)
                        flow_segments.append(segment)

                # Rate limiting: TomTom free tier = 2,500/day
                if idx % 10 == 0 and idx > 0:
                    time.sleep(0.1)  # Small delay every 10 requests

            except Exception as e:
                logger.warning(f"  ⚠️ Failed for point ({lat:.4f}, {lon:.4f}): {e}")
                continue

            if idx % 50 == 0:
                logger.info(f"  ... processed {idx}/{len(sample_points)} points, {len(flow_segments)} segments found")

        self.traffic_flow_data = flow_segments
        logger.info(f"  ✅ Total unique flow segments: {len(flow_segments)}")
        return flow_segments

    def _fetch_flow_at_point(self, lat, lon):
        """
        Fetches traffic flow for the road segment nearest to (lat, lon).
        Returns parsed segment data or None.
        """
        url = TRAFFIC_FLOW_BASE
        params = {
            "key": self.api_key,
            "point": f"{lat},{lon}",
            "unit": "KMPH",
            "thickness": 1,
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        flow = data.get("flowSegmentData", {})

        if not flow:
            return None

        # Extract coordinates of the road segment
        coords = flow.get("coordinates", {}).get("coordinate", [])
        if not coords:
            return None

        # Calculate congestion ratio
        current_speed = flow.get("currentSpeed", 0)
        free_flow_speed = flow.get("freeFlowSpeed", 1)
        congestion_ratio = 1.0 - (current_speed / max(free_flow_speed, 1))
        congestion_ratio = max(0.0, min(1.0, congestion_ratio))

        # Classify congestion level
        if congestion_ratio < 0.2:
            congestion_level = "free_flow"
        elif congestion_ratio < 0.4:
            congestion_level = "light"
        elif congestion_ratio < 0.6:
            congestion_level = "moderate"
        elif congestion_ratio < 0.8:
            congestion_level = "heavy"
        else:
            congestion_level = "severe"

        return {
            "current_speed": current_speed,
            "free_flow_speed": free_flow_speed,
            "current_travel_time": flow.get("currentTravelTime", 0),
            "free_flow_travel_time": flow.get("freeFlowTravelTime", 0),
            "congestion_ratio": round(congestion_ratio, 3),
            "congestion_level": congestion_level,
            "confidence": flow.get("confidence", 0),
            "road_closure": flow.get("roadClosure", False),
            "coordinates": coords,  # List of {latitude, longitude}
            "frc": flow.get("frc", ""),  # Functional Road Class
        }

    # ========================================================================
    # TRAFFIC INCIDENTS: Blocked roads, accidents, construction
    # ========================================================================
    def _fetch_traffic_incidents(self):
        """
        Fetches traffic incidents (accidents, road closures, construction)
        within the Andheri bounding box.
        """
        logger.info("🚧 Fetching traffic incidents...")

        bb = self.bounding_box
        url = f"{TRAFFIC_INCIDENTS_BASE}"
        params = {
            "key": self.api_key,
            "bbox": f"{bb['south']},{bb['west']},{bb['north']},{bb['east']}",
            "fields": "{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code},startTime,endTime,from,to,length,delay,roadNumbers,aci{probabilityOfOccurrence,numberOfReports,lastReportTime}}}}",
            "language": "en-US",
            "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",
            "timeValidityFilter": "present",
        }

        try:
            response = requests.get(url, params=params, timeout=15)

            if response.status_code != 200:
                logger.warning(f"  ⚠️ Incidents API returned {response.status_code}")
                return []

            data = response.json()
            incidents_raw = data.get("incidents", [])

            incidents = []
            for inc in incidents_raw:
                inc_type = inc.get("type", "UNKNOWN")
                props = inc.get("properties", {})
                geometry = inc.get("geometry", {})

                # Extract coordinates
                coords = geometry.get("coordinates", [])
                parsed_coords = self._parse_incident_coords(geometry)

                # Classify severity
                magnitude = props.get("magnitudeOfDelay", 0)
                if magnitude >= 4:
                    severity = "critical"
                elif magnitude >= 3:
                    severity = "major"
                elif magnitude >= 2:
                    severity = "moderate"
                else:
                    severity = "minor"

                # Get event descriptions
                events = props.get("events", [])
                descriptions = [e.get("description", "") for e in events]

                incident = {
                    "type": inc_type,
                    "severity": severity,
                    "magnitude_of_delay": magnitude,
                    "from_road": props.get("from", ""),
                    "to_road": props.get("to", ""),
                    "description": "; ".join(descriptions) if descriptions else inc_type,
                    "delay_seconds": props.get("delay", 0),
                    "length_meters": props.get("length", 0),
                    "coordinates": parsed_coords,
                    "road_numbers": props.get("roadNumbers", []),
                    "icon_category": props.get("iconCategory", 0),
                    "is_road_closure": props.get("iconCategory", 0) in [0, 7, 8],
                }
                incidents.append(incident)

            self.traffic_incidents = incidents
            logger.info(f"  ✅ Found {len(incidents)} incidents")

            # Log blocked roads
            blocked = [i for i in incidents if i["is_road_closure"]]
            if blocked:
                logger.warning(f"  🚫 {len(blocked)} ROAD CLOSURES detected!")
                for b in blocked:
                    logger.warning(f"     → {b['from_road']} to {b['to_road']}: {b['description']}")

            return incidents

        except Exception as e:
            logger.error(f"  ❌ Failed to fetch incidents: {e}")
            return []

    def _parse_incident_coords(self, geometry):
        """Parse incident geometry into list of {latitude, longitude}"""
        coords = []
        geo_type = geometry.get("type", "")
        raw_coords = geometry.get("coordinates", [])

        if geo_type == "Point" and len(raw_coords) >= 2:
            coords.append({"latitude": raw_coords[1], "longitude": raw_coords[0]})
        elif geo_type == "LineString":
            for c in raw_coords:
                if len(c) >= 2:
                    coords.append({"latitude": c[1], "longitude": c[0]})
        elif geo_type == "MultiPoint":
            for c in raw_coords:
                if len(c) >= 2:
                    coords.append({"latitude": c[1], "longitude": c[0]})

        return coords

    # ========================================================================
    # PUBLIC: Get data for frontend visualization
    # ========================================================================
    def get_frontend_traffic_data(self):
        """
        Returns traffic data formatted for the frontend heatmap + road segments.
        """
        heatmap_points = []
        road_segments = []

        # --- Heatmap points from flow data ---
        for segment in self.traffic_flow_data:
            for coord in segment["coordinates"]:
                lat = coord.get("latitude", 0)
                lon = coord.get("longitude", 0)
                intensity = segment["congestion_ratio"]

                heatmap_points.append({
                    "lat": lat,
                    "lon": lon,
                    "intensity": round(intensity, 3),
                })

            # Road segment with color
            if len(segment["coordinates"]) >= 2:
                road_segments.append({
                    "coordinates": [
                        {"lat": c["latitude"], "lon": c["longitude"]}
                        for c in segment["coordinates"]
                    ],
                    "congestion_ratio": segment["congestion_ratio"],
                    "congestion_level": segment["congestion_level"],
                    "current_speed": segment["current_speed"],
                    "free_flow_speed": segment["free_flow_speed"],
                    "road_closure": segment["road_closure"],
                })

        # --- Incident markers ---
        incident_markers = []
        for inc in self.traffic_incidents:
            if inc["coordinates"]:
                center = inc["coordinates"][0]
                incident_markers.append({
                    "lat": center["latitude"],
                    "lon": center["longitude"],
                    "type": inc["type"],
                    "severity": inc["severity"],
                    "description": inc["description"],
                    "is_road_closure": inc["is_road_closure"],
                    "delay_seconds": inc["delay_seconds"],
                })

        return {
            "heatmap_points": heatmap_points,
            "road_segments": road_segments,
            "incident_markers": incident_markers,
            "summary": {
                "total_segments": len(self.traffic_flow_data),
                "total_incidents": len(self.traffic_incidents),
                "road_closures": len([i for i in self.traffic_incidents if i["is_road_closure"]]),
                "avg_congestion": round(
                    sum(s["congestion_ratio"] for s in self.traffic_flow_data) / max(len(self.traffic_flow_data), 1),
                    3
                ),
                "fetch_timestamp": self.fetch_timestamp,
            },
        }


# ============================================================================
# Standalone test
# ============================================================================
if __name__ == "__main__":
    service = TomTomService()
    data = service.fetch_all_traffic_data()
    frontend_data = service.get_frontend_traffic_data()

    print(f"\n📊 Summary:")
    print(f"   Flow segments: {len(data['flow'])}")
    print(f"   Incidents: {len(data['incidents'])}")
    print(f"   Heatmap points: {len(frontend_data['heatmap_points'])}")
    print(f"   Road segments: {len(frontend_data['road_segments'])}")

    # Save for debugging
    with open("Newupdate/tomtom_debug_output.json", "w") as f:
        json.dump(frontend_data, f, indent=2)
    print("   💾 Saved debug output to Newupdate/tomtom_debug_output.json")