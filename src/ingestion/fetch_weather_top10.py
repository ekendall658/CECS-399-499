import requests
import pandas as pd
import os

# --- CONFIGURATION ---
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"
WEATHER_FILENAME = "tn_weather_top10_21_25.csv"

CITIES = {
    "nashville": {"lat": 36.16, "lon": -86.78},
    "memphis": {"lat": 35.15, "lon": -90.05},
    "knoxville": {"lat": 35.96, "lon": -83.92},
    "chattanooga": {"lat": 35.04, "lon": -85.30},
    "clarksville": {"lat": 36.53, "lon": -87.36},
    "murfreesboro": {"lat": 35.85, "lon": -86.39},
    "franklin": {"lat": 35.93, "lon": -86.87},
    "johnson_city": {"lat": 36.31, "lon": -82.35},
    "jackson": {"lat": 35.61, "lon": -88.81},
    "hendersonville": {"lat": 36.30, "lon": -86.62}
}

HOURLY_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation"
]


def fetch_comprehensive_weather():
    print(f"Starting API call for {len(CITIES)} cities...")

    url = "https://archive-api.open-meteo.com/v1/archive"

    city_names = list(CITIES.keys())
    latitudes = ",".join(str(CITIES[name]["lat"]) for name in city_names)
    longitudes = ",".join(str(CITIES[name]["lon"]) for name in city_names)

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(HOURLY_PARAMS),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC"
    }

    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    data_json = response.json()

    # If only one location is returned, wrap it so logic still works
    if isinstance(data_json, dict):
        data_json = [data_json]

    city_dfs = []

    for i, city_name in enumerate(city_names):
        hourly = data_json[i]["hourly"]

        df_city = pd.DataFrame({
            "timestamp": pd.to_datetime(hourly["time"], utc=True)
        })

        for param in HOURLY_PARAMS:
            df_city[f"{city_name}_{param}"] = hourly[param]

        city_dfs.append(df_city.set_index("timestamp"))

    full_df = pd.concat(city_dfs, axis=1).reset_index()
    return full_df


if __name__ == "__main__":
    df_weather = fetch_comprehensive_weather()

    save_path = os.path.join(os.getcwd(), WEATHER_FILENAME)
    df_weather.to_csv(save_path, index=False)

    print(f"\nSUCCESS: Data saved to {save_path}")
    print(f"Rows: {len(df_weather)} | Columns: {len(df_weather.columns)}")
    print(df_weather.info())
    print(df_weather.head())