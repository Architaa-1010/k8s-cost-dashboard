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
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"]
    
    # Total cost across all namespaces
    total_cost = round(float(df["totalCost"].sum()), 2)
    
    # Number of unique namespaces
    namespace_count = df["name"].nunique()
    
    # Average daily cost
    # Average daily cost — sum per day first, then average
    daily_totals = df.groupby("date")["totalCost"].sum()
    avg_daily = round(float(daily_totals.mean()), 2)
    # Cost trend — daily total across all namespaces
    trend = (
        df.groupby("date")["totalCost"]
        .sum()
        .reset_index()
        .rename(columns={"date": "date", "totalCost": "cost"})
    )
    trend["cost"] = trend["cost"].round(4)
    trend_list = trend.to_dict(orient="records")
    
    # Top 3 most expensive namespaces
    expensive = (
        df.groupby("name")["totalCost"]
        .sum()
        .reset_index()
        .sort_values("totalCost", ascending=False)
        .head(3)
    )
    expensive_list = [
        {"name": row["name"], "cost": f"${row['totalCost']:.2f}"}
        for _, row in expensive.iterrows()
    ]
    
    # Top 3 most wasteful (lowest average CPU efficiency)
    wasteful = (
        df.groupby("name")["cpuEfficiency"]
        .mean()
        .reset_index()
        .sort_values("cpuEfficiency", ascending=True)
        .head(3)
    )
    wasteful_list = [
        {"name": row["name"], "efficiency": f"{row['cpuEfficiency']*100:.0f}%"}
        for _, row in wasteful.iterrows()
    ]
    
    # Simple linear forecast for month end
    daily_totals_sorted = daily_totals.reset_index()
    daily_totals_sorted["dayIndex"] = range(len(daily_totals_sorted))
    x = daily_totals_sorted["dayIndex"].values
    y = daily_totals_sorted["totalCost"].values
    slope = np.polyfit(x, y, 1)[0]
    last_day = x[-1]
    forecast_30 = round(y[-1] + slope * 30, 2)

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
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"]
    ns = df[df["name"] == name]
    
    if ns.empty:
        return {"error": f"Namespace '{name}' not found"}
    
    # Cost breakdown
    cpu_cost = float(round(ns["cpuCost"].sum(), 2))
    ram_cost = float(round(ns["ramCost"].sum(), 2))
    storage_cost = float(round(ns["pvCost"].sum(), 2))

    # Efficiency
    cpu_eff = ns["cpuEfficiency"].mean()
    ram_eff = ns["ramEfficiency"].mean()

    # Handle both formats:
    # 0.58 -> 58%
    # 58   -> 58%
    if cpu_eff > 1:
        cpu_eff = cpu_eff / 100

    if ram_eff > 1:
        ram_eff = ram_eff / 100

    cpu_eff = round(cpu_eff, 4)
    ram_eff = round(ram_eff, 4)

    avg_pods = float(round(ns["podCount"].mean(), 1))
    
    # Linear forecast for 30 days
    ns_sorted = ns.sort_values("date").reset_index(drop=True)
    x = np.arange(len(ns_sorted))
    y = ns_sorted["totalCost"].values
    slope, intercept = np.polyfit(x, y, 1)
    forecast_30d = float(round(
        float(intercept + slope * (len(x) + 30)), 2
    ))
    
    # Right sizing recommendation
    if cpu_eff < 0.10:
        recommendation = f"CPU efficiency is critically low at {cpu_eff*100:.0f}%. Reduce CPU allocation by 70% — significant savings possible."
    elif cpu_eff < 0.30:
        recommendation = f"CPU efficiency is low at {cpu_eff*100:.0f}%. Consider reducing CPU limits to save cost."
    elif ram_eff < 0.50:
        recommendation = f"RAM efficiency is low at {ram_eff*100:.0f}%. Consider reducing RAM allocation."
    else:
        recommendation = f"Resource utilization is healthy. CPU: {cpu_eff*100:.0f}%, RAM: {ram_eff*100:.0f}%."
    print(type(cpu_cost))
    print(type(avg_pods))
    print(type(cpu_eff))

    return {
        "name": name,
        "cpu_cost": cpu_cost,
        "ram_cost": ram_cost,
        "storage_cost": storage_cost,
        "cpu_efficiency": cpu_eff,
        "ram_efficiency": ram_eff,
        "avg_pods": avg_pods,
        "forecast_30d": f"${forecast_30d}",
        "recommendation": recommendation,
    }


@app.get("/namespaces")
def get_namespaces():
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    return {"namespaces": uploaded_data["df"]["name"].unique().tolist()}


@app.get("/forecast/{name}")
def get_forecast(name: str):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"]
    ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
    
    if ns.empty:
        return {"error": f"Namespace '{name}' not found"}
    

    historical = [
        {"day": int(row["dayIndex"]), "value": round(row["totalCost"], 4)}
        for _, row in ns.iterrows()
    ]
    
    # Linear forecast for next 30 days
    x = np.arange(len(ns))
    y = ns["totalCost"].values
    slope, intercept = np.polyfit(x, y, 1)
    
    last_day = int(ns["dayIndex"].iloc[-1])
    forecast = [{"day": last_day, "value": round(float(y[-1]), 4)}]
    for i in range(1, 31):
        predicted = float(intercept + slope * (len(x) + i))
        forecast.append({
            "day": last_day + i,
            "value": round(max(predicted, 0), 4)
        })
    
    # Weekly totals from forecast
    forecast_values = [f["value"] for f in forecast[1:]]
    weekly = [
        round(sum(forecast_values[i*7:(i+1)*7]), 2)
        for i in range(4)
    ]
    monthly = round(sum(forecast_values[:30]), 2)
    
    return {
        "name": name,
        "historical": historical,
        "forecast": forecast,
        "weekly": [f"${w}" for w in weekly],
        "monthly": f"${monthly}",
    }

@app.get("/forecast/sarima/{name}")
def get_sarima_forecast(name: str):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
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

    weekly = [
        round(sum(forecast_values[i*7:(i+1)*7]), 2)
        for i in range(4)
    ]
    monthly = round(sum(forecast_values[:30]), 2)

    return {
        "name": name,
        "model": "SARIMA",
        "historical": historical,
        "forecast": forecast,
        "weekly": [f"${w}" for w in weekly],
        "monthly": f"${monthly}",
    }
@app.get("/forecast/sarima-pods/{name}")
def get_sarima_pods_forecast(name: str):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
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
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
    df = uploaded_data["df"]
    namespaces = df["name"].unique().tolist()
    results = {}

    for name in namespaces:
        ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)
        y = ns["totalCost"].values
        try:
            model = SARIMAX(y, order=(1,1,1), seasonal_order=(1,1,1,7))
            result = model.fit(disp=False)
            forecast_values = result.forecast(steps=30)
            monthly = round(float(sum([max(float(v), 0) for v in forecast_values])), 2)
        except:
            # fallback to linear if SARIMA fails
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            forecast_values = [max(float(intercept + slope * (len(y) + i)), 0) for i in range(1, 31)]
            monthly = round(sum(forecast_values), 2)
        
        results[name] = monthly

    return {"forecasts": results}
@app.get("/forecast/prophet/{name}")
def get_prophet_forecast(name: str):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}
    
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
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

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

        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        db = client[database]
        col = db[collection]

        records = list(col.find({}, {"_id": 0}))

        if not records:
            return {"error": "Collection is empty or not found"}

        df = pd.DataFrame(records)

        # Validate required fields
        

        uploaded_data["df"] = df
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

        namespaces = []
        date_range = "Unknown"

        if len(missing) == 0:
            if "dayIndex" not in df.columns:
                df = df.sort_values("date").reset_index(drop=True)
                df["dayIndex"] = df.groupby("name").cumcount()

            uploaded_data["df"] = df
            df.to_csv(DATA_PATH, index=False)

            namespaces = df["name"].unique().tolist()
            date_range = f"{df['date'].min()} to {df['date'].max()}"

        return {
            "message": "MongoDB connected successfully",
            "needs_mapping": len(missing) > 0,
            "columns": df.columns.tolist(),
            "missing": missing,
            "namespaces": namespaces,
            "total_records": len(df),
            "date_range": date_range
        }

    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}

@app.get("/status")
def get_status():
    if "df" not in uploaded_data:
        return {"has_data": False}
    
    df = uploaded_data["df"]
    return {
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
    return {"message": "Data cleared"}

@app.get("/backtest/{name}")
def backTest(name: str, model: str = "sarima"):
    if "df" not in uploaded_data:
        return {"error": "No data uploaded yet"}

    df = uploaded_data["df"]
    ns = df[df["name"] == name].sort_values("date").reset_index(drop=True)

    if ns.empty:
        return {"error": f"Namespace '{name}' not found"}

    y = ns["totalCost"].values
    dates = ns["date"].tolist()
    days = ns["dayIndex"].tolist()

    # Split — 60 train, 30 test
    split = 60
    train = y[:split]
    test = y[split:]
    test_days = days[split:]
    test_dates = dates[split:]

    if model == "sarima":
        try:
            m = SARIMAX(train, order=(1,1,1), seasonal_order=(1,1,1,7))
            result = m.fit(disp=False)
            predicted = result.forecast(steps=len(test))
            predicted = [max(float(v), 0) for v in predicted]
        except Exception as e:
            return {"error": f"SARIMA failed: {str(e)}"}

    elif model == "prophet":
        try:
            prophet_df = pd.DataFrame({
                "ds": pd.to_datetime(ns["date"][:split]),
                "y": train
            })
            m = Prophet(weekly_seasonality=True, daily_seasonality=False)
            m.fit(prophet_df)
            future = pd.DataFrame({
                "ds": pd.to_datetime(test_dates)
            })
            forecast = m.predict(future)
            predicted = [max(float(v), 0) for v in forecast["yhat"].values]
        except Exception as e:
            return {"error": f"Prophet failed: {str(e)}"}
    else:
        return {"error": "model must be 'sarima' or 'prophet'"}

    # Calculate metrics
    actual = list(test)
    mape = float(np.mean([
        abs(a - p) / a * 100
        for a, p in zip(actual, predicted) if a != 0
    ]))
    rmse = float(np.sqrt(np.mean([(a - p) ** 2 for a, p in zip(actual, predicted)])))
    mae = float(np.mean([abs(a - p) for a, p in zip(actual, predicted)]))

    # Build comparison data
    comparison = []
    for i in range(len(test)):
        comparison.append({
            "day": test_days[i],
            "actual": round(float(actual[i]), 4),
            "predicted": round(float(predicted[i]), 4)
        })

    # Training period for chart context
    train_data = [
        {"day": int(days[i]), "actual": round(float(y[i]), 4)}
        for i in range(split)
    ]

    return {
        "name": name,
        "model": model.upper(),
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

        # Save raw data exactly as received
        uploaded_data["df"] = df
        df.to_csv(DATA_PATH, index=False)

        # Check whether mapping is needed
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

        namespaces = []
        date_range = "Unknown"

        if len(missing) == 0:
            if "dayIndex" not in df.columns:
                df = df.sort_values("date").reset_index(drop=True)
                df["dayIndex"] = df.groupby("name").cumcount()

            uploaded_data["df"] = df
            df.to_csv(DATA_PATH, index=False)

            namespaces = df["name"].unique().tolist()
            date_range = f"{df['date'].min()} to {df['date'].max()}"

        return {
            "message": "API connected successfully",
            "needs_mapping": len(missing) > 0,
            "columns": df.columns.tolist(),
            "missing": missing,
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