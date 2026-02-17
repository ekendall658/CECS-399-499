"""
Weather analysis for Nashville BNA
Date range:(01/01/2015-01/01/2025)
Data source: NOAA National Centers for Environmental Information (NCEI)
Dataset: Daily Summaries(CSV format)
Station ID: Nashville BNA airport GHCND:USW00013897
Data includes daily maximum temperature (TMAX), minimum temperature (TMIN), average temperature (TAVG), precipitation (PRCP), and average wind speed (AWND).
Unit: standard units (°F for temperature, inches for precipitation, mph for wind speed)
"""




# Nashville BNA weather analysis.py
import csv
import numpy as np
import pandas as pd
from datetime import datetime

def clean_weather_data(file_path):
    weather_df = pd.read_csv(file_path)
    weather_df["DATE"] = pd.to_datetime(weather_df["DATE"])
    weather_df = weather_df.replace(-9999, np.nan)
    weather_df = weather_df[["DATE", "TMAX", "TMIN", "TAVG", "PRCP", "AWND"]]
    return weather_df


