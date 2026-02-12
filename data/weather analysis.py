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
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime


#load data
df = pd.read_csv('weather.csv')

#cleaning data
df["DATE"]=pd.to_datetime(df["DATE"])
df= df.replace(-9999, np.nan)

#selecting columns
df = df[["DATE","TMAX","TMIN","TAVG","PRCP","AWND"]]

#Show the first five rows of the cleaned data
print(df.head())

#Sort the data by date
df = df.sort_values("DATE")
print("Data shape:", df.shape)
print("\nMissing values:")
print(df.isnull().sum())

#Plotting the data

# 1.Plot temperature trends
plt.figure(figsize=(12, 6))
plt.plot(df["DATE"], df["TMAX"], label="TMAX", color="red")
plt.plot(df["DATE"], df["TMIN"], label="TMIN", color="blue")
plt.plot(df["DATE"], df["TAVG"], label="TAVG", color="green")
plt.xlabel("Date")
plt.ylabel("Temperature (°F)")
plt.title("Temperature Trends Over Time")
plt.legend()
plt.grid()
plt.show()  

# 2.Plot precipitation trends
plt.figure(figsize=(12, 6))
plt.plot(df["DATE"], df["PRCP"], label="Precipitation", color="blue")
plt.xlabel("Date")
plt.ylabel("Precipitation (inches)")
plt.title("Precipitation Trends Over Time")
plt.legend()
plt.grid()
plt.show()

#3.Plot average wind speed trends
plt.figure(figsize=(12, 6))
plt.plot(df["DATE"], df["AWND"], label="Average Wind Speed", color="black")
plt.xlabel("Date")
plt.ylabel("Average Wind Speed (mph)")     
plt.title("Average Wind Speed Trends Over Time")
plt.legend()
plt.grid()
plt.show()      

# 4.Identify extreme weather events
extreme_heat = df[df["TMAX"] > 95]
print("Extreme heat days (>95F):", len(extreme_heat))
extreme_cold = df[df["TMIN"] < 32]
print("Extreme cold days (<32F):", len(extreme_cold))   

