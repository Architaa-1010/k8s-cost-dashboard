from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import json
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
from prophet import Prophet
from pymongo import MongoClient
import os
from datetime import date, timedelta
warnings.filterwarnings("ignore")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# We store the uploaded data in memory while the server is running
uploaded_data = {}
forecast_cache = {}

def get_namespace_df(name: str):
    """Get data for a specific namespace - works for both pandas and MongoDB sources"""
    if "col" in uploaded_data:
        records=list(uploaded_data["col"].find({"name":name},{"_id":0}))
        if not records:
            return None
        return pd.DataFrame(records)
    elif "df" in uploaded_data:
        df=uploaded_data["df"]
        ns=df[df["name"]==name]
        if ns.empty:
            return None
        return ns.reset_index(drop=True)
    return None

def get_full_df():
    """Get full dataframe - only use for overview aggregation"""
    if "col" in uploaded_data:
        return None
    elif "df" in uploaded_data:
        return uploaded_data["df"]
    return None

def get_namespaces():
    """Get list of namespaces """
    if "col" in uploaded_data:
        return uploaded_data["col"].distinct("name")
    elif "df" in uploaded_data:
        return uploaded_data["df"]["name"].unique().tolist()
    return []

DATA_PATH="saved_data.csv"
if os.path.exists(DATA_PATH):
    try:
        saved_df=pd.read_csv(DATA_PATH)
        uploaded_data["df"]=saved_df
        print(f"Loaded saved data: {len(saved_df)} records")
    except Exception as e:
        print(f"Could not load saved data: {e}")

