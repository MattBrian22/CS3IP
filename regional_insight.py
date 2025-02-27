import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# TomTom API Configuration
API_KEY = os.getenv("TOMTOM_API_KEY2")
URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"

# Static locations for the West Midlands
locations = {
    "Birmingham": "52.4862,-1.8904",
    "Coventry": "52.4081,-1.5100",
    "Wolverhampton": "52.5862,-2.1275",
    "Solihull": "52.4128,-1.7782",
    "Walsall": "52.5860,-1.9829",
    "Dudley": "52.5087,-2.0873",
    "Sandwell": "52.5090,-2.0125"
}

# Fetch traffic data function
def fetch_west_midlands_data():
    results = []
    for name, coord in locations.items():
        params = {
            "key": API_KEY,
            "point": coord,
            "zoom": 10
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

# Main function for the dashboard
def regional_dashboard():
    st.title("Regional Traffic Insights Dashboard")
    st.write("Analyze and visualize traffic patterns across the West Midlands in real-time and historically.")

    # Sidebar controls
    st.sidebar.header("Filters")
    refresh_button = st.sidebar.button("Refresh Data")
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 60, 10)

    # Fetch data on refresh or session state
    if refresh_button or "data" not in st.session_state:
        data = fetch_west_midlands_data()
        st.session_state["data"] = data
    else:
        data = st.session_state["data"]

    # Display KPIs and visualizations
    if not data.empty:
        st.header("Traffic Insights Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Average Speed", f"{data['Current Speed'].mean():.2f} km/h")
        col2.metric("Free Flow Speed", f"{data['Free Flow Speed'].mean():.2f} km/h")
        col3.metric("Confidence", f"{data['Confidence'].mean() * 100:.2f}%")

        st.subheader("Traffic Trends")
        trend_chart = px.bar(
            data, x="Location", y="Current Speed", color="Location",
            title="Current Speed by Location"
        )
        st.plotly_chart(trend_chart, use_container_width=True)

        st.subheader("Congestion Heatmap")
        data["Congestion Level"] = (
            (data["Free Flow Speed"] - data["Current Speed"]) / data["Free Flow Speed"]
        ).clip(lower=0).round(2)

        valid_data = data.dropna(subset=["Latitude", "Longitude"])
        heatmap = px.scatter_mapbox(
            valid_data,
            lat="Latitude", lon="Longitude",
            color="Congestion Level", size="Congestion Level",
            color_continuous_scale=px.colors.sequential.Inferno,
            hover_name="Location",
            title="Congestion Heatmap",
            mapbox_style="open-street-map", zoom=9,
            center={"lat": 52.4862, "lon": -1.8904}
        )
        st.plotly_chart(heatmap, use_container_width=True)

        st.subheader("Interactive Map")
        map_center = [52.4862, -1.8904]
        m = folium.Map(location=map_center, zoom_start=9)
        for _, row in data.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=(
                    f"Location: {row['Location']}<br>"
                    f"Current Speed: {row['Current Speed']} km/h<br>"
                    f"Free Flow Speed: {row['Free Flow Speed']} km/h<br>"
                    f"Confidence: {row['Confidence'] * 100:.2f}%"
                ),
                icon=folium.Icon(color="blue")
            ).add_to(m)
        st_folium(m, width=700, height=500)

    else:
        st.warning("No data available. Click 'Refresh Data' to fetch traffic information.")

    st.caption("Data Source: TomTom API")
    st.caption(f"Last Updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")


# import pandas as pd
# import plotly.express as px
# import folium
# from folium.plugins import HeatMap

# # Generate regional traffic summary
# def generate_traffic_summary(df):
#     summary = {
#         "Average Speed (km/h)": df["speed"].mean(),
#         "Peak Congestion (%)": df["congestion"].max(),
#         "Low Congestion (%)": df["congestion"].min(),
#     }
#     return summary

# # Generate traffic trends (e.g., speed by location)
# def generate_traffic_trends(df):
#     fig = px.bar(
#         df,
#         x="location",
#         y="speed",
#         title="Current Speed by Location",
#         labels={"speed": "Speed (km/h)", "location": "Location"}
#     )
#     return fig

# # Generate congestion heatmap
# def generate_congestion_heatmap(df):
#     heatmap_data = df[["latitude", "longitude", "congestion"]].values.tolist()
#     m = folium.Map(location=[df["latitude"].mean(), df["longitude"].mean()], zoom_start=12)
#     HeatMap(heatmap_data, min_opacity=0.5, radius=15).add_to(m)
#     return m
