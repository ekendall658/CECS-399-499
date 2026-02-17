import pandas as pd

def merge_energy_weather(energy_df, weather_df):
    energy_df["DATE"] = pd.to_datetime(energy_df["DATE"])
    weather_df["DATE"] = pd.to_datetime(weather_df["DATE"])
    merged = energy_df.merge(weather_df, on="DATE", how="inner")
    return merged
