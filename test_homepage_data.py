
from src.dashboard.homepage_data import load_homepage_data


data = load_homepage_data()


print("\n====================================")
print("RISKWEAVE HOMEPAGE DATA TEST")
print("====================================")

print("\nWEATHER")
print("Latest historical date:", data["weather_date"])
print("District count:", data["weather_district_count"])
print("Mean temperature:", data["temperature_mean"])
print("Mean rainfall:", data["rainfall_mean"])
print("Mean humidity:", data["humidity_mean"])

print("\nWEATHER FORECAST")
print("Latest forecast date:", data["forecast_date"])
print("Forecast district count:", data["forecast_district_count"])

print("\nDENGUE")
print("Latest reporting year:", data["dengue_year"])
print("Latest reporting week:", data["dengue_week"])
print("Total dengue cases:", data["dengue_total"])
print("District count:", data["dengue_district_count"])

print("\nENVIRONMENTAL ANOMALIES")
print("District count:", data["anomaly_district_count"])
print("District-days with anomalies:", data["total_anomaly_days"])
print("Rainfall anomalies:", data["rainfall_anomalies"])
print("Temperature anomalies:", data["temperature_anomalies"])
print("Humidity anomalies:", data["humidity_anomalies"])

print("\n====================================")
print("TEST COMPLETED")
print("====================================")
