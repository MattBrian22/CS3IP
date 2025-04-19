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
import random
import time

# Initialize session state if they don't exist
if "routes" not in st.session_state:
    st.session_state["routes"] = []

if "selected_route" not in st.session_state:
    st.session_state["selected_route"] = None

# Load environment variables
load_dotenv()
API_KEY = os.getenv("TOMTOM_API_KEY")
ROUTING_URL = "https://api.tomtom.com/routing/1/calculateRoute/{start}:{end}/json"

# Simulate historical data for congestion, accidents, and air quality
def simulate_historical_data(time_of_day):
    """
    Simulate historical data for congestion, accident rates, and air quality.
    """
    # Simulate historical congestion data (in percentage)
    congestion_patterns = {
        "morning": random.uniform(70, 90),  # Higher congestion during morning rush hours
        "afternoon": random.uniform(40, 60),  # Afternoon less congestion
        "evening": random.uniform(50, 80),  # Evening congestion peaks
        "night": random.uniform(10, 30),  # Low congestion at night
    }
    
    # Simulate historical accident data (in percentage)
    accident_patterns = {
        "morning": random.uniform(0.2, 0.5),  # More accidents in the morning rush hour
        "afternoon": random.uniform(0.1, 0.3),  # Fewer accidents in the afternoon
        "evening": random.uniform(0.3, 0.6),  # Evening could be risky as well
        "night": random.uniform(0, 0.1),  # Fewer accidents at night
    }
    
    # Simulate historical air quality (AQI index)
    air_quality_patterns = {
        "morning": random.uniform(50, 100),  # Worse air quality during peak hours
        "afternoon": random.uniform(30, 60),  # Moderate air quality
        "evening": random.uniform(40, 90),  # Pollution peaks again in the evening
        "night": random.uniform(10, 30),  # Air quality improves at night
    }
    
    congestion = congestion_patterns.get(time_of_day, random.uniform(30, 70))
    accidents = accident_patterns.get(time_of_day, random.uniform(0.1, 0.3))
    air_quality = air_quality_patterns.get(time_of_day, random.uniform(20, 60))

    return congestion, accidents, air_quality

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

# Apply historical data to routes
def apply_historical_data_to_routes(routes):
    """
    Apply simulated historical data to the routes to adjust their scores.
    """
    for route in routes:
        # Assume the routes take place during different times of day
        time_of_day = random.choice(["morning", "afternoon", "evening", "night"])
        
        # Simulate historical data for the given time of day
        congestion_data, accident_data, air_quality_data = simulate_historical_data(time_of_day)
        
        # Apply congestion data to adjust travel time
        route["adjusted_travel_time"] = route["travel_time"] * (1 + (congestion_data / 100))

        # Apply accident risk: higher accident rate may increase travel time (safety factor)
        route["adjusted_travel_time"] += route["travel_time"] * (accident_data / 100)
        
        # Apply air quality factor: worse air quality may affect the eco-score (lower is better)
        route["eco_score"] = max(0, 100 - air_quality_data)

        # Generate a combined score based on adjusted travel time and eco score
        route["total_score"] = route["adjusted_travel_time"] - route["eco_score"]

    return routes

# Apply User Preferences to Final Predictions
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
creator.create("FitnessMax", base.Fitness, weights=(1.0, ))
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
            (1 / (route["adjusted_travel_time"] + 1)) * time_weight +
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
st.title("Computational Intelligence Routing")

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

        # Apply simulated historical data to routes
        updated_routes = apply_historical_data_to_routes(routes)

        st.session_state["routes"] = updated_routes
        best_weights = optimize_route_scoring(updated_routes)

        # Calculate the score for each route
        for route in updated_routes:
            predictions = np.array([ 
                (1 / (route["adjusted_travel_time"] + 1)) * best_weights[0], 
                (1 / (route["traffic_delay"] + 1)) * best_weights[1],
                (1 / (route["distance"] + 1)) * best_weights[2],
                best_weights[3]
            ])
            score = apply_user_preferences(predictions, traffic_vs_time, safety_vs_speed, environmental_impact, route_complexity).sum()

            # Add feedback based on the adjustments made by the simulated data
            feedback = []
            feedback.append(f"The route was optimized for the fastest travel time. Congestion increased time by +{round(route['traffic_delay'], 2)} minutes.")
            feedback.append(f"Safety was adjusted by considering accident rates. Safety risk increased by {round(route['traffic_delay'], 2)}%.")
            feedback.append(f"Air quality factor was considered for the eco-friendly score.")
            route["Score"] = round(score, 4)
            route["Feedback"] = " ".join(feedback)

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

