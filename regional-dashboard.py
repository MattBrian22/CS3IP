import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import requests
import os
from dotenv import load_dotenv  # Required to load .env file locally
from traffic_incident import incident
# from traffic import incident



# Load environment variables from .env file (only needed for local development)
load_dotenv()

# Set up the page configuration
st.set_page_config(
    page_title="Regional Traffic Insights Dashboard",
    layout="wide"
)

# 1. Header Section
st.title("Regional Traffic Insights Dashboard")
st.write("Analyze and visualize traffic patterns across the West Midlands in real-time and historically.")

# 2. Sidebar for User Filters
st.sidebar.header("Filters")
refresh_button = st.sidebar.button("Refresh Data")
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 60, 10)

# TomTom API details
# API_KEY = "gYN70IBMm6wQHSAbWpiemuWyEeNIMYUj"
API_KEY = os.getenv("TOMTOM_API_KEY2")
URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"

# West Midlands locations (static list of key cities)
locations = {
    "Birmingham": "52.4862,-1.8904",
    "Coventry": "52.4081,-1.5100",
    "Wolverhampton": "52.5862,-2.1275",
    "Solihull": "52.4128,-1.7782",
    "Walsall": "52.5860,-1.9829",
    "Dudley": "52.5087,-2.0873",
    "Sandwell": "52.5090,-2.0125"
}

# Function to fetch real-time traffic data from TomTom API for multiple locations
def fetch_west_midlands_data():
    results = []
    for name, coord in locations.items():
        params = {
            "key": API_KEY,
            "point": coord,
            "zoom": 10  # Adjust zoom level as needed
        }
        try:
            response = requests.get(URL, params=params)
            if response.status_code == 200:
                data = response.json()
                lat, lon = map(float, coord.split(","))
                results.append({
                    "Location": name,
                    "Current Speed": data["flowSegmentData"]["currentSpeed"],
                    "Free Flow Speed": data["flowSegmentData"]["freeFlowSpeed"],
                    "Confidence": data["flowSegmentData"]["confidence"],
                    "Road Closure": data["flowSegmentData"].get("roadClosure", "No"),
                    "Latitude": lat,
                    "Longitude": lon
                })
            else:
                st.error(f"API Error for {name}: {response.status_code}")
        except Exception as e:
            st.error(f"Error fetching data for {name}: {e}")
    return pd.DataFrame(results)

# Fetch data on refresh
if refresh_button or "data" not in st.session_state:
    data = fetch_west_midlands_data()
    st.session_state["data"] = data
else:
    data = st.session_state["data"]

# Display KPIs
st.header("Traffic Insights Overview")
if not data.empty:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Average Speed", f"{data['Current Speed'].mean():.2f} km/h")
    col2.metric("Free Flow Speed", f"{data['Free Flow Speed'].mean():.2f} km/h")
    col3.metric("Confidence", f"{data['Confidence'].mean() * 100:.2f}%")
    # col4.metric("Road Closures", data['Road Closure'].sum())

    # Traffic Trends
    st.subheader("Traffic Trends")
    trend_chart = px.bar(
        data,
        x="Location",
        y="Current Speed",
        color="Location",
        title="Current Speed by Location"
    )
    st.plotly_chart(trend_chart, use_container_width=True)

        # Congestion Heatmap
    st.subheader("Congestion Heatmap")

    # Calculate congestion level
    data["Congestion Level"] = (
        (data["Free Flow Speed"] - data["Current Speed"]) / data["Free Flow Speed"]
    ).clip(lower=0).round(2)

    # Filter out any rows with invalid or missing coordinates to ensure smooth rendering
    valid_data = data.dropna(subset=["Latitude", "Longitude"])

    # Create a scatter mapbox heatmap
    heatmap = px.scatter_mapbox(
        valid_data,  # Use the filtered data
        lat="Latitude",
        lon="Longitude",
        color="Congestion Level",
        size="Congestion Level",
        color_continuous_scale=px.colors.sequential.Inferno,  # High contrast
        size_max=50,  # Set max size for bubble markers
        hover_name="Location",  # Add location name to hover info
        hover_data={
            "Current Speed": ":.2f",  # Show current speed
            "Free Flow Speed": ":.2f",  # Show free flow speed
            "Congestion Level": ":.2f"  # Show congestion level
        },
        title="Congestion Heatmap",
        mapbox_style="open-street-map",  # Higher-contrast style
        zoom=9,  # Adjust zoom for better view of the region
        center={"lat": 52.4862, "lon": -1.8904}  # Center the map on Birmingham
    )

    # Display the heatmap with updated settings
    st.plotly_chart(heatmap, use_container_width=True)

# Footer
st.write("---")
st.caption("Data Source: TomTom API")
st.caption(f"Last Updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")


# 🚀 Sidebar Navigation for Dashboard Selection
model_selection = st.sidebar.selectbox(
    "Select Dashboard Mode",
    ["📊 Regional Traffic Insights", "🚨 Real-Time Traffic Incidents"]
)

# ✅ Load the selected dashboard dynamically
if model_selection == "📊 Regional Traffic Insights":
    pass  # Placeholder for the main traffic insights dashboard
elif model_selection == "🚨 Real-Time Traffic Incidents":
    incident()  # ✅ Calls the incident() function dynamically

