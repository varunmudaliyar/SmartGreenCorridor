#!/usr/bin/env python3

"""
Export SUMO network geometry (nodes + edges) with latitude/longitude.

Outputs in current folder:
- network_nodes.json
- network_edges.json
- network_nodes.csv
- network_edges.csv
- network_coords.xml
"""

import os
import json
import csv
import xml.etree.ElementTree as ET
import traci
import sumolib

# ====== CONFIGURE THESE ======
DATA_DIR = "sumo_data"
SUMO_CONFIG = os.path.join(DATA_DIR, "simulation.sumocfg")
SUMO_BINARY = "sumo"          # or "sumo-gui"
# ==============================


def start_sumo():
    traci.start([
        SUMO_BINARY,
        "-c", SUMO_CONFIG,
        "--start",
        "--no-step-log",
        "--quit-on-end",
        "--time-to-teleport", "300"
    ])


def load_net():
    # Find .net.xml from DATA_DIR
    net_file = None
    for f in os.listdir(DATA_DIR):
        if f.endswith(".net.xml"):
            net_file = os.path.join(DATA_DIR, f)
            break
    if net_file is None:
        raise RuntimeError("No .net.xml file found in sumo_data/")
    net = sumolib.net.readNet(net_file)
    return net


def export_network_coords():
    net = load_net()

    nodes = {}
    edges = {}

    # NODES: id, lat, lon (and SUMO x,y if you want)
    for node in net.getNodes():
        nid = node.getID()
        x, y = node.getCoord()              # SUMO coordinates
        lat, lon = traci.simulation.convertGeo(x, y, fromGeo=False)
        nodes[nid] = {
            "id": nid,
            "lat": float(lat),
            "lon": float(lon),
            "x": float(x),
            "y": float(y),
        }

    # EDGES: id, from, to, list of (lat,lon) points along edge
    for edge in net.getEdges():
        eid = edge.getID()
        if eid.startswith(":"):
            # internal junction edges; skip for higher-level graph
            continue
        from_node = edge.getFromNode().getID()
        to_node = edge.getToNode().getID()

        shape = edge.getShape()   # list of (x,y)
        points = []
        for x, y in shape:
            lat, lon = traci.simulation.convertGeo(x, y, fromGeo=False)
            points.append({"lat": float(lat), "lon": float(lon)})

        edges[eid] = {
            "id": eid,
            "from": from_node,
            "to": to_node,
            "points": points
        }

    return nodes, edges


def write_json(nodes, edges, out_dir="."):
    with open(os.path.join(out_dir, "network_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(list(nodes.values()), f, indent=2)
    with open(os.path.join(out_dir, "network_edges.json"), "w", encoding="utf-8") as f:
        json.dump(list(edges.values()), f, indent=2)


def write_csv(nodes, edges, out_dir="."):
    # Nodes CSV: id, lat, lon, x, y
    with open(os.path.join(out_dir, "network_nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "lat", "lon", "x", "y"])
        for n in nodes.values():
            w.writerow([n["id"], n["lat"], n["lon"], n["x"], n["y"]])

    # Edges CSV: id, from, to, points_json
    with open(os.path.join(out_dir, "network_edges.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "from", "to", "points_json"])
        for e in edges.values():
            w.writerow([
                e["id"],
                e["from"],
                e["to"],
                json.dumps(e["points"])
            ])


def write_xml(nodes, edges, out_dir="."):
    root = ET.Element("network")

    nodes_el = ET.SubElement(root, "nodes")
    for n in nodes.values():
        ET.SubElement(nodes_el, "node", {
            "id": n["id"],
            "lat": str(n["lat"]),
            "lon": str(n["lon"]),
            "x": str(n["x"]),
            "y": str(n["y"]),
        })

    edges_el = ET.SubElement(root, "edges")
    for e in edges.values():
        edge_el = ET.SubElement(edges_el, "edge", {
            "id": e["id"],
            "from": e["from"],
            "to": e["to"],
        })
        shape_el = ET.SubElement(edge_el, "shape")
        for p in e["points"]:
            ET.SubElement(shape_el, "point", {
                "lat": str(p["lat"]),
                "lon": str(p["lon"]),
            })

    tree = ET.ElementTree(root)
    tree.write(os.path.join(out_dir, "network_coords.xml"), encoding="utf-8", xml_declaration=True)


def main():
    start_sumo()
    try:
        nodes, edges = export_network_coords()
        out_dir = "."
        write_json(nodes, edges, out_dir)
        write_csv(nodes, edges, out_dir)
        write_xml(nodes, edges, out_dir)
        print("Done. Files written in current folder.")
    finally:
        traci.close()


if __name__ == "__main__":
    main()
