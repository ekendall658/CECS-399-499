from data_cleaning import clean_weather_data

weather_df = clean_weather_data("weather.csv")

print("Weather cleaned successfully.")
print(weather_df.head())
