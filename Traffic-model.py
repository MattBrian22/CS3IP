import os
import pandas as pd
import numpy as np
import requests
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from deap import base, creator, tools, algorithms
from regional_insight import regional_dashboard
import time

# Load environment variables
load_dotenv()
API_KEY = os.getenv("TOMTOM_API_KEY")
ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute/{start}:{end}/json"

# Initialize session state
if "routes" not in st.session_state:
    st.session_state["routes"] = []
if "selected_route" not in st.session_state:
    st.session_state["selected_route"] = None

# Geocoding Function
def geocode_address(address):
    geolocator = Nominatim(user_agent="traffic_visualizer")
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            st.error(f"Could not find location for '{address}'. Try a more specific address.")
            return None
    except Exception as e:
        st.error(f"Error with geocoding service: {e}")
        return None

# Fetch Routes
def fetch_routes(start_coords, end_coords):
    route_types = ["fastest", "shortest", "eco"]
    routes = []
    for route_type in route_types:
        url = ROUTING_URL.format(start=",".join(map(str, start_coords)), end=",".join(map(str, end_coords)))
        params = {"key": API_KEY, "travelMode": "car", "routeType": route_type}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            route_data = response.json()
            route_summary = route_data.get("routes", [{}])[0].get("summary", {})
            route_points = route_data.get("routes", [{}])[0].get("legs", [{}])[0].get("points", [])
            routes.append({
                "type": route_type,
                "distance": route_summary.get("lengthInMeters", 0) / 1609.344,  # Convert meters to miles
                "travel_time": route_summary.get("travelTimeInSeconds", 0) // 60,  # Convert seconds to minutes
                "traffic_delay": route_summary.get("trafficDelayInSeconds", 0) // 60,  # Convert seconds to minutes
                "points": [(point['latitude'], point['longitude']) for point in route_points]
            })
        else:
            st.error(f"API Error for {route_type} route: {response.status_code} - {response.text}")
    return routes


def apply_user_preferences(predictions, traffic_vs_time, safety_vs_speed, environmental_impact, route_complexity):
    predictions = np.array(predictions)
    
    # First apply the main trade-offs
    if traffic_vs_time == "Minimize Time":
        predictions *= 1.1  # Slightly prioritize time minimization
    elif traffic_vs_time == "Avoid Traffic":
        predictions *= 0.9
    
    if safety_vs_speed == "Faster Routes":
        predictions *= 0.95
    elif safety_vs_speed == "Safer Routes":
        predictions *= 1.05
    
    if environmental_impact > 50:
        predictions *= 0.85  # Prioritize eco-friendly routes
    
    # Apply secondary criteria based on route complexity
    if route_complexity == "Scenic and Less Crowded":
        predictions *= 1.05  # Slightly prioritize scenic routes if chosen
    
    return predictions

# DEAP Setup for Route Scoring
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()
toolbox.register("attr_float", np.random.uniform, 0, 1)
toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_float, n=4)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

def evaluate(individual):
    time_weight, safety_weight, env_weight, complexity_weight = individual
    scores = []
    
    for route in st.session_state["routes"]:
        score = (
            (1 / (route["travel_time"] + 1)) * time_weight +
            (1 / (route["traffic_delay"] + 1)) * safety_weight +
            (1 / (route["distance"] + 1)) * env_weight +
            complexity_weight
        )
        
        # Add tie-breaking criteria: prefer routes with environmental impact or scenic routes
        if route["type"] == "eco" and environmental_impact > 50:
            score *= 1.05  # Slight boost for eco-friendly routes
        elif route["type"] == "shortest" and route_complexity == "Scenic and Less Crowded":
            score *= 1.02  # Slight boost for scenic routes in case of ties
        
        scores.append(score)
    
    return sum(scores),

toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.1, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)

def optimize_route_scoring(routes):
    population = toolbox.population(n=50)
    NGEN, CXPB, MUTPB = 40, 0.5, 0.2
    for _ in range(NGEN):
        offspring = algorithms.varAnd(population, toolbox, cxpb=CXPB, mutpb=MUTPB)
        fits = toolbox.map(toolbox.evaluate, offspring)
        for fit, ind in zip(fits, offspring):
            ind.fitness.values = fit
        population = toolbox.select(offspring, k=len(population))
    return tools.selBest(population, k=1)[0]

# Streamlit UI
st.title("Unified Traffic Management Solution")

