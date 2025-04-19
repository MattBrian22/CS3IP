import random
import numpy as np
import requests
import folium
import streamlit as st
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px

# Load environment variables
load_dotenv()

# Fetch the API key securely
API_KEY = os.getenv("TOMTOM_API_KEY2")

# Define the base URL for TomTom Traffic Incident API
TRAFFIC_INCIDENT_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"

# Initialize geolocator for Geopy
geolocator = Nominatim(user_agent="traffic_incident_app")

# Define Icon Categories for Mapping
ICON_CATEGORY_MAP = {
    1: "Accident",
    8: "Road Closed",
    6: "Jam",
    0: "Unknown",
    2: "Fog",
    3: "DangerousConditions",
    4: "Rain",
    5: "Ice",
    7: "LaneClosed",
    9: "RoadWorks",
    10: "Wind",
    11: "Flooding",
    14: "BrokenDownVehicle"
}

# Define color mapping for different incidents
ICON_COLOR_MAP = {
    "Accident": "red",
    "Road Closed": "black",
    "Jam": "orange",
    "Fog": "gray",
    "DangerousConditions": "purple",
    "Rain": "blue",
    "Ice": "blue",
    "LaneClosed": "green",
    "RoadWorks": "yellow",
    "Wind": "brown",
    "Flooding": "cyan",
    "BrokenDownVehicle": "magenta",
    "Unknown": "gray"
}

# ✅ Function to get location coordinates safely
def get_location_coordinates(location_name):
    try:
        location = geolocator.geocode(location_name, exactly_one=True)
        if location:
            return location.latitude, location.longitude
        else:
            st.error(f"⚠️ Unable to find coordinates for {location_name}. Check the city name.")
            return None, None
    except Exception as e:
        st.error(f"⚠️ Geocoding Error: {e}")
        return None, None

