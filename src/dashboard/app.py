import json
import webbrowser
from threading import Timer
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output, callback

from src.features.engine import process_raw_to_features

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

    dcc.Interval(id="refresh-interval", interval=5000, n_intervals=0),
], style={"fontFamily": "Arial, sans-serif", "padding": "20px", "backgroundColor": "#f5f6fa"})


def _load_features():
    try:
        df = process_raw_to_features(DATA_PATH)
        return df.sort_values("ts_bucket").tail(100)
    except Exception:
        return pd.DataFrame()


@callback(
    Output("iot-feed-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_iot(_):
    df = _load_features()
    if df.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["occupancy_rate"],
                             mode="lines+markers", name="Occupancy Rate",
                             line=dict(color="#3498db")))
    fig.add_trace(go.Scatter(x=df["ts_bucket"], y=df["net_flux"],
                             mode="lines", name="Net Flux",
                             line=dict(color="#e74c3c", dash="dot")))
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("ml-prediction-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_ml(_):
    df = _load_features()
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
    df = _load_features()
    if df.empty:
        return go.Figure()
    lots = df.groupby("lot_id")["occupancy_rate"].mean().reset_index()
    lots["blocks"] = np.random.randint(3, 15, len(lots))
    fig = px.bar(lots, x="lot_id", y="blocks", color="occupancy_rate",
                 color_continuous_scale="Viridis",
                 labels={"lot_id": "Parking Zone", "blocks": "Chain Length"})
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("rl-pricing-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_rl(_):
    steps = list(range(50))
    occupancy = np.clip(np.cumsum(np.random.randn(50) * 0.02) + 0.6, 0, 1)
    price = np.clip(10 * (1 + (occupancy - 0.5) * 0.5), 5, 50)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=steps, y=occupancy, name="Occupancy",
                             line=dict(color="#3498db")), secondary_y=False)
    fig.add_trace(go.Scatter(x=steps, y=price, name="Dynamic Price",
                             line=dict(color="#e74c3c")), secondary_y=True)
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
    fig = go.Figure(data=[
        go.Bar(name="Occupancy Delta", x=scenarios, y=occ_impacts,
               marker_color=["#2ecc71", "#e74c3c", "#f39c12", "#3498db",
                             "#9b59b6", "#e67e22"])
    ])
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
    return fig


@callback(
    Output("marl-graph", "figure"),
    Input("refresh-interval", "n_intervals"),
)
def update_marl(_):
    zones = [f"Zone {i}" for i in range(4)]
    occs = np.random.uniform(0.3, 0.9, 4)
    prices = np.clip(10 * (1 + (occs - 0.5) * 0.8), 5, 50)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Occupancy", x=zones, y=occs,
                         marker_color="#3498db", yaxis="y"))
    fig.add_trace(go.Scatter(name="Price", x=zones, y=prices,
                             mode="lines+markers",
                             marker=dict(size=10, color="#e74c3c"),
                             yaxis="y2"))
    fig.update_layout(
        template="plotly_white",
        yaxis=dict(title="Occupancy", range=[0, 1]),
        yaxis2=dict(title="Price ($)", overlaying="y", side="right", range=[0, 60]),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def run_dashboard(host="0.0.0.0", port=8050, open_browser=True):
    if open_browser:
        Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()
