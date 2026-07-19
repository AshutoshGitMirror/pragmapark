"""Build the real Mumbai road graph from OpenStreetMap and commit it.

Build-time only. Requires network + the optional geo deps::

    pip install -r requirements-geo.txt
    python scripts/build_mumbai_graph.py

This overwrites ``data/geo/mumbai_graph.gpickle`` (the committed routing
artifact) with a real OSMnx drive network. The runtime/CI keeps working
unchanged because the router just loads whatever pickle exists; the
synthetic grid remains the fallback if this is never run.

After building, commit the resulting pickle::

    git add data/geo/mumbai_graph.gpickle && git commit -m "routing: real OSM Mumbai graph"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.routing.graph_builder import (  # noqa: E402
    GRAPH_PATH,
    MUMBAI_BOX,
    build_city_graph,
    save_graph,
)


def main() -> None:
    print(f"Building real OSM drive graph for Mumbai bbox={MUMBAI_BOX} ...")
    G = build_city_graph("Mumbai, India", MUMBAI_BOX, "drive")
    save_graph(G, GRAPH_PATH)
    print(
        f"Wrote {GRAPH_PATH}\n"
        f"  nodes={G.number_of_nodes()} edges={G.number_of_edges()}\n"
        f"Commit it: git add {GRAPH_PATH} && git commit -m 'routing: real OSM Mumbai graph'"
    )


if __name__ == "__main__":
    main()
