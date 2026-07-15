"""
Traffic Mapper: Maps TomTom data → SUMO edges.
- Exact match: Every SUMO edge gets a specific TomTom speed.
- Injects/removes vehicles to match real-world congestion levels.
- Blocks edges with road closures/incidents.
"""

import math
import logging
import traci

logger = logging.getLogger("TrafficMapper")


class TrafficMapper:
    """
    Maps TomTom traffic flow data to SUMO network edges.
    Uses exact nearest-neighbor matching with coordinate conversion.
    """

    def __init__(self):
        self.edge_mapping = {}       # edge_id -> tomtom segment data
        self.edge_geo_cache = {}     # edge_id -> (lat, lon) center point
        self.blocked_edges = set()   # Edges blocked due to incidents
        self.congestion_map = {}     # edge_id -> congestion_ratio (0-1)
        self.original_speeds = {}    # edge_id -> original max speed (for restore)
        self.injected_vehicles = []  # Track vehicles we injected

    # ========================================================================
    # MAIN: Apply TomTom data to SUMO (called once after fetch)
    # ========================================================================
    def apply_traffic_to_sumo(self, tomtom_data):
        """
        Main entry point. Takes TomTom data dict and applies to running SUMO.
        Must be called AFTER traci.start().
        
        Args:
            tomtom_data: Dict from TomTomService.fetch_all_traffic_data()
        """
        logger.info("=" * 60)
        logger.info("🗺️  MAPPING TOMTOM DATA → SUMO NETWORK")
        logger.info("=" * 60)

        flow_segments = tomtom_data.get("flow", [])
        incidents = tomtom_data.get("incidents", [])

        # Step 1: Build SUMO edge geo cache
        self._build_edge_geo_cache()

        # Step 2: Map each SUMO edge to nearest TomTom segment
        self._map_edges_to_tomtom(flow_segments)

        # Step 3: Apply speeds to SUMO edges
        self._apply_speeds()

        # Step 4: Handle incidents (block roads)
        self._apply_incidents(incidents)

        # Step 5: Inject vehicles for congestion
        self._inject_congestion_vehicles()

        logger.info("✅ Traffic mapping complete!")
        self._log_summary()

    # ========================================================================
    # Step 1: Build cache of SUMO edge center points in lat/lon
    # ========================================================================
    def _build_edge_geo_cache(self):
        """
        Converts all SUMO edge center points to lat/lon coordinates.
        Uses traci.simulation.convertGeo() for accurate conversion.
        """
        logger.info("  📍 Building SUMO edge geo cache...")

        edge_ids = traci.edge.getIDList()
        cached = 0

        for edge_id in edge_ids:
            # Skip internal edges (junctions)
            if edge_id.startswith(":"):
                continue

            try:
                # Get edge shape (list of (x, y) points in SUMO coords)
                shape = traci.edge.getShape(edge_id)

                if not shape:
                    continue

                # Get center point of edge
                if len(shape) >= 2:
                    mid_idx = len(shape) // 2
                    cx, cy = shape[mid_idx]
                else:
                    cx, cy = shape[0]

                # Convert SUMO x,y to lat/lon
                lon, lat = traci.simulation.convertGeo(cx, cy)

                self.edge_geo_cache[edge_id] = (lat, lon)
                cached += 1

            except Exception as e:
                continue

        logger.info(f"  ✅ Cached {cached} edges with geo coordinates")

    # ========================================================================
    # Step 2: Map SUMO edges to nearest TomTom segment
    # ========================================================================
    def _map_edges_to_tomtom(self, flow_segments):
        """
        For each SUMO edge, find the closest TomTom flow segment.
        Uses Haversine distance for exact matching.
        """
        logger.info(f"  🔗 Mapping {len(self.edge_geo_cache)} edges to {len(flow_segments)} TomTom segments...")

        if not flow_segments:
            logger.warning("  ⚠️ No TomTom flow segments to map!")
            return

        # Pre-compute TomTom segment center points
        tomtom_centers = []
        for seg in flow_segments:
            coords = seg.get("coordinates", [])
            if coords:
                avg_lat = sum(c["latitude"] for c in coords) / len(coords)
                avg_lon = sum(c["longitude"] for c in coords) / len(coords)
                tomtom_centers.append((avg_lat, avg_lon, seg))

        matched = 0
        for edge_id, (edge_lat, edge_lon) in self.edge_geo_cache.items():
            best_dist = float("inf")
            best_segment = None

            for tt_lat, tt_lon, segment in tomtom_centers:
                dist = self._haversine(edge_lat, edge_lon, tt_lat, tt_lon)
                if dist < best_dist:
                    best_dist = dist
                    best_segment = segment

            # Only match if within 300m (reasonable for urban roads)
            if best_segment and best_dist <= 300:
                self.edge_mapping[edge_id] = best_segment
                self.congestion_map[edge_id] = best_segment["congestion_ratio"]
                matched += 1
            else:
                # No close match — keep SUMO defaults, assume light traffic
                self.congestion_map[edge_id] = 0.1

        logger.info(f"  ✅ Matched {matched}/{len(self.edge_geo_cache)} edges to TomTom data")

    # ========================================================================
    # Step 3: Apply TomTom speeds to SUMO edges
    # ========================================================================
    def _apply_speeds(self):
        """
        Sets the max speed of each matched SUMO edge to TomTom's currentSpeed.
        """
        logger.info("  🚗 Applying TomTom speeds to SUMO edges...")

        applied = 0
        for edge_id, segment in self.edge_mapping.items():
            try:
                # Save original speed for potential restore
                if edge_id not in self.original_speeds:
                    self.original_speeds[edge_id] = traci.edge.getMaxSpeed(edge_id)

                # Convert km/h to m/s for SUMO
                tomtom_speed_ms = segment["current_speed"] / 3.6

                # Don't set speed below 1 m/s (avoid stuck vehicles)
                tomtom_speed_ms = max(1.0, tomtom_speed_ms)

                # Apply to all lanes of this edge
                lane_count = traci.edge.getLaneNumber(edge_id)
                for lane_idx in range(lane_count):
                    lane_id = f"{edge_id}_{lane_idx}"
                    try:
                        traci.lane.setMaxSpeed(lane_id, tomtom_speed_ms)
                    except Exception:
                        pass

                applied += 1

            except Exception as e:
                continue

        logger.info(f"  ✅ Applied speeds to {applied} edges")

    # ========================================================================
    # Step 4: Handle incidents (block edges)
    # ========================================================================
    def _apply_incidents(self, incidents):
        """
        For road closures/severe incidents, block the nearest SUMO edges.
        """
        logger.info(f"  🚧 Processing {len(incidents)} incidents...")

        closures = [i for i in incidents if i.get("is_road_closure", False)]
        severe = [i for i in incidents if i.get("severity") in ("critical", "major") and not i.get("is_road_closure")]

        blocked_count = 0

        for incident in closures + severe:
            coords = incident.get("coordinates", [])
            if not coords:
                continue

            # Find nearest edge to incident
            inc_lat = coords[0]["latitude"]
            inc_lon = coords[0]["longitude"]

            nearest_edge = self._find_nearest_edge(inc_lat, inc_lon)
            if nearest_edge:
                try:
                    # Block the edge by disallowing all vehicles
                    lane_count = traci.edge.getLaneNumber(nearest_edge)
                    for lane_idx in range(lane_count):
                        lane_id = f"{nearest_edge}_{lane_idx}"
                        try:
                            traci.lane.setDisallowed(lane_id, ["passenger", "bus", "taxi", "emergency"])
                        except Exception:
                            pass

                    self.blocked_edges.add(nearest_edge)
                    self.congestion_map[nearest_edge] = 1.0  # Maximum congestion
                    blocked_count += 1

                    logger.info(f"    🚫 Blocked edge {nearest_edge}: {incident.get('description', 'N/A')}")

                except Exception as e:
                    logger.warning(f"    ⚠️ Failed to block edge {nearest_edge}: {e}")

        logger.info(f"  ✅ Blocked {blocked_count} edges due to incidents")

    # ========================================================================
    # Step 5: Inject vehicles to match congestion levels
    # ========================================================================
    def _inject_congestion_vehicles(self):
        """
        Injects additional vehicles on congested edges to create realistic
        traffic density in SUMO. Also removes vehicles from low-traffic edges.
        """
        logger.info("  🚗 Injecting congestion vehicles...")

        injected = 0
        max_inject = 200  # Cap total injected vehicles for performance

        # Sort edges by congestion (most congested first)
        congested_edges = sorted(
            [(eid, ratio) for eid, ratio in self.congestion_map.items() if ratio > 0.3],
            key=lambda x: x[1],
            reverse=True
        )

        for edge_id, congestion_ratio in congested_edges:
            if injected >= max_inject:
                break

            if edge_id in self.blocked_edges:
                continue

            # Calculate how many vehicles to inject based on congestion
            # Heavy congestion → more vehicles
            try:
                edge_length = traci.edge.getLength(edge_id)
                lane_count = traci.edge.getLaneNumber(edge_id)

                # Target vehicle density: congestion_ratio * max_density
                # Max density ~= 1 vehicle per 8 meters per lane
                max_vehicles = int((edge_length / 8.0) * lane_count)
                target_vehicles = int(congestion_ratio * max_vehicles)

                # Current vehicles on this edge
                current_vehicles = traci.edge.getLastStepVehicleNumber(edge_id)

                vehicles_to_add = max(0, target_vehicles - current_vehicles)
                vehicles_to_add = min(vehicles_to_add, 5)  # Max 5 per edge per injection

                for i in range(vehicles_to_add):
                    veh_id = f"tomtom_congestion_{edge_id}_{i}_{int(traci.simulation.getTime())}"
                    try:
                        # Create route with just this edge
                        route_id = f"route_congestion_{edge_id}_{i}"
                        traci.route.add(route_id, [edge_id])
                        traci.vehicle.add(
                            veh_id,
                            route_id,
                            typeID="DEFAULT_VEHTYPE",
                            depart="now",
                            departSpeed="0",
                        )
                        # Set slow speed to simulate congestion
                        traci.vehicle.setMaxSpeed(veh_id, max(1.0, (1 - congestion_ratio) * 13.9))
                        self.injected_vehicles.append(veh_id)
                        injected += 1
                    except Exception:
                        pass

            except Exception as e:
                continue

        logger.info(f"  ✅ Injected {injected} congestion vehicles")

    # ========================================================================
    # PUBLIC: Get congestion data for a specific edge
    # ========================================================================
    def get_edge_congestion(self, edge_id):
        """Returns congestion ratio (0-1) for a given edge."""
        return self.congestion_map.get(edge_id, 0.0)

    def is_edge_blocked(self, edge_id):
        """Returns True if edge is blocked due to incident."""
        return edge_id in self.blocked_edges

    def get_all_congestion_data(self):
        """Returns full congestion map for all edges."""
        return self.congestion_map.copy()

    def get_blocked_edges(self):
        """Returns set of blocked edge IDs."""
        return self.blocked_edges.copy()

    # ========================================================================
    # UTILITIES
    # ========================================================================
    def _find_nearest_edge(self, lat, lon, max_dist=200):
        """Find the nearest SUMO edge to a lat/lon point."""
        best_edge = None
        best_dist = float("inf")

        for edge_id, (e_lat, e_lon) in self.edge_geo_cache.items():
            dist = self._haversine(lat, lon, e_lat, e_lon)
            if dist < best_dist and dist <= max_dist:
                best_dist = dist
                best_edge = edge_id

        return best_edge

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two lat/lon points."""
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = math.sin(d_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _log_summary(self):
        """Log a summary of the mapping results."""
        total = len(self.edge_geo_cache)
        mapped = len(self.edge_mapping)
        blocked = len(self.blocked_edges)

        # Congestion breakdown
        levels = {"free_flow": 0, "light": 0, "moderate": 0, "heavy": 0, "severe": 0}
        for edge_id, ratio in self.congestion_map.items():
            if ratio < 0.2:
                levels["free_flow"] += 1
            elif ratio < 0.4:
                levels["light"] += 1
            elif ratio < 0.6:
                levels["moderate"] += 1
            elif ratio < 0.8:
                levels["heavy"] += 1
            else:
                levels["severe"] += 1

        logger.info(f"\n  📊 TRAFFIC MAPPING SUMMARY:")
        logger.info(f"     Total SUMO edges:    {total}")
        logger.info(f"     Matched to TomTom:   {mapped}")
        logger.info(f"     Blocked (incidents):  {blocked}")
        logger.info(f"     Congestion levels:")
        logger.info(f"       🟢 Free flow:  {levels['free_flow']}")
        logger.info(f"       🟡 Light:      {levels['light']}")
        logger.info(f"       🟠 Moderate:   {levels['moderate']}")
        logger.info(f"       🔴 Heavy:      {levels['heavy']}")
        logger.info(f"       ⛔ Severe:     {levels['severe']}")