from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Connection ───────────────────────────────────────────────
CONNECTION_STRING = "mongodb+srv://architaaa2024_db_user:Achu101006@cluster0.4xsvnha.mongodb.net/?appName=Cluster0"
DATABASE = "kubecost"
COLLECTION = "allocations"

client = MongoClient(CONNECTION_STRING)
col = client[DATABASE][COLLECTION]

# Create indexes on startup
col.create_index([("name", 1), ("date", 1)])
col.create_index([("cluster", 1), ("name", 1), ("date", 1)])
col.create_index("date")
col.create_index("name")
col.create_index("cluster")

# ─── State ────────────────────────────────────────────────────
current_cluster = {"value": None}  # None = all clusters

# ─── Helpers ──────────────────────────────────────────────────
def get_cluster_filter():
    cluster = current_cluster["value"]
    if cluster:
        return {"cluster": cluster}
    return {}

def get_match_stage():
    f = get_cluster_filter()
    return {"$match": f} if f else {"$match": {}}

# ─── Routes ───────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "K8s Data API running"}


@app.get("/clusters")
def get_clusters():
    clusters = col.distinct("cluster")
    return {"clusters": clusters, "has_clusters": len(clusters) > 0}


@app.post("/select-cluster")
def select_cluster(payload: dict):
    cluster = payload.get("cluster")
    current_cluster["value"] = cluster
    query = {"cluster": cluster} if cluster else {}
    namespaces = col.distinct("name", query)
    return {"cluster": cluster, "namespaces": namespaces}


@app.get("/status")
def get_status():
    total = col.count_documents({})
    first = col.find_one({}, {"date": 1, "_id": 0}, sort=[("date", 1)])
    last  = col.find_one({}, {"date": 1, "_id": 0}, sort=[("date", -1)])
    namespaces = col.distinct("name")
    date_range = f"{first['date']} to {last['date']}" if first and last else "Unknown"
    return {
        "has_data": True,
        "namespaces": namespaces,
        "total_records": total,
        "date_range": date_range
    }


@app.get("/namespaces")
def get_namespaces():
    cluster_filter = get_cluster_filter()
    namespaces = col.distinct("name", cluster_filter)
    return {"namespaces": namespaces}


@app.get("/overview")
def get_overview():
    match = get_match_stage()

    # Total cost
    total_result = list(col.aggregate([
        match,
        {"$group": {"_id": None, "total": {"$sum": "$totalCost"}}}
    ]))
    total_cost = round(total_result[0]["total"], 2) if total_result else 0

    # Namespace count
    cluster_filter = get_cluster_filter()
    namespace_count = len(col.distinct("name", cluster_filter))

    # Daily trend
    trend = list(col.aggregate([
        match,
        {"$group": {"_id": "$date", "cost": {"$sum": "$totalCost"}}},
        {"$sort": {"_id": 1}},
        {"$project": {"date": "$_id", "cost": {"$round": ["$cost", 4]}, "_id": 0}}
    ]))

    avg_daily = round(total_cost / max(len(trend), 1), 2)

    # Most expensive
    expensive = list(col.aggregate([
        match,
        {"$group": {"_id": "$name", "total": {"$sum": "$totalCost"}}},
        {"$sort": {"total": -1}},
        {"$limit": 3}
    ]))
    expensive_list = [{"name": r["_id"], "cost": f"${r['total']:.2f}"} for r in expensive]

    # Most wasteful
    wasteful = list(col.aggregate([
        match,
        {"$group": {"_id": "$name", "avgCpuEff": {"$avg": "$cpuEfficiency"}}},
        {"$sort": {"avgCpuEff": 1}},
        {"$limit": 3}
    ]))
    wasteful_list = [{"name": r["_id"], "efficiency": f"{r['avgCpuEff']*100:.0f}%"} for r in wasteful]

    # Forecast — last 30 days average
    last_30 = list(col.aggregate([
        match,
        {"$group": {"_id": "$date", "cost": {"$sum": "$totalCost"}}},
        {"$sort": {"_id": -1}},
        {"$limit": 30}
    ]))
    avg_last_30 = sum(r["cost"] for r in last_30) / max(len(last_30), 1)
    forecast_30 = round(avg_last_30 * 30, 2)

    return {
        "total_cost": total_cost,
        "namespace_count": namespace_count,
        "avg_daily_cost": avg_daily,
        "forecast_month_end": forecast_30,
        "trend": trend,
        "most_expensive": expensive_list,
        "most_wasteful": wasteful_list,
    }


@app.get("/namespace/{name}")
def get_namespace(name: str):
    cluster_filter = get_cluster_filter()
    match_query = {"name": name}
    match_query.update(cluster_filter)

    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": None,
            "cpu_cost":       {"$sum": "$cpuCost"},
            "ram_cost":       {"$sum": "$ramCost"},
            "storage_cost":   {"$sum": "$pvCost"},
            "cpu_efficiency": {"$avg": "$cpuEfficiency"},
            "ram_efficiency": {"$avg": "$ramEfficiency"},
            "avg_pods":       {"$avg": "$podCount"},
        }}
    ]
    result = list(col.aggregate(pipeline))
    if not result:
        return {"error": f"Namespace '{name}' not found"}

    r = result[0]
    cpu_eff = round(r["cpu_efficiency"], 4)
    ram_eff = round(r["ram_efficiency"], 4)

    # Last 30 days for forecast
    last_30_query = {"name": name}
    last_30_query.update(cluster_filter)
    last_30 = list(col.find(
        last_30_query,
        {"totalCost": 1, "_id": 0},
        sort=[("date", -1)]
    ).limit(30))

    if last_30:
        costs = [d["totalCost"] for d in reversed(last_30)]
        x = np.arange(len(costs))
        slope, intercept = np.polyfit(x, costs, 1)
        forecast_30d = round(float(intercept + slope * (len(costs) + 30)), 2)
    else:
        forecast_30d = 0

    if cpu_eff < 0.10:
        recommendation = f"CPU efficiency is critically low at {cpu_eff*100:.0f}%. Reduce CPU allocation by 70%."
    elif cpu_eff < 0.30:
        recommendation = f"CPU efficiency is low at {cpu_eff*100:.0f}%. Consider reducing CPU limits."
    elif ram_eff < 0.50:
        recommendation = f"RAM efficiency is low at {ram_eff*100:.0f}%. Consider reducing RAM allocation."
    else:
        recommendation = f"Resource utilization is healthy. CPU: {cpu_eff*100:.0f}%, RAM: {ram_eff*100:.0f}%."

    return {
        "name": name,
        "cpu_cost":       round(r["cpu_cost"], 2),
        "ram_cost":       round(r["ram_cost"], 2),
        "storage_cost":   round(r["storage_cost"], 2),
        "cpu_efficiency": cpu_eff,
        "ram_efficiency": ram_eff,
        "avg_pods":       round(r["avg_pods"], 1),
        "forecast_30d":   f"${forecast_30d}",
        "recommendation": recommendation,
    }


@app.get("/namespace-data/{name}")
def get_namespace_data(name: str):
    """Returns raw time series data for a namespace — used by main FastAPI for SARIMA/Prophet"""
    cluster_filter = get_cluster_filter()
    query = {"name": name}
    query.update(cluster_filter)

    records = list(col.find(
        query,
        {"date": 1, "dayIndex": 1, "totalCost": 1, "podCount": 1, "_id": 0},
        sort=[("date", 1)]
    ))
    if not records:
        return {"error": f"Namespace '{name}' not found"}

    return {"name": name, "records": records}