@app.get("/")
def root():
    return {"status": "K8s Cost Dashboard API running"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    records = json.loads(contents)

    df = pd.DataFrame(records)

    uploaded_data["df"] = df
    uploaded_data["cluster"]=None
    df.to_csv(DATA_PATH, index=False)

    required = [
        "name",
        "date",
        "cpuCost",
        "ramCost",
        "pvCost",
        "podCount",
        "totalCost",
        "cpuEfficiency",
        "ramEfficiency"
    ]

    missing = [f for f in required if f not in df.columns]

    # Only calculate these if standard fields exist
    namespaces = []
    date_range = "Unknown"

    if "name" in df.columns:
        namespaces = df["name"].unique().tolist()

    if "date" in df.columns:
        date_range = f"{df['date'].min()} to {df['date'].max()}"

    return {
        "message": "File uploaded successfully",
        "namespaces": namespaces,
        "total_records": len(df),
        "date_range": date_range,
        "needs_mapping": len(missing) > 0,
        "columns": df.columns.tolist(),
        "missing": missing
    }


@app.get("/overview")
def get_overview():
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        # MongoDB — aggregate directly in database
        cluster_match = {"$match": get_cluster_filter()} if get_cluster_filter() else {"$match": {}}
        col = uploaded_data["col"]

        # Total cost
        total_pipeline = [cluster_match, {"$group": {"_id": None, "total": {"$sum": "$totalCost"}}}]
        total_result = list(col.aggregate(total_pipeline))
        total_cost = round(total_result[0]["total"], 2) if total_result else 0

        # Namespace count
        namespaces = col.distinct("name")
        namespace_count = len(namespaces)

        # Daily trend — aggregate by date
        trend_pipeline = [
            cluster_match,
            {"$group": {"_id": "$date", "cost": {"$sum": "$totalCost"}}},
            {"$sort": {"_id": 1}},
            {"$project": {"date": "$_id", "cost": {"$round": ["$cost", 4]}, "_id": 0}}
        ]
        trend = list(col.aggregate(trend_pipeline))

        # Avg daily cost
        avg_daily = round(total_cost / max(len(trend), 1), 2)

        # Most expensive namespaces
        expensive_pipeline = [
            cluster_match,
            {"$group": {"_id": "$name", "total": {"$sum": "$totalCost"}}},
            {"$sort": {"total": -1}},
            {"$limit": 3}
        ]
        expensive = [
            {"name": r["_id"], "cost": f"${r['total']:.2f}"}
            for r in col.aggregate(expensive_pipeline)
        ]

        # Most wasteful (lowest CPU efficiency)
        wasteful_pipeline = [
            cluster_match,
            {"$group": {"_id": "$name", "avgCpuEff": {"$avg": "$cpuEfficiency"}}},
            {"$sort": {"avgCpuEff": 1}},
            {"$limit": 3}
        ]
        wasteful = [
            {"name": r["_id"], "efficiency": f"{r['avgCpuEff']*100:.0f}%"}
            for r in col.aggregate(wasteful_pipeline)
        ]

        # Simple forecast — use last 30 days trend
        last_30 = list(col.aggregate([
            {"$group": {"_id": "$date", "cost": {"$sum": "$totalCost"}}},
            {"$sort": {"_id": -1}},
            {"$limit": 30}
        ]))
        if last_30:
            avg_last_30 = sum(r["cost"] for r in last_30) / len(last_30)
            forecast_30 = round(avg_last_30 * 30, 2)
        else:
            forecast_30 = 0

        return {
            "total_cost": total_cost,
            "namespace_count": namespace_count,
            "avg_daily_cost": avg_daily,
            "forecast_month_end": forecast_30,
            "trend": trend,
            "most_expensive": expensive,
            "most_wasteful": wasteful,
        }

    else:
        # Pandas source (JSON upload) — existing logic
        df = uploaded_data["df"]
        total_cost = round(float(df["totalCost"].sum()), 2)
        namespace_count = df["name"].nunique()
        daily_totals = df.groupby("date")["totalCost"].sum()
        avg_daily = round(float(daily_totals.mean()), 2)
        trend = (
            df.groupby("date")["totalCost"]
            .sum().reset_index()
            .rename(columns={"date": "date", "totalCost": "cost"})
        )
        trend["cost"] = trend["cost"].round(4)
        trend_list = trend.to_dict(orient="records")
        expensive = (
            df.groupby("name")["totalCost"].sum()
            .reset_index().sort_values("totalCost", ascending=False).head(3)
        )
        expensive_list = [{"name": r["name"], "cost": f"${r['totalCost']:.2f}"} for _, r in expensive.iterrows()]
        wasteful = (
            df.groupby("name")["cpuEfficiency"].mean()
            .reset_index().sort_values("cpuEfficiency", ascending=True).head(3)
        )
        wasteful_list = [{"name": r["name"], "efficiency": f"{r['cpuEfficiency']*100:.0f}%"} for _, r in wasteful.iterrows()]
        daily_totals_sorted = daily_totals.reset_index()
        daily_totals_sorted["dayIndex"] = range(len(daily_totals_sorted))
        x = daily_totals_sorted["dayIndex"].values
        y = daily_totals_sorted["totalCost"].values
        slope = np.polyfit(x, y, 1)[0]
        forecast_30 = round(float(y[-1] + slope * 30), 2)
        return {
            "total_cost": total_cost,
            "namespace_count": namespace_count,
            "avg_daily_cost": avg_daily,
            "forecast_month_end": forecast_30,
            "trend": trend_list,
            "most_expensive": expensive_list,
            "most_wasteful": wasteful_list,
        }


@app.get("/namespace/{name}")
def get_namespace(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        col = uploaded_data["col"]

        # Aggregate directly in MongoDB
        pipeline = [
            {"$match": {"name": name}},
            {"$group": {
                "_id": None,
                "cpu_cost":       {"$sum": "$cpuCost"},
                "ram_cost":       {"$sum": "$ramCost"},
                "storage_cost":   {"$sum": "$pvCost"},
                "cpu_efficiency": {"$avg": "$cpuEfficiency"},
                "ram_efficiency": {"$avg": "$ramEfficiency"},
                "avg_pods":       {"$avg": "$podCount"},
                "count":          {"$sum": 1}
            }}
        ]
        result = list(col.aggregate(pipeline))
        if not result:
            return {"error": f"Namespace '{name}' not found"}

        r = result[0]
        cpu_eff = round(r["cpu_efficiency"], 4)
        ram_eff = round(r["ram_efficiency"], 4)

        # Linear forecast from last 30 days
        last_30 = list(col.find(
            {"name": name},
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

    else:
        # Pandas source
        df = uploaded_data["df"]
        ns = df[df["name"] == name]
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}
        cpu_cost     = round(ns["cpuCost"].sum(), 2)
        ram_cost     = round(ns["ramCost"].sum(), 2)
        storage_cost = round(ns["pvCost"].sum(), 2)
        cpu_eff      = round(ns["cpuEfficiency"].mean(), 4)
        ram_eff      = round(ns["ramEfficiency"].mean(), 4)
        avg_pods     = round(ns["podCount"].mean(), 1)
        ns_sorted    = ns.sort_values("date").reset_index(drop=True)
        x            = np.arange(len(ns_sorted))
        y            = ns_sorted["totalCost"].values
        slope, intercept = np.polyfit(x, y, 1)
        forecast_30d = round(float(intercept + slope * (len(x) + 30)), 2)
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
            "cpu_cost": cpu_cost, "ram_cost": ram_cost,
            "storage_cost": storage_cost,
            "cpu_efficiency": cpu_eff, "ram_efficiency": ram_eff,
            "avg_pods": avg_pods, "forecast_30d": f"${forecast_30d}",
            "recommendation": recommendation,
        }

@app.get("/namespaces")
def get_namespaces_endpoint():
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    return {"namespaces": get_namespaces_list()}

def get_namespaces_list():
    if "col" in uploaded_data:
        return uploaded_data["col"].distinct("name")
    elif "df" in uploaded_data:
        return uploaded_data["df"]["name"].unique().tolist()
    return []

def get_cluster_filter():
    if uploaded_data.get("source") != "mongodb":
        return {}
    cluster = uploaded_data.get("cluster")
    if cluster:
        return {"cluster": cluster}
    return {}


@app.get("/forecast/{name}")
def get_forecast(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        col = uploaded_data["col"]
        query = {"name": name}
        query.update(get_cluster_filter())
        # Query only this namespace, sorted by date
        records = list(col.find(
            query,
            {"name": name},
            {"date": 1, "dayIndex": 1, "totalCost": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}

    x = np.arange(len(ns))
    y = ns["totalCost"].values
    slope, intercept = np.polyfit(x, y, 1)
    last_day = int(ns["dayIndex"].iloc[-1])

    historical = [
        {"day": int(row["dayIndex"]), "value": round(float(row["totalCost"]), 4)}
        for _, row in ns.iterrows()
    ]
    forecast = [{"day": last_day, "value": round(float(y[-1]), 4)}]
    for i in range(1, 31):
        predicted = float(intercept + slope * (len(x) + i))
        forecast.append({"day": last_day + i, "value": round(max(predicted, 0), 4)})

    forecast_values = [f["value"] for f in forecast[1:]]
    weekly  = [round(sum(forecast_values[i*7:(i+1)*7]), 2) for i in range(4)]
    monthly = round(sum(forecast_values[:30]), 2)

    return {
        "name": name, "historical": historical, "forecast": forecast,
        "weekly": [f"${w}" for w in weekly], "monthly": f"${monthly}",
    }

@app.get("/forecast/sarima/{name}")
def get_sarima_forecast(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        query = {"name": name}
        query.update(get_cluster_filter())
        records = list(uploaded_data["col"].find(
            query,
            {"date": 1, "dayIndex": 1, "totalCost": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
        # Reset dayIndex to be sequential
        ns = ns.reset_index(drop=True)
        ns["dayIndex"] = ns.index
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}

    y = ns["totalCost"].values

    try:
        model = SARIMAX(y, order=(1,1,1), seasonal_order=(1,1,1,7))
        result = model.fit(disp=False)
        forecast_values = result.forecast(steps=30)
        forecast_values = [max(float(v), 0) for v in forecast_values]
    except Exception as e:
        return {"error": f"SARIMA failed: {str(e)}"}

    last_day = int(ns["dayIndex"].iloc[-1])
    historical = [
        {"day": int(row["dayIndex"]), "value": round(float(row["totalCost"]), 4)}
        for _, row in ns.iterrows()
    ]
    forecast = [{"day": last_day, "value": round(float(y[-1]), 4)}]
    for i, val in enumerate(forecast_values):
        forecast.append({"day": last_day + i + 1, "value": round(val, 4)})

    weekly  = [round(sum(forecast_values[i*7:(i+1)*7]), 2) for i in range(4)]
    monthly = round(sum(forecast_values[:30]), 2)

    return {
        "name": name, "model": "SARIMA",
        "historical": historical, "forecast": forecast,
        "weekly": [f"${w}" for w in weekly], "monthly": f"${monthly}",
    }


@app.get("/forecast/sarima-pods/{name}")
def get_sarima_pods_forecast(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        query = {"name": name}
        query.update(get_cluster_filter())
        records = list(uploaded_data["col"].find(
            query,
            {"date": 1, "dayIndex": 1, "totalCost": 1, "podCount": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}
    
    y = ns["podCount"].values.astype(float)

    try:
        model = SARIMAX(y, order=(1,1,1), seasonal_order=(1,1,1,7))
        result = model.fit(disp=False)
        forecast_values = result.forecast(steps=30)
        forecast_values = [max(float(v), 0) for v in forecast_values]
    except Exception as e:
        return {"error": f"SARIMA failed: {str(e)}"}

    last_day = int(ns["dayIndex"].iloc[-1])

    historical = [
        {"day": int(row["dayIndex"]), "value": round(float(row["podCount"]), 1)}
        for _, row in ns.iterrows()
    ]

    forecast = [{"day": last_day, "value": round(float(y[-1]), 1)}]
    for i, val in enumerate(forecast_values):
        forecast.append({"day": last_day + i + 1, "value": round(val, 1)})

    weekly = [
        round(sum(forecast_values[i*7:(i+1)*7]), 1)
        for i in range(4)
    ]
    monthly = round(sum(forecast_values[:30]), 1)

    return {
        "name": name,
        "model": "SARIMA",
        "metric": "podCount",
        "historical": historical,
        "forecast": forecast,
        "weekly": [str(w) for w in weekly],
        "monthly": str(monthly),
    }

@app.get("/budget-forecasts")
def get_budget_forecasts():
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    # Check cache first
    cluster_key = uploaded_data.get("cluster", "all")
    if cluster_key in forecast_cache:
        return {"forecasts": forecast_cache[cluster_key]}

    namespaces = get_namespaces_list()
    results = {}

    for name in namespaces:
        if "col" in uploaded_data:
            query = {"name": name}
            query.update(get_cluster_filter())
            records = list(uploaded_data["col"].find(
                query,
                {"totalCost": 1, "dayIndex": 1, "_id": 0},
                sort=[("date", 1)]
            ))
            if not records:
                continue
            ns = pd.DataFrame(records)
        else:
            df = uploaded_data["df"]
            ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)

        y = ns["totalCost"].values
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        forecast_values = [max(float(intercept + slope * (len(y) + i)), 0) for i in range(1, 31)]
        monthly = round(sum(forecast_values), 2)
        results[name] = monthly

    # Store in cache
    forecast_cache[cluster_key] = results
    return {"forecasts": results}

@app.get("/forecast/prophet/{name}")
def get_prophet_forecast(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        query = {"name": name}
        query.update(get_cluster_filter())
        records = list(uploaded_data["col"].find(
            query,
            {"date": 1, "dayIndex": 1, "totalCost": 1, "podCount": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}

    # Prophet requires columns named ds and y
    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(ns["date"]),
        "y": ns["totalCost"].values
    })

    try:
        model = Prophet(weekly_seasonality=True, daily_seasonality=False)
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=30)
        forecast = model.predict(future)
        forecast_values = [max(float(v), 0) for v in forecast["yhat"].tail(30).values]
    except Exception as e:
        return {"error": f"Prophet failed: {str(e)}"}

    last_day = int(ns["dayIndex"].iloc[-1])

    historical = [
        {"day": int(row["dayIndex"]), "value": round(float(row["totalCost"]), 4)}
        for _, row in ns.iterrows()
    ]

    forecast_out = [{"day": last_day, "value": round(float(ns["totalCost"].iloc[-1]), 4)}]
    for i, val in enumerate(forecast_values):
        forecast_out.append({"day": last_day + i + 1, "value": round(val, 4)})

    weekly = [
        round(sum(forecast_values[i*7:(i+1)*7]), 2)
        for i in range(4)
    ]
    monthly = round(sum(forecast_values[:30]), 2)

    return {
        "name": name,
        "model": "Prophet",
        "historical": historical,
        "forecast": forecast_out,
        "weekly": [f"${w}" for w in weekly],
        "monthly": f"${monthly}",
    }

@app.get("/forecast/prophet-pods/{name}")
def get_prophet_pods_forecast(name: str):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        query = {"name": name}
        query.update(get_cluster_filter())
        records = list(uploaded_data["col"].find(
            query,
            {"date": 1, "dayIndex": 1, "totalCost": 1, "podCount": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}

    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(ns["date"]),
        "y": ns["podCount"].values.astype(float)
    })

    try:
        model = Prophet(weekly_seasonality=True, daily_seasonality=False)
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=30)
        forecast = model.predict(future)
        forecast_values = [max(float(v), 0) for v in forecast["yhat"].tail(30).values]
    except Exception as e:
        return {"error": f"Prophet failed: {str(e)}"}

    last_day = int(ns["dayIndex"].iloc[-1])

    historical = [
        {"day": int(row["dayIndex"]), "value": round(float(row["podCount"]), 1)}
        for _, row in ns.iterrows()
    ]

    forecast_out = [{"day": last_day, "value": round(float(ns["podCount"].iloc[-1]), 1)}]
    for i, val in enumerate(forecast_values):
        forecast_out.append({"day": last_day + i + 1, "value": round(val, 1)})

    weekly = [
        round(sum(forecast_values[i*7:(i+1)*7]), 1)
        for i in range(4)
    ]
    monthly = round(sum(forecast_values[:30]), 1)

    return {
        "name": name,
        "model": "Prophet",
        "metric": "podCount",
        "historical": historical,
        "forecast": forecast_out,
        "weekly": [str(w) for w in weekly],
        "monthly": str(monthly),
    }
@app.post("/connect-mongodb")
def connect_mongodb(payload: dict):
    try:
        connection_string = payload.get("connection_string")
        database = payload.get("database")
        collection = payload.get("collection")

        if not all([connection_string, database, collection]):
            return {"error": "connection_string, database, and collection are all required"}

        client = MongoClient(connection_string, serverSelectionTimeoutMS=10000)
        db = client[database]
        col = db[collection]

        sample= list(col.find({},{"_id":0}).limit(5))
        if not sample:
            return {"error": "Collection is empty or not found"}
        
        sample_keys=list(sample[0].keys())
        required=["name","date","cpuCost","ramCost","pvCost","podCount","totalCost","cpuEfficiency","ramEfficiency"]

        missing = [f for f in required if f not in sample_keys]
        if missing:
            return {"error": f"Missing required fields: {missing}."}

        col.create_index([("name",1),("date",1)])
        col.create_index("date")
        col.create_index("name")
        col.create_index([("cluster", 1), ("name", 1), ("date", 1)])

        uploaded_data["col"]=col
        uploaded_data["source"]="mongodb"
        uploaded_data["cluster"]=None
        namespaces=col.distinct("name")

        first=col.find_one({},{"date":1, "_id":0},sort=[("date",1)])
        last=col.find_one({},{"date":1, "_id":0},sort=[("date",-1)])
        date_range=f"{first['date']} to {last['date']}"

        total=col.count_documents({})

        return {
            "message": "MongoDB connected successfully",
            "namespaces": namespaces,
            "total_records": total,
            "date_range": date_range
        }

    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}

@app.get("/status")
def get_status():
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"has_data": False}
    if "col" in uploaded_data:
        col=uploaded_data["col"]
        namespaces=col.distinct("name")
        total=col.count_documents({})
        first=col.find_one({},{"date":1, "_id":0},sort=[("date",1)])
        last=col.find_one({},{"date":1, "_id":0},sort=[("date",-1)])
        date_range=f"{first['date']} to {last['date']}" if first and last else "Unknown"
        return{
            "has_data": True,
            "namespaces": namespaces,
            "total_records": total,
            "date_range": date_range
        }
    else:
        df=uploaded_data["df"]
        return{
            "has_data": True,
            "namespaces": df["name"].unique().tolist(),
            "total_records": len(df),
            "date_range": f"{df['date'].min()} to {df['date'].max()}"
        }

@app.post("/reset")
def reset_data():
    uploaded_data.clear()
    if os.path.exists(DATA_PATH):
        os.remove(DATA_PATH)
    if os.path.exists(BUDGETS_PATH):
        os.remove(BUDGETS_PATH)
    return {"message": "Data cleared"}

@app.get("/backtest/{name}")
def backTest(
    name: str,
    model: str = "sarima",
    metric: str = "cost"
):
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    if "col" in uploaded_data:
        query = {"name": name}
        query.update(get_cluster_filter())
        records = list(uploaded_data["col"].find(
            query,
            {"date": 1, "dayIndex": 1, "totalCost": 1, "podCount": 1, "_id": 0},
            sort=[("date", 1)]
        ))
        if not records:
            return {"error": f"Namespace '{name}' not found"}
        ns = pd.DataFrame(records)
    else:
        df = uploaded_data["df"]
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        if ns.empty:
            return {"error": f"Namespace '{name}' not found"}

    # -----------------------------
    # Select target column
    # -----------------------------
    if metric == "pods":
        target_col = "podCount"
    else:
        target_col = "totalCost"

    y = ns[target_col].values
    dates = ns["date"].tolist()
    days = ns["dayIndex"].tolist()

    # -----------------------------
    # Train/Test Split
    # -----------------------------
    split = 60

    if len(y) <= split:
        return {"error": "Need more than 60 records for backtesting"}

    train = y[:split]
    test = y[split:]

    test_days = days[split:]
    test_dates = dates[split:]

    # -----------------------------
    # SARIMA
    # -----------------------------
    if model == "sarima":
        try:
            m = SARIMAX(
                train,
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 7)
            )

            result = m.fit(disp=False)

            predicted = result.forecast(
                steps=len(test)
            )

            predicted = [
                max(float(v), 0)
                for v in predicted
            ]

        except Exception as e:
            return {
                "error": f"SARIMA failed: {str(e)}"
            }

    
    # Prophet
    
    elif model == "prophet":
        try:
            prophet_df = pd.DataFrame({
                "ds": pd.to_datetime(ns["date"][:split]),
                "y": train
            })

            m = Prophet(
                weekly_seasonality=True,
                daily_seasonality=False
            )

            m.fit(prophet_df)

            future = pd.DataFrame({
                "ds": pd.to_datetime(test_dates)
            })

            forecast = m.predict(future)

            predicted = [
                max(float(v), 0)
                for v in forecast["yhat"].values
            ]

        except Exception as e:
            return {
                "error": f"Prophet failed: {str(e)}"
            }

    else:
        return {
            "error": "model must be 'sarima' or 'prophet'"
        }

    # -----------------------------
    # Metrics
    # -----------------------------
    actual = list(test)

    mape = float(np.mean([
        abs(a - p) / a * 100
        for a, p in zip(actual, predicted)
        if a != 0
    ]))

    rmse = float(np.sqrt(np.mean([
        (a - p) ** 2
        for a, p in zip(actual, predicted)
    ])))

    mae = float(np.mean([
        abs(a - p)
        for a, p in zip(actual, predicted)
    ]))

    # -----------------------------
    # Comparison Data
    # -----------------------------
    comparison = []

    for i in range(len(test)):
        comparison.append({
            "day": test_days[i],
            "actual": round(float(actual[i]), 4),
            "predicted": round(float(predicted[i]), 4)
        })

    # -----------------------------
    # Training Data
    # -----------------------------
    train_data = [
        {
            "day": int(days[i]),
            "actual": round(float(y[i]), 4)
        }
        for i in range(split)
    ]

    return {
        "name": name,
        "model": model.upper(),
        "metric": metric,
        "target": target_col,
        "train_days": split,
        "test_days": len(test),
        "metrics": {
            "mape": round(mape, 2),
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "accuracy": round(100 - mape, 2)
        },
        "train_data": train_data,
        "comparison": comparison
    }

@app.post("/connect-api")
async def connect_api(payload: dict):
    try:
        api_url = payload.get("api_url")
        if not api_url:
            return {"error": "api_url is required"}

        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(api_url)

        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}

        records = response.json()

        if not isinstance(records, list):
            return {"error": "API must return a JSON array of records"}

        df = pd.DataFrame(records)

        required = ["name", "date", "cpuCost", "ramCost", "pvCost", "podCount", "totalCost", "cpuEfficiency", "ramEfficiency"]
        missing = [f for f in required if f not in df.columns]

        if len(missing) > 0:
            return {"error": f"Your API data is missing required fields: {missing}. Expected Kubecost standard format."}

        if "dayIndex" not in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
            df["dayIndex"] = df.groupby("name").cumcount()

        uploaded_data["df"] = df
        uploaded_data["cluster"]=None
        

        namespaces = df["name"].unique().tolist()
        date_range = f"{df['date'].min()} to {df['date'].max()}"

        return {
            "message": "API connected successfully",
            "namespaces": namespaces,
            "total_records": len(df),
            "date_range": date_range
        }

    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}


@app.get("/test-kubecost")
async def test_kubecost():
    data = []

    for i in range(90):
        data.append({
            "name": "namespace1",
            "date": f"2025-01-{(i%30)+1:02d}",
            "cpuCost": 10 + i*0.1,
            "ramCost": 5 + i*0.05,
            "pvCost": 2,
            "podCount": 4,
            "totalCost": 17 + i*0.2,
            "cpuEfficiency": 0.80,
            "ramEfficiency": 0.75
        })

    return data

@app.post("/apply-mapping")
def apply_mapping(payload: dict):
    try:
        if "df" not in uploaded_data:
            return {"error": "No data uploaded yet"}
        
        mapping = payload.get("mapping")
        if not mapping:
            return {"error": "No mapping provided"}

        df = uploaded_data["df"].copy()
        
        # Rename columns based on mapping
        # mapping looks like: {"their_field": "our_field"}
        reverse_mapping = {v: k for k, v in mapping.items()}
        df = df.rename(columns=mapping)
        
        # Validate all required fields are now present
        required = ["name", "date", "cpuCost", "ramCost", "pvCost", 
                   "podCount", "totalCost", "cpuEfficiency", "ramEfficiency"]
        missing = [f for f in required if f not in df.columns]
        if missing:
            return {"error": f"Still missing fields after mapping: {missing}"}

        if "dayIndex" not in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
            df["dayIndex"] = df.groupby("name").cumcount()

        uploaded_data["df"] = df
        df.to_csv(DATA_PATH, index=False)

        namespaces = df["name"].unique().tolist()
        date_range = f"{df['date'].min()} to {df['date'].max()}"

        return {
            "message": "Mapping applied successfully",
            "namespaces": namespaces,
            "total_records": len(df),
            "date_range": date_range
        }

    except Exception as e:
        return {"error": f"Mapping failed: {str(e)}"}


@app.get("/detected-columns")
def get_detected_columns():
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"]
    columns = df.columns.tolist()
    
    required = ["name", "date", "cpuCost", "ramCost", "pvCost",
                "podCount", "totalCost", "cpuEfficiency", "ramEfficiency"]
    
    missing = [f for f in required if f not in columns]
    
    return {
        "columns": columns,
        "required": required,
        "missing": missing,
        "needs_mapping": len(missing) > 0
    }

@app.get("/fields")
def get_fields():
    if "df" not in uploaded_data:
        if os.path.exists(DATA_PATH):
            try:
                df = pd.read_csv(DATA_PATH)
                uploaded_data["df"] = df
            except:
                return {"error": "No data uploaded yet"}
        else:
            return {"error": "No data uploaded yet"}
    
    columns = uploaded_data["df"].columns.tolist()
    return {"fields": columns}


@app.post("/map-fields")
def map_fields(mapping: dict):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"].copy()
    
    required = {
        "name": mapping.get("name"),
        "date": mapping.get("date"),
        "cpuCost": mapping.get("cpuCost"),
        "ramCost": mapping.get("ramCost"),
        "pvCost": mapping.get("pvCost"),
        "podCount": mapping.get("podCount"),
        "totalCost": mapping.get("totalCost"),
        "cpuEfficiency": mapping.get("cpuEfficiency"),
        "ramEfficiency": mapping.get("ramEfficiency"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        return {"error": f"Please map all fields. Missing: {missing}"}

    rename_map = {v: k for k, v in required.items() if v != k}
    df = df.rename(columns=rename_map)

    if "dayIndex" not in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
        df["dayIndex"] = df.groupby("name").cumcount()

    uploaded_data["df"] = df
    df.to_csv(DATA_PATH, index=False)

    return {
        "message": "Fields mapped successfully",
        "namespaces": df["name"].unique().tolist(),
        "total_records": len(df),
        "date_range": f"{df['date'].min()} to {df['date'].max()}"
    }

@app.get("/test-mapping")
async def test_mapping():
    data = []
    start = date(2025, 1, 1)

    for i in range(90):
        data.append({
            "namespace": "frontend",
            "timestamp": str(start + timedelta(days=i)),
            "cpu_cost": 10 + i * 0.1,
            "memory_cost": 5 + i * 0.05,
            "storage_cost": 2,
            "pods": 4 + (i % 3),
            "total_cost": 17 + i * 0.2,
            "cpu_utilization": 80,
            "memory_utilization": 75
        })

    return data

@app.get("/test-mapping-2")
async def test_mapping_2():
    data = []
    start = date(2025, 1, 1)

    for i in range(90):
        data.append({
            "project": "payments",
            "day": str(start + timedelta(days=i)),
            "compute_spend": 15 + i * 0.15,
            "memory_spend": 8 + i * 0.08,
            "disk_spend": 3,
            "containers": 5,
            "daily_total": 26 + i * 0.25,
            "cpu_usage_pct": 0.82,
            "memory_usage_pct": 0.76
        })

    return data

BUDGETS_PATH = "saved_budgets.json"

@app.get("/budgets")
def get_budgets():
    if os.path.exists(BUDGETS_PATH):
        with open(BUDGETS_PATH, 'r') as f:
            return {"budgets": json.load(f)}
    return {"budgets": {}}

@app.post("/budgets")
def save_budgets(payload: dict):
    budgets = payload.get("budgets", {})
    with open(BUDGETS_PATH, 'w') as f:
        json.dump(budgets, f)
    return {"message": "Budgets saved"}


@app.get("/clusters")
def get_clusters():
    if "col" not in uploaded_data and "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    if "col" in uploaded_data:
        clusters=uploaded_data["col"].distinct("cluster")
        return {"clusters":clusters, "has_clusters":True}
    else:
        df=uploaded_data["df"]
        if "cluster" in df.columns:
            clusters=df["cluster"].unique().tolist()
            return {"clusters":clusters, "has_clusters":True}
        else:
            return {"clusters":[], "has_clusters":False}
        

@app.post("/select-cluster")
def select_cluster(payload: dict):
    cluster=payload.get("cluster")
    uploaded_data["cluster"]=cluster
    forecast_cache.clear()

    if "col" in uploaded_data:
        query={"cluster":cluster} if cluster else {}
        namespaces=uploaded_data["col"].distinct("name",query)

    else:
        df=uploaded_data["df"]
        if cluster and "cluster" in df.columns:
            namespaces=df[df["cluster"]==cluster]["name"].unique().tolist()
        else:
            namespaces=df["name"].unique().tolist()

    return {"cluster":cluster, "namespaces":namespaces}

                        