# ✅ Function to fetch traffic incidents (real-time data fetch from TomTom)
def fetch_traffic_incidents(api_key, start_lat, start_lon, end_lat, end_lon):
    bbox = f"{start_lon},{start_lat},{end_lon},{end_lat}"  
    params = {
        "key": api_key,  
        "bbox": bbox,  
        "t": "1740485980",  
    }
    
    try:
        response = requests.get(TRAFFIC_INCIDENT_URL, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"🚨 Error fetching traffic incidents: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"🚨 Error fetching traffic incidents: {e}")
        return None

# ✅ Function to clean and process incident data (for real-time data)
def clean_data(traffic_incidents):
    if traffic_incidents is None:
        return []

    cleaned_incidents = []
    incidents = traffic_incidents.get('incidents', [])

    if not incidents:
        return []

    for incident in incidents:
        properties = incident.get('properties', {})
        geometry = incident.get('geometry', {})

        icon_category = properties.get('iconCategory', 'Unknown')
        description = ICON_CATEGORY_MAP.get(icon_category, 'Unknown')

        severity = properties.get('magnitudeOfDelay') or properties.get('delay') or properties.get('impact') or "Not Reported"

        coordinates = geometry.get('coordinates', [])
        if not coordinates:
            continue

        incident_data = {
            'iconCategory': icon_category,
            'type': description,
            'severity': severity,
            'coordinates': coordinates,
            'color': ICON_COLOR_MAP.get(description, 'gray')  
        }

        cleaned_incidents.append(incident_data)

    return cleaned_incidents

# Simulated statistics calculation functions
def calculate_average_accident_rate():
    return random.uniform(0, 100)  # Simulated value between 0% to 100%

def calculate_std_deviation_of_accident_rate():
    return random.uniform(0, 20)  # Simulated value between 0 and 20

def calculate_average_air_particulates():
    return random.uniform(0, 500)  # Simulated value between 0 and 500 µg/m³

def incident():
    # 🚀 **Streamlit UI**
    st.title("🚦 Traffic Incident Data Fetcher")

    # ✅ Sidebar Inputs
    st.sidebar.subheader("📍 Enter Locations")
    start_location = st.sidebar.text_input("🏁 Start Location (City Name)", value="Birmingham")
    end_location = st.sidebar.text_input("🏁 End Location (City Name)", value="Coventry")

    # ✅ Sidebar Form for Decision-Maker's Statistics Selection
    st.sidebar.subheader("📊 Statistics Configuration")
    statistic_types = st.sidebar.multiselect(
        "Select Statistics", 
        ["Average Accident Rate", "Standard Deviation of Accident Rate", "Average Air Particulates"],
        default=["Average Accident Rate"]  # Default selection
    )

    # Add Date Picker for time period
    start_date = st.sidebar.date_input("From Date", pd.to_datetime('2023-01-01'))
    end_date = st.sidebar.date_input("To Date", pd.to_datetime('2023-01-31'))

    # ✅ Initialize session state for the traffic map & incident count
    if "traffic_map" not in st.session_state:
        st.session_state["traffic_map"] = None
    if "total_incidents" not in st.session_state:
        st.session_state["total_incidents"] = None
    if "cleaned_incidents" not in st.session_state:
        st.session_state["cleaned_incidents"] = None

    # 🚀 Fetch Traffic Data Button (real-time traffic incidents)
    if st.sidebar.button("🚨 Fetch Traffic Incidents"):
        start_lat, start_lon = get_location_coordinates(start_location)
        end_lat, end_lon = get_location_coordinates(end_location)

        if start_lat and start_lon and end_lat and end_lon:
            # ✅ Fetch real-time traffic incidents
            traffic_incidents = fetch_traffic_incidents(API_KEY, start_lat, start_lon, end_lat, end_lon)

            if traffic_incidents:
                cleaned_incidents = clean_data(traffic_incidents)
                st.session_state["total_incidents"] = len(cleaned_incidents)  # ✅ Store incident count
                st.session_state["cleaned_incidents"] = cleaned_incidents  # Store cleaned incidents for statistics

                # ✅ Create a Folium map centered at the start location
                traffic_map = folium.Map(location=[start_lat, start_lon], zoom_start=12)

                # ✅ Add markers and polylines with different colors for each type
                for incident in cleaned_incidents:
                    for coord in incident['coordinates']:
                        lat, lon = coord[1], coord[0]
                        folium.PolyLine([(lat, lon)], color=incident['color'], weight=2.5, opacity=1).add_to(traffic_map)

                    first_coord = incident['coordinates'][0]
                    folium.Marker(
                        [first_coord[1], first_coord[0]],
                        popup=f"🚦 Type: {incident['type']}",
                        icon=folium.Icon(color=incident['color'])
                    ).add_to(traffic_map)

                # ✅ Save map in session state
                st.session_state["traffic_map"] = traffic_map

                # **Simulate and display statistics for multiple selected types**
                statistic_values_list = simulate_statistics(statistic_types, start_location, end_location, start_date, end_date)
                display_multiple_bar_charts(statistic_values_list, start_date, end_date)

    # ✅ Display Persistent Incident Count (simulated count)
    if st.session_state["total_incidents"] is not None:
        st.subheader(f"🚧 **Total Incidents Reported:** {st.session_state['total_incidents']}")

    # ✅ Display the updated traffic map
    if st.session_state["traffic_map"]:
        st_folium(st.session_state["traffic_map"], width=700, height=500)

    # ✅ Display the bar chart if it exists in session state
    if "bar_chart" in st.session_state:
        st.plotly_chart(st.session_state["bar_chart"])

    
    # ✅ Display all the bar charts stored in session_state
    display_all_charts()


    # Add Data Source and Timestamp
    st.caption("📊 Data Source: TomTom API")
    st.caption(f"🕒 Last Updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Function to simulate multiple statistics calculations
def simulate_statistics(statistic_types, start_location, end_location, start_date, end_date):
    # Prepare a list to store all statistic values
    statistic_values_list = []

    # # Debugging: Show selected statistics
    # st.write("Selected statistics:", statistic_types)
    
    # Iterate over the selected statistics and calculate for both locations
    for stat_type in statistic_types:
        if stat_type == "Average Accident Rate":
            accident_rate_start = calculate_average_accident_rate()  # Simulated data for start_location
            accident_rate_end = calculate_average_accident_rate()    # Simulated data for end_location
            statistic_values = [
                {"Location": start_location, "Average Accident Rate": accident_rate_start},
                {"Location": end_location, "Average Accident Rate": accident_rate_end},
            ]
            statistic_values_list.append((statistic_values, "Average Accident Rate"))
        
        elif stat_type == "Standard Deviation of Accident Rate":
            std_dev_start = calculate_std_deviation_of_accident_rate()  # Simulated data for start_location
            std_dev_end = calculate_std_deviation_of_accident_rate()    # Simulated data for end_location
            statistic_values = [
                {"Location": start_location, "Standard Deviation of Accident Rate": std_dev_start},
                {"Location": end_location, "Standard Deviation of Accident Rate": std_dev_end},
            ]
            statistic_values_list.append((statistic_values, "Standard Deviation of Accident Rate"))
        
        elif stat_type == "Average Air Particulates":
            air_particulates_start = calculate_average_air_particulates()  # Simulated data for start_location
            air_particulates_end = calculate_average_air_particulates()    # Simulated data for end_location
            statistic_values = [
                {"Location": start_location, "Average Air Particulates (µg/m³)": air_particulates_start},
                {"Location": end_location, "Average Air Particulates (µg/m³)": air_particulates_end},
            ]
            statistic_values_list.append((statistic_values, "Average Air Particulates (µg/m³)"))
    
    # # Debugging: Check if multiple statistics are being added
    # st.write(f"Simulated statistics list: {statistic_values_list}")
    
    return statistic_values_list

# # Function to display multiple bar charts for selected statistics
# def display_multiple_bar_charts(statistic_values_list, start_date, end_date):
#     # Initialize a list to store multiple charts in session_state
#     if "bar_charts" not in st.session_state:
#         st.session_state["bar_charts"] = []

#     # Iterate over all statistic types and generate a bar chart for each
#     for statistic_values, statistic_type in statistic_values_list:
#         # Generate the chart
#         bar_chart = display_bar_chart(statistic_values, statistic_type, start_date, end_date)
        
#         # Append the chart to session_state
#         st.session_state["bar_charts"].append(bar_chart)

# # Function to generate a single bar chart and return it
# def display_bar_chart(statistic_values, statistic_type, start_date, end_date):
#     # Prepare the data for the bar chart
#     chart_data = pd.DataFrame(statistic_values, columns=["Location", statistic_type])

#     # Create a bar chart using plotly.express
#     bar_chart = px.bar(
#         chart_data,
#         x="Location",  # X-axis will show the city names
#         y=statistic_type,  # Y-axis will show the statistic values
#         color="Location",  # Color the bars differently based on Location
#         title=f"{statistic_type} from {start_date} to {end_date}",
#         labels={"Location": "City", statistic_type: f"{statistic_type} Value"},
#     )
    
#     return bar_chart  # Return the chart object

# # # Function to display all the charts stored in session_state
# def display_all_charts():
#     if "bar_charts" in st.session_state:
#         for chart in st.session_state["bar_charts"]:
#             st.plotly_chart(chart)

# Function to display multiple bar charts for selected statistics
def display_multiple_bar_charts(statistic_values_list, start_date, end_date):
    # Clear the previous charts in session_state before appending new ones
    st.session_state["bar_charts"] = []

    # Iterate over all statistic types and generate a bar chart for each
    for statistic_values, statistic_type in statistic_values_list:
        # Generate the chart
        bar_chart = display_bar_chart(statistic_values, statistic_type, start_date, end_date)
        
        # Append the chart to session_state
        st.session_state["bar_charts"].append(bar_chart)

# Function to generate a single bar chart and return it
def display_bar_chart(statistic_values, statistic_type, start_date, end_date):
    # Prepare the data for the bar chart
    chart_data = pd.DataFrame(statistic_values, columns=["Location", statistic_type])

    # Create a bar chart using plotly.express
    bar_chart = px.bar(
        chart_data,
        x="Location",  # X-axis will show the city names
        y=statistic_type,  # Y-axis will show the statistic values
        color="Location",  # Color the bars differently based on Location
        title=f"{statistic_type} from {start_date} to {end_date}",
        labels={"Location": "City", statistic_type: f"{statistic_type} Value"},
    )
    
    return bar_chart  # Return the chart object

# Function to display all the charts stored in session_state
def display_all_charts():
    if "bar_charts" in st.session_state and st.session_state["bar_charts"]:
        st.write(f"Displaying {len(st.session_state['bar_charts'])} charts...")
        for chart in st.session_state["bar_charts"]:
            st.plotly_chart(chart)
    else:
        st.write("No charts to display")

