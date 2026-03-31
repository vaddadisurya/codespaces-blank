import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Building 59 - Asset Command Center", layout="wide")

# Custom CSS to make the "Widget Squares" look like a real dashboard container
st.markdown("""
    <style>
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    div[data-testid="stMetricLabel"] { font-size: 0.9rem; color: #888; }
    .asset-card { border: 1px solid #333; padding: 15px; border-radius: 8px; margin-bottom: 20px; background-color: #0e1117;}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA MOCKING (Replace with your Azure Blob Fetcher) ---
# For demonstration, we simulate granular, machine-level data coming from your data lake
def get_machine_telemetry(sector):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if sector == "HVAC & Air Handling":
        return [
            {"id": "AHU-EastWing-01", "name": "Main Air Handler (East)", "loc": "Roof Deck - East", "status": "Online", "last_seen": now, "oee": 92.1, "mttr": "2.4h", "mtbf": "5120h", "metric_name": "Filter Resistance (Pa)", "current_val": 240, "thresh": 300, "trend": np.linspace(150, 240, 10) + np.random.normal(0, 5, 10)},
            {"id": "VAV-Floor2-04", "name": "Variable Air Volume Box", "loc": "Floor 2 - Open Office", "status": "Warning", "last_seen": now, "oee": 74.3, "mttr": "1.1h", "mtbf": "840h", "metric_name": "Damper Actuator Latency (ms)", "current_val": 850, "thresh": 1000, "trend": np.linspace(400, 850, 10) + np.random.normal(0, 20, 10)}
        ]
    elif sector == "Pumps & Plant":
        return [
            {"id": "HWP-Basement-01", "name": "Primary Hot Water Pump", "loc": "Basement Mech Room", "status": "Critical", "last_seen": now, "oee": 45.0, "mttr": "4.5h", "mtbf": "2100h", "metric_name": "Bearing Vibration (mm/s)", "current_val": 7.8, "thresh": 8.0, "trend": np.linspace(2.0, 7.8, 10) + np.random.normal(0, 0.2, 10)},
            {"id": "CHWP-Basement-02", "name": "Chilled Water Pump", "loc": "Basement Mech Room", "status": "Online", "last_seen": now, "oee": 98.5, "mttr": "3.2h", "mtbf": "6500h", "metric_name": "Bearing Vibration (mm/s)", "current_val": 2.1, "thresh": 8.0, "trend": np.linspace(2.0, 2.1, 10) + np.random.normal(0, 0.1, 10)}
        ]
    elif sector == "Electrical & Lighting":
        return [
            {"id": "MDP-Main-01", "name": "Main Distribution Panel", "loc": "Ground Floor Electrical", "status": "Online", "last_seen": now, "oee": 99.9, "mttr": "0.5h", "mtbf": "12000h", "metric_name": "Phase Imbalance (%)", "current_val": 1.2, "thresh": 5.0, "trend": np.linspace(1.0, 1.2, 10) + np.random.normal(0, 0.1, 10)},
            {"id": "LC-Floor3-01", "name": "Lighting Controller", "loc": "Floor 3 - IT Closet", "status": "Offline", "last_seen": (datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"), "oee": 0.0, "mttr": "1.5h", "mtbf": "3000h", "metric_name": "Ghost Lighting Alerts", "current_val": 14, "thresh": 5, "trend": np.linspace(0, 14, 10)}
        ]
    return []

# --- 3. THE WIDGET RENDERER (Consistent across all sectors) ---
def render_predictive_sparkline(trend_data, current_val, threshold, metric_name):
    """Generates a small, clean predictive chart for the widget square."""
    fig = go.Figure()
    # Historical Trend
    fig.add_trace(go.Scatter(y=trend_data, mode='lines', name='History', line=dict(color='#0078D4', width=2)))
    
    # Simple Linear Projection (Predictive Maintenance)
    slope = (trend_data[-1] - trend_data[0]) / len(trend_data)
    projection = [current_val + (slope * i) for i in range(1, 6)]
    fig.add_trace(go.Scatter(x=list(range(len(trend_data)-1, len(trend_data)+4)), y=[trend_data[-1]] + projection, mode='lines', name='Forecast', line=dict(color='#FF8C00', dash='dash', width=2)))
    
    # Failure Threshold
    fig.add_hline(y=threshold, line_dash="dot", line_color="#D13438", annotation_text="Limit")
    
    fig.update_layout(
        height=150, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_machine_card(machine):
    """The master widget square template."""
    st.markdown(f"### {machine['name']}")
    st.caption(f"**ID:** {machine['id']} | **Location:** {machine['loc']} | **Last Online:** {machine['last_seen']}")
    
    # Status Indicator
    if machine['status'] == "Online": st.success("🟢 STATUS: ONLINE & HEALTHY")
    elif machine['status'] == "Warning": st.warning("🟡 STATUS: DEGRADATION DETECTED")
    else: st.error(f"🔴 STATUS: {machine['status'].upper()} / OFFLINE")

    # Metrics Grid
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current OEE", f"{machine['oee']}%")
    c2.metric("MTTR", machine['mttr'])
    c3.metric("MTBF", machine['mtbf'])
    
    # Calculate RUL based on trend
    slope = (machine['trend'][-1] - machine['trend'][0]) / len(machine['trend'])
    rul = round((machine['thresh'] - machine['current_val']) / slope, 1) if slope > 0.01 else "> 30"
    c4.metric("Predicted RUL", f"{rul} Days" if isinstance(rul, float) else rul)

    # Predictive Chart
    st.markdown(f"**Predictive Analytics:** {machine['metric_name']}")
    st.plotly_chart(render_predictive_sparkline(machine['trend'], machine['current_val'], machine['thresh'], machine['metric_name']), use_container_width=True)
    st.markdown("---")


# --- 4. DASHBOARD UI ---
st.sidebar.title("🏢 Building 59")
st.sidebar.caption("Asset Level Command Center")
selected_sector = st.sidebar.selectbox("Filter by Sector", ["HVAC & Air Handling", "Pumps & Plant", "Electrical & Lighting"])

st.title(f"Sector: {selected_sector}")
st.markdown("Individual asset telemetry, reliability metrics, and predictive forecasts.")

# Fetch granular data and render a card for EVERY machine
machines_in_sector = get_machine_telemetry(selected_sector)

if not machines_in_sector:
    st.info("No active equipment found in this sector.")
else:
    # Use columns to create a grid (2 machines per row)
    for i in range(0, len(machines_in_sector), 2):
        col_left, col_right = st.columns(2)
        
        with col_left:
            render_machine_card(machines_in_sector[i])
            
        with col_right:
            if i + 1 < len(machines_in_sector):
                render_machine_card(machines_in_sector[i+1])