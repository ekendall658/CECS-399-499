import pandas as pd

def merge_energy_weather(energy_df, weather_df):
    # Ensure timestamp columns are datetime
    energy_df["timestamp"] = pd.to_datetime(energy_df["timestamp"])
    weather_df["timestamp"] = pd.to_datetime(weather_df["timestamp"])

    # Merge on hourly timestamp
    merged = energy_df.merge(weather_df, on="timestamp", how="inner")
    return merged
