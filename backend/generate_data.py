from pymongo import MongoClient
from datetime import date, timedelta
import random

# Replace with your actual connection string
CONNECTION_STRING = "mongodb+srv://architaaa2024_db_user:Achu101006@cluster0.4xsvnha.mongodb.net/?appName=Cluster0"
DATABASE = "kubecost"
COLLECTION = "allocations"

# All possible namespaces in the ecosystem
ALL_NAMESPACES = [
    {"name": "production-api",  "base_cost": 1.35, "growth": 0.008, "cpu_eff": 0.45, "ram_eff": 0.70, "pods": 22},
    {"name": "ml-training",     "base_cost": 1.15, "growth": 0.007, "cpu_eff": 0.70, "ram_eff": 0.90, "pods": 18},
    {"name": "kafka",           "base_cost": 1.07, "growth": 0.005, "cpu_eff": 0.10, "ram_eff": 0.89, "pods": 6},
    {"name": "postgres-db",     "base_cost": 0.78, "growth": 0.003, "cpu_eff": 0.20, "ram_eff": 0.88, "pods": 3},
    {"name": "ingress-nginx",   "base_cost": 0.57, "growth": 0.002, "cpu_eff": 0.80, "ram_eff": 0.88, "pods": 5},
    {"name": "staging",         "base_cost": 0.45, "growth": 0.001, "cpu_eff": 0.10, "ram_eff": 0.66, "pods": 5},
    {"name": "kube-system",     "base_cost": 0.30, "growth": 0.001, "cpu_eff": 0.02, "ram_eff": 0.94, "pods": 4},
    {"name": "prometheus",      "base_cost": 0.028, "growth": 0.0001, "cpu_eff": 1.00, "ram_eff": 1.00, "pods": 4},
    {"name": "opencost",        "base_cost": 0.022, "growth": 0.0001, "cpu_eff": 0.05, "ram_eff": 0.28, "pods": 3},
    {"name": "data-pipeline",   "base_cost": 0.90, "growth": 0.006, "cpu_eff": 0.55, "ram_eff": 0.75, "pods": 8},
    {"name": "redis-cache",     "base_cost": 0.65, "growth": 0.004, "cpu_eff": 0.60, "ram_eff": 0.80, "pods": 4},
    {"name": "elasticsearch",   "base_cost": 0.85, "growth": 0.005, "cpu_eff": 0.40, "ram_eff": 0.70, "pods": 6},
    {"name": "grafana",         "base_cost": 0.25, "growth": 0.001, "cpu_eff": 0.30, "ram_eff": 0.65, "pods": 2},
    {"name": "alertmanager",    "base_cost": 0.18, "growth": 0.001, "cpu_eff": 0.25, "ram_eff": 0.60, "pods": 2},
    {"name": "cert-manager",    "base_cost": 0.12, "growth": 0.0005, "cpu_eff": 0.15, "ram_eff": 0.55, "pods": 2},
    {"name": "istio-system",    "base_cost": 0.35, "growth": 0.002, "cpu_eff": 0.50, "ram_eff": 0.72, "pods": 6},
    {"name": "logging",         "base_cost": 0.42, "growth": 0.003, "cpu_eff": 0.35, "ram_eff": 0.68, "pods": 4},
    {"name": "monitoring",      "base_cost": 0.38, "growth": 0.002, "cpu_eff": 0.45, "ram_eff": 0.75, "pods": 5},
    {"name": "api-gateway",     "base_cost": 0.72, "growth": 0.004, "cpu_eff": 0.65, "ram_eff": 0.82, "pods": 7},
    {"name": "auth-service",    "base_cost": 0.55, "growth": 0.003, "cpu_eff": 0.58, "ram_eff": 0.78, "pods": 5},
]

CLUSTERS = 120
START_DATE = date(2023, 1, 1)
TOTAL_DAYS = 365

print(f"Starting data generation...")

client = MongoClient(CONNECTION_STRING)
db = client[DATABASE]
col = db[COLLECTION]

col.drop()
print("Cleared existing collection.")

batch = []
batch_size = 5000
total = 0

for cluster_id in range(CLUSTERS):
    cluster_name = f"cluster-{cluster_id+1:02d}"

    # Each cluster gets a random subset of namespaces (5-15)
    cluster_ns_count = random.randint(5, 15)
    cluster_namespaces = random.sample(ALL_NAMESPACES, cluster_ns_count)

    # kube-system always exists in every cluster
    ns_names = [ns["name"] for ns in cluster_namespaces]
    if "kube-system" not in ns_names:
        cluster_namespaces.append(next(n for n in ALL_NAMESPACES if n["name"] == "kube-system"))

    for ns in cluster_namespaces:
        # Each namespace has a random lifespan within the 365 days
        # Simulates pods/namespaces spinning up and down
        ns_start = random.randint(0, 100)
        ns_duration = random.randint(60, TOTAL_DAYS - ns_start)
        ns_end = ns_start + ns_duration

        for day_idx in range(ns_start, ns_end):
            current_date = START_DATE + timedelta(days=day_idx)

            weekday = current_date.weekday()
            weekend_factor = 0.85 if weekday >= 5 else 1.0
            monday_factor = 1.15 if weekday == 0 and ns["name"] in ["production-api", "ml-training"] else 1.0
            noise = 1 + random.uniform(-0.08, 0.08)
            growth_factor = 1 + (ns["growth"] * day_idx)

            total_cost = round(
                ns["base_cost"] * growth_factor * weekend_factor * monday_factor * noise, 6
            )
            cpu_cost  = round(total_cost * 0.60, 6)
            ram_cost  = round(total_cost * 0.30, 6)
            pv_cost   = round(total_cost * 0.10, 6)

            batch.append({
                "name":          ns["name"],
                "cluster":       cluster_name,
                "date":          str(current_date),
                "dayIndex":      day_idx - ns_start,
                "cpuCost":       cpu_cost,
                "ramCost":       ram_cost,
                "pvCost":        pv_cost,
                "podCount":      max(1, ns["pods"] + random.randint(-1, 2)),
                "totalCost":     total_cost,
                "cpuEfficiency": round(min(1.0, max(0.01, ns["cpu_eff"] + random.uniform(-0.02, 0.02))), 4),
                "ramEfficiency": round(min(1.0, max(0.01, ns["ram_eff"] + random.uniform(-0.02, 0.02))), 4),
            })

            if len(batch) >= batch_size:
                col.insert_many(batch)
                total += len(batch)
                print(f"Inserted {total:,} records...")
                batch = []

if batch:
    col.insert_many(batch)
    total += len(batch)

print(f"Done! Total records: {total:,}")
client.close()