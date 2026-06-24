# K8s Cost Dashboard

A full-stack Kubernetes cost analytics platform built using React, FastAPI, Pandas, Prophet, SARIMA, and MongoDB.

## Features

### Data Ingestion

* Upload JSON files
* Connect MongoDB collections
* Connect external REST APIs
* Automatic field detection
* Dynamic field mapping for non-standard schemas

### Cost Analytics

* Cluster Overview
* Namespace Deep Dive
* Cost Breakdown Visualization
* Resource Efficiency Analysis
* Right-Sizing Recommendations

### Forecasting

* Linear Trend Forecasting
* SARIMA Forecasting
* Prophet Forecasting

### Budget Monitoring

* Budget Alert System
* Forecast vs Budget Comparison
* Overspend Detection

### Model Evaluation

* Forecast Backtesting
* MAPE
* MAE
* RMSE
* Accuracy Metrics

## Technology Stack

### Frontend

* React
* React Router
* Recharts

### Backend

* FastAPI
* Pandas
* NumPy
* Prophet
* Statsmodels
* PyMongo

## Project Structure

backend/

* main.py
* database.py
* requirements.txt

frontend/

* src/
* public/
* package.json

## Running the Backend

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Running the Frontend

```bash
npm install
npm start
```

## Supported Input Sources

### Standard Schema

```json
{
  "name": "frontend",
  "date": "2025-01-01",
  "cpuCost": 10,
  "ramCost": 5,
  "pvCost": 2,
  "podCount": 4,
  "totalCost": 17,
  "cpuEfficiency": 0.8,
  "ramEfficiency": 0.75
}
```

### Custom Schemas

The dashboard supports custom field names through dynamic field mapping.

Example:

```json
{
  "namespace_name": "frontend",
  "usage_date": "2025-01-01",
  "cpu_cost_usd": 10
}
```

## Author

Architaa A
