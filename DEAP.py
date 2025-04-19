import operator
import random
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from deap import base, creator, tools, gp
from deap import algorithms
from sklearn.model_selection import train_test_split
import csv
import os


# Step 1: Load the dataset
file_path = r"C:\Users\brian\Downloads\classified-counts_from_2024-11-11_to_2024-11-11.csv"
data = pd.read_csv(file_path)

# Step 2: Inspect the dataset
print("Columns in dataset:", data.columns.tolist())  # Debug: List all columns
print("Sample data from dataset:")
print(data.head())  # Debug: Show the first few rows

# Step 3: Filter and pair data
if 'direction' not in data.columns or 'Car' not in data.columns:
    raise ValueError("Dataset must include 'direction' and 'Car' columns.")

# Separate inbound and outbound data
inbound_data = data[data['direction'] == 'in']['Car'].reset_index(drop=True)
outbound_data = data[data['direction'] == 'out']['Car'].reset_index(drop=True)

if len(inbound_data) != len(outbound_data):
    raise ValueError("Mismatch in the number of 'in' and 'out' rows.")

# Normalize data
inbound_data = (inbound_data - inbound_data.mean()) / inbound_data.std()
outbound_data = (outbound_data - outbound_data.mean()) / outbound_data.std()

# Train-test split
inbound_train, inbound_val, outbound_train, outbound_val = train_test_split(
    inbound_data, outbound_data, test_size=0.2, random_state=42
)

data_pairs_train = list(zip(inbound_train, outbound_train))
data_pairs_val = list(zip(inbound_val, outbound_val))
print(f"Number of training data pairs: {len(data_pairs_train)}")

# Step 4: Define custom evaluation function
def custom_evaluate(individual, data_pairs):
    func = toolbox.compile(expr=individual)
    errors = [(func(inbound) - outbound) ** 2 for inbound, outbound in data_pairs]
    rmse = np.sqrt(sum(errors) / len(errors))
    complexity_penalty = len(individual) * 0.005  # Penalize tree complexity
    return rmse + complexity_penalty,  # Penalized RMSE

def calculate_percentage_error(predictions, actuals):
    errors = [(abs(pred - actual) / abs(actual)) * 100 for pred, actual in zip(predictions, actuals)]
    avg_error = sum(errors) / len(errors)
    return avg_error

def safe_div(x, y):
    return x / y if y != 0 else 1

def safe_log(x):
    return math.log(x) if x > 0 else 0

# Step 5: Define genetic programming components
pset = gp.PrimitiveSet("MAIN", 1)  # 1 input: inbound vehicles
pset.addPrimitive(operator.add, 2)
pset.addPrimitive(operator.sub, 2)
pset.addPrimitive(operator.mul, 2)
pset.addPrimitive(operator.neg, 1)
pset.addPrimitive(safe_div, 2)
pset.addPrimitive(safe_log, 1)
pset.addEphemeralConstant("rand", lambda: random.uniform(-0.5, 0.5))
pset.renameArguments(ARG0="inbound_vehicles")
creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMin)

toolbox = base.Toolbox()
toolbox.register("expr", gp.genHalfAndHalf, pset=pset, min_=1, max_=3)
toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.expr)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("compile", gp.compile, pset=pset)
toolbox.register("evaluate", custom_evaluate, data_pairs=data_pairs_train)
toolbox.register("select", tools.selTournament, tournsize=3)
toolbox.register("mate", gp.cxOnePoint)
toolbox.register("expr_mut", gp.genFull, min_=2, max_=4)
toolbox.register("mutate", gp.mutUniform, expr=toolbox.expr_mut, pset=pset)

# Step 6: Configure and run the genetic programming evolution process
population = toolbox.population(n=500)
hof = tools.HallOfFame(1)
stats = tools.Statistics(lambda ind: ind.fitness.values)
stats.register("avg", np.mean)
stats.register("std", np.std)
stats.register("min", np.min)
stats.register("max", np.max)

_, logbook = algorithms.eaSimple(
    population, toolbox, cxpb=0.7, mutpb=0.2, ngen=150, stats=stats, halloffame=hof, verbose=True
)

# Step 7: Extract generation and minimum fitness values for plotting
gen = logbook.select("gen")
min_fitness_values = logbook.select("min")

# Plot fitness progression
plt.figure(figsize=(10, 6))
plt.plot(gen, min_fitness_values, label="Best Fitness (Min)", marker='o')
plt.xlabel("Generation")
plt.ylabel("Fitness (RMSE)")
plt.title("Fitness Progression Over Generations")
plt.legend()
plt.grid()
plt.show()

# Step 8: Display the best evolved model
best_individual = hof[0]
print("Best individual:", best_individual)
print("Best training fitness (RMSE):", custom_evaluate(best_individual, data_pairs_train)[0])

# File path to store RMSE results
output_file = "rmse_results.csv"

# Check if the file already exists to determine if the header should be written
file_exists = os.path.isfile(output_file)

# Append RMSE values to the CSV file
with open(output_file, "a", newline="") as csvfile:
    writer = csv.writer(csvfile)
    
    # Write header only if the file is new
    if not file_exists:
        writer.writerow(["Run", "Generation", "RMSE"])  # Header
    
    # Identify the current run number
    current_run = sum(1 for _ in open(output_file)) // len(gen) if file_exists else 1
    
    # Write data for the current run
    for g, rmse in zip(gen, min_fitness_values):
        writer.writerow([f"Run {current_run}", g, rmse])

print(f"RMSE values for Run {current_run} appended to {output_file}")

# Validate the model
func = toolbox.compile(expr=best_individual)
predictions = [func(inv) for inv in inbound_val]
val_rmse = np.sqrt(np.mean([(pred - actual) ** 2 for pred, actual in zip(predictions, outbound_val)]))
print("Validation RMSE:", val_rmse)

# Calculate percentage error
percentage_error = calculate_percentage_error(predictions, outbound_val)
print("Validation Percentage Error:", percentage_error, "%")


plt.figure(figsize=(10, 6))
plt.axhline(y=1, color='red', linestyle='--', label="1% Target")
plt.plot(range(len(predictions)), [abs(pred - actual) for pred, actual in zip(predictions, outbound_val)], label="Error", marker='o', linestyle='-', color='blue')
plt.xlabel("Data Points")
plt.ylabel("Error")
plt.title("Prediction Errors on Validation Data")
plt.legend()
plt.grid()
plt.show()