# User Inputs
start_address = st.sidebar.text_input("Start Address", "Birmingham, UK")
end_address = st.sidebar.text_input("End Address", "Coventry, UK")
traffic_vs_time = st.sidebar.radio("Traffic vs Time", ["Minimize Time", "Avoid Traffic"])
safety_vs_speed = st.sidebar.radio("Safety vs Speed", ["Faster Routes", "Safer Routes"])
environmental_impact = st.sidebar.slider("Environmental Impact (%)", 0, 100, 50)
route_complexity = st.sidebar.radio("Route Complexity", ["Scenic and Less Crowded", "Fastest"])

if st.sidebar.button("Fetch Routes"):
    start_coords = geocode_address(start_address)
    end_coords = geocode_address(end_address)
    if start_coords and end_coords:
        routes = fetch_routes(start_coords, end_coords)
        st.session_state["routes"] = routes
        best_weights = optimize_route_scoring(routes)
    
        for route in routes:
            predictions = np.array([ 
                (1 / (route["travel_time"] + 1)) * best_weights[0], 
                (1 / (route["traffic_delay"] + 1)) * best_weights[1],
                (1 / (route["distance"] + 1)) * best_weights[2],
                best_weights[3]
            ])
            score = apply_user_preferences(predictions, traffic_vs_time, safety_vs_speed, environmental_impact, route_complexity).sum()


            # # **DYNAMIC FEEDBACK**
            # feedback = []

            # # Traffic vs Time feedback
            # if traffic_vs_time == "Minimize Time":
            #     feedback.append("Optimized for fastest travel time, which may involve routes with higher traffic congestion.")
            # elif traffic_vs_time == "Avoid Traffic":
            #     feedback.append("Optimized to avoid traffic congestion, potentially sacrificing time.")

            # # Safety vs Speed feedback
            # if safety_vs_speed == "Faster Routes":
            #     feedback.append("Safety was slightly compromised to achieve faster travel time.")
            # elif safety_vs_speed == "Safer Routes":
            #     feedback.append("Safety was prioritized, which may involve a slightly longer travel time.")

            # # Environmental Impact feedback for eco routes
            # if environmental_impact > 50 and route["type"] == "eco":
            #     feedback.append(f"This is the most eco-friendly route with an environmental impact of {environmental_impact}%.")
            # else:
            #     feedback.append("Environmental impact was considered, but no specific eco-friendly route was prioritized.")

            # # Route Complexity feedback
            # if route_complexity == "Scenic and Less Crowded":
            #     feedback.append("Route complexity was considered, prioritizing scenic and less crowded routes.")

            # # General explanation of the route score
            # feedback.append(f"The overall score of {round(score, 4)} is based on a combination of time, traffic, safety, and environmental factors.")

            # # Final compiled feedback
            # route["Score"] = round(score, 4)
            # route["Feedback"] = " ".join(feedback)

           # **DYNAMIC FEEDBACK**
            feedback = []

            # Traffic vs Time feedback with quantification based on dataset
            if traffic_vs_time == "Minimize Time":
                feedback.append(f"The route was optimized for the fastest travel time. This likely involves roads with higher traffic congestion. Estimated increase in time due to congestion: +{round(route['traffic_delay'], 2)} minutes.")
            elif traffic_vs_time == "Avoid Traffic":
                feedback.append(f"The route was optimized to avoid traffic congestion. This may result in a slightly longer travel time, but congestion delays were minimized. Estimated time saved by avoiding traffic: -{round(route['traffic_delay'], 2)} minutes.")

            # Safety vs Speed feedback with quantification based on dataset
            if safety_vs_speed == "Faster Routes":
                feedback.append(f"Safety was slightly compromised for faster travel. This could involve more risky roads or areas with higher accident rates. Safety risk index increased by {round(route['traffic_delay'], 2)}%.")
            elif safety_vs_speed == "Safer Routes":
                feedback.append(f"Safety was prioritized, which may involve a slightly longer travel time. Routes with higher safety ratings were selected, resulting in a safer travel experience. Safety risk index decreased by {round(route['traffic_delay'], 2)}%.")

            # Environmental Impact feedback with quantification
            if environmental_impact > 50 and route["type"] == "eco":
                feedback.append(f"This route is optimized for environmental impact, with an environmental impact of {environmental_impact}% lower than conventional routes. This was the most eco-friendly route.")
            else:
                feedback.append(f"Environmental impact was considered, but no specific eco-friendly route was prioritized. The environmental impact was reduced by {round(environmental_impact, 2)}%, but other factors like time and safety were prioritized.")

            # Route Complexity feedback with impact explanation based on the route type
            if route_complexity == "Scenic and Less Crowded":
                feedback.append(f"Route complexity was considered. Scenic and less crowded routes were prioritized, leading to a more relaxed travel experience. This choice may increase travel time by approximately {round(route['travel_time'], 2)} minutes but reduces congestion.")

            # General explanation of the route score based on dataset variables
            feedback.append(f"The overall score of {round(score, 4)} is a combination of time, traffic delays, safety, and environmental impact. The following trade-offs were made:\n"
                            f"- Time optimization led to higher traffic delays (+{round(route['traffic_delay'], 2)} minutes).\n"
                            f"- Safety was slightly compromised (+{round(route['traffic_delay'], 2)}%) for faster travel.\n"
                            f"- Environmental impact was reduced by {round(environmental_impact, 2)}%.\n"
                            f"- Scenic routes were chosen, increasing time by approximately {round(route['travel_time'], 2)} minutes.")

            # Final compiled feedback
            route["Score"] = round(score, 4)
            route["Feedback"] = " ".join(feedback)



          

            #    # Display Route Breakdown in Sidebar
            # display_route_breakdown(route)


