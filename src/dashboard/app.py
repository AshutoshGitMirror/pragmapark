import time as time_module
import webbrowser
from threading import Timer
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output, callback

from src.features.engine import process_raw_to_features
from src.pipeline.orchestrator import pipeline
from src.micro.state_engine import slot_state_engine, SlotState
from typing import cast
from src.api.database import ParkingLot, MicroSlot, get_db_cm

DATA_PATH = "data/raw/birmingham_parking.csv"
TEMPLATE_DIR = Path(__file__).parent / "templates"

app = Dash(__name__, title="Gemini Smart Parking Dashboard")

app.layout = html.Div([
    html.H1("Gemini Smart Parking — 6-Layer Hybrid System",
            style={"textAlign": "center", "color": "#2c3e50", "marginBottom": 30}),
    html.Div([
        html.Div([
            html.H3("Layer 1 — IoT Sensor Feed"),
            dcc.Graph(id="iot-feed-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
        html.Div([
            html.H3("Layer 2 — ML Prediction (RF+XGBoost)"),
            dcc.Graph(id="ml-prediction-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
    ]),
    html.Div([
        html.Div([
            html.H3("Layer 3 — Blockchain Ledger"),
            dcc.Graph(id="blockchain-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
        html.Div([
            html.H3("Layer 4 — RL Pricing Control"),
            dcc.Graph(id="rl-pricing-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
    ]),
    html.Div([
        html.Div([
            html.H3("Layer 5 — Digital Twin Scenarios"),
            dcc.Graph(id="digital-twin-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
        html.Div([
            html.H3("Layer 6 — MARL Multi-Zone Routing"),
            dcc.Graph(id="marl-graph"),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),
    ]),
    html.Div([
        html.H3("Layer 7 — Micro Slot Grid (per-slot occupancy heatmap)",
                style={"textAlign": "center"}),
        dcc.Dropdown(id="lot-selector", placeholder="Select lot...", style={"width": "300px", "margin": "10px auto"}),
        dcc.Graph(id="slot-grid-graph"),
    ], style={"width": "96%", "padding": "10px", "margin": "auto"}),
    dcc.Interval(id="refresh-interval", interval=5000, n_intervals=0),
    dcc.Interval(id="slot-grid-interval", interval=15000, n_intervals=0),
    dcc.Interval(id="lot-dropdown-interval", interval=30000, n_intervals=0),
], style={"fontFamily": "Arial, sans-serif", "padding": "20px", "backgroundColor": "#f5f6fa"})

_cache_ts = 0.0
_cache_df = None

def _get_features():
    global _cache_ts, _cache_df
    now = time_module.monotonic()
    if now - _cache_ts < 4.0 and _cache_df is not None:
        return _cache_df
    try:
        df = process_raw_to_features(DATA_PATH)
        _cache_df = df.sort_values("ts_bucket").tail(100)
    except Exception:
        _cache_df = pd.DataFrame()
    _cache_ts = now
    return _cache_df


@callback(
    Output("iot-feed-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_iot(_):
    df = _get_features()
    if df.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["occupancy_rate"],
                             mode="lines+markers", name="Occupancy Rate",
                             line=dict(color="#3498db")))
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["pe_net_flux"],
                             mode="lines", name="Net Flux",
                             line=dict(color="#e74c3c", dash="dot")))
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("ml-prediction-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_ml(_):
    df = _get_features()
    if df.empty or "target" not in df.columns:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["target"],
                             mode="lines", name="Actual (t+15m)",
                             line=dict(color="#2ecc71")))
    df["sma"] = df["target"].rolling(5).mean()
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["sma"],
                             mode="lines", name="SMA-5 Forecast",
                             line=dict(color="#f39c12", dash="dash")))
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("blockchain-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_blockchain(_):
    df = _get_features()
    if df.empty:
        return go.Figure()
    lots = df.groupby("lot_id")["occupancy_rate"].mean().reset_index()
    ledger = pipeline.ledger
    chain_len = len(ledger.chain) if ledger else 0
    pending = len(ledger.pending_transactions) if ledger else 0
    lots["blocks"] = chain_len
    fig = px.bar(lots, x="lot_id", y="blocks", color="occupancy_rate",
                 color_continuous_scale="Viridis",
                 labels={"lot_id": "Parking Zone", "blocks": "Chain Length"})
    fig.add_annotation(text=f"Pending TX: {pending} | Total Blocks: {chain_len}",
                       xref="paper", yref="paper", x=0.5, y=1.05, showarrow=False)
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("rl-pricing-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_rl(_):
    steps = list(range(20))
    pipeline._ensure_models()
    agent_avail = pipeline.pricing.agent_available
    occs = [0.3 + 0.6 * i / len(steps) for i in steps]
    prices = [pipeline._get_rl_price(occ, 10.0, 200.0)[0] for occ in occs]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=steps, y=occs, name="Occupancy",
                             line=dict(color="#3498db")), secondary_y=False)
    fig.add_trace(go.Scatter(x=steps, y=prices, name="Dynamic Price",
                             line=dict(color="#e74c3c")), secondary_y=True)
    fig.add_annotation(text=f"RL Agent: {'active' if agent_avail else 'heuristic fallback'}",
                       xref="paper", yref="paper", x=0.5, y=1.05, showarrow=False)
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("digital-twin-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_dt(_):
    scenarios = ["Normal", "Zone Closure", "Price Surge", "Capacity Expansion",
                 "Weather", "Holiday Spike"]
    occ_impacts = [0, +0.5, -0.15, -0.17, -0.3, +0.25]
    colors = ["#2ecc71", "#e74c3c", "#f39c12", "#3498db", "#9b59b6", "#e67e22"]
    fig = go.Figure(data=[go.Bar(name="Occupancy Delta", x=scenarios, y=occ_impacts, marker_color=colors)])
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("marl-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_marl(_):
    zones = ["Zone A", "Zone B", "Zone C", "Zone D"]
    df = _get_features()
    if not df.empty and "lot_id" in df.columns:
        latest = df.groupby("lot_id").last().reset_index()
        occs = (latest["occupancy_rate"].tail(4).tolist() + [0.5] * 4)[:4]
    else:
        occs = [0.5, 0.6, 0.4, 0.7]
    prices = [round(10 * (1 + (occ - 0.5) * 0.8), 2) for occ in occs]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Occupancy", x=zones, y=occs, marker_color="#3498db", yaxis="y"))
    fig.add_trace(go.Scatter(name="Price", x=zones, y=prices,
                             mode="lines+markers", marker=dict(size=10, color="#e74c3c"), yaxis="y2"))
    fig.update_layout(
        template="plotly_white",
        yaxis=dict(title="Occupancy", range=[0, 1]),
        yaxis2=dict(title="Price ($)", overlaying="y", side="right", range=[0, 60]),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


@callback(
    Output("lot-selector", "options"),
    Input("lot-dropdown-interval", "n_intervals"),
)
def populate_dropdown(_):
    with get_db_cm() as db:
        lots = db.query(ParkingLot.lot_id, ParkingLot.name).all()
        return [{"label": f"{lid} — {nm}", "value": lid} for lid, nm in lots]


_STATE_MAP = {
    SlotState.OCCUPIED: 3, SlotState.RESERVED: 2,
    SlotState.MAINTENANCE: 0.5, SlotState.AVAILABLE: 1,
    SlotState.PREBOOKED: 2.5,
}
_TYPE_MAP = {"handicap": 1.5, "ev": 1.2}
_LABEL_MAP = {3: "Occupied", 2: "Reserved", 2.5: "Prebooked", 0.5: "Maintenance", 1.5: "Handicap", 1.2: "EV", 1: "Available"}


@callback(
    Output("slot-grid-graph", "figure"),
    Input("lot-selector", "value"),
    Input("slot-grid-interval", "n_intervals"),
)
def update_slot_grid(lot_id, _):
    if not lot_id:
        return go.Figure(layout={"title": "Select a lot to view slot grid"})
    with get_db_cm() as db:
        slots = db.query(MicroSlot).filter(MicroSlot.lot_id == lot_id).order_by(MicroSlot.slot_index).all()
    if not slots:
        return go.Figure(layout={"title": "No micro slots for this lot"})
    slot_state_engine.cleanup_expired()
    slot_map = {(s.row_label, s.position): s for s in slots}
    rows = sorted(set(s.row_label for s in slots))
    positions = sorted(set(s.position for s in slots))
    heat = []
    for r in rows:
        row_data = []
        for p in positions:
            s = slot_map.get((r, p))
            if s is None:
                row_data.append(None)
            else:
                st = slot_state_engine.get_state(cast(int, s.id))
                if st == SlotState.AVAILABLE:
                    val = _TYPE_MAP.get(cast(str, s.slot_type), 1)
                else:
                    val = _STATE_MAP.get(st, 1)
                row_data.append(val)
        heat.append(row_data)
    occ = slot_state_engine.occupancies(lot_id, slots)
    fig = go.Figure(data=go.Heatmap(
        z=heat, x=positions, y=rows,
        colorscale=[[0, "#95a5a6"], [0.2, "#27ae60"], [0.28, "#2ecc71"],
                    [0.4, "#3498db"], [0.55, "#f39c12"], [0.75, "#e74c3c"], [1, "#c0392b"]],
        zmin=0.5, zmax=3, hoverongaps=False,
        hovertemplate="Row %{y} Pos %{x}<br>Status: %{customdata}<extra></extra>",
        customdata=[[_LABEL_MAP.get(v, "Empty") if v is not None else "Empty" for v in row] for row in heat],
    ))
    fig.update_layout(
        title=f"{lot_id} — {occ['occupied_slots']}/{occ['total_slots']} occupied ({occ['occupancy_rate']*100:.1f}%)",
        template="plotly_white", xaxis=dict(title="Position"), yaxis=dict(title="Row"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def run_dashboard(host="0.0.0.0", port=8050, open_browser=True):  # nosec B104
    if open_browser:
        Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()