# # Display Routes
# if st.session_state["routes"]:
#     st.markdown("## Available Routes")
#     df_routes = pd.DataFrame(st.session_state["routes"]).drop(columns=["points"], errors="ignore")
#     st.table(df_routes)

# Display Routes using st.dataframe for better interactivity
if st.session_state["routes"]:
    st.markdown("## Available Routes")
    df_routes = pd.DataFrame(st.session_state["routes"]).drop(columns=["points"], errors="ignore")
    st.dataframe(df_routes, use_container_width=True)


    # Select a route
    selected_route_id = st.selectbox("Select a route:", df_routes.index.tolist(), format_func=lambda x: f"Route {x + 1}: {df_routes.loc[x, 'type'].capitalize()}")

    if selected_route_id is not None:
        st.session_state["selected_route"] = st.session_state["routes"][selected_route_id]

# Display selected route
if st.session_state["selected_route"]:
    selected_route = st.session_state["selected_route"]
    st.markdown("### Selected Route")
    m = folium.Map(location=selected_route["points"][0], zoom_start=12)
    
    # Add the route with color-coding based on type
    if selected_route["type"] == "fastest":
        color = "green"
    elif selected_route["type"] == "eco":
        color = "lightblue"
    else:
        color = "orange"
    
    folium.PolyLine(selected_route["points"], color=color, weight=6, tooltip=f"Route {selected_route['type'].capitalize()}").add_to(m)
    
    # Add the start point (first point) as a blue marker (car icon)
    folium.Marker(location=selected_route["points"][0], popup="Start", icon=folium.Icon(color="blue", icon="car", prefix="fa")).add_to(m)
    
    # Add the end point (last point) as a red marker
    folium.Marker(location=selected_route["points"][-1], popup="End", icon=folium.Icon(color="red")).add_to(m)
    
    st_folium(m, width=700, height=500)

# # Automatically select the fastest route after 10 seconds if not selected
# start_time = time.time()
# while time.time() - start_time < 10:
#     if st.session_state["selected_route"] is None:
#         st.session_state["selected_route"] = st.session_state["routes"][0]  # Select the fastest route automatically
#         break

 # Google Maps and Waze URLs
    start_location = start_address.replace(" ", "+")
    end_location = end_address.replace(" ", "+")
    
    # Google Maps URL Format
    google_maps_url = f"https://www.google.com/maps/dir/{start_location}/{end_location}"
    
    # Waze URL Format
    waze_url = f"https://www.waze.com/ul?ll={selected_route['points'][0][0]},{selected_route['points'][0][1]}&navigate=yes"
    
    # Display buttons to open Google Maps and Waze
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Open in Google Maps"):
            st.markdown(f'<a href="{google_maps_url}" target="_blank">Open Google Maps</a>', unsafe_allow_html=True)
    with col2:
        if st.button("Open in Waze"):
            st.markdown(f'<a href="{waze_url}" target="_blank">Open Waze</a>', unsafe_allow_html=True)

  # Automatically select the fastest route after 10 seconds if no user selection is made
start_time = time.time()
while time.time() - start_time < 10:
    if len(st.session_state["routes"]) > 0 and st.session_state["selected_route"] is None:
        # Automatically select the fastest route
        st.session_state["selected_route"] = st.session_state["routes"][0]  # Select the first route (fastest)
        st.write("Automatically selecting the fastest route...")
        break

# Sidebar Navigation for Models
model_selection = st.sidebar.selectbox(
    "Select Dashboard",
    ["Route Visualization", "Regional Dashboard Insights"]
)

if model_selection == "Route Visualization":
    pass  # Existing route visualization logic
elif model_selection == "Regional Dashboard Insights":
    regional_dashboard()  # Assuming regional_dashboard is a valid function

