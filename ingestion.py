import boto3
import os
import sys
import pandas as pd
from pathlib import Path
sys.path.append('src/ingestion')

from fetch_eia import fetch_eia_master_data
from fetch_weather_top10 import fetch_comprehensive_weather

# Import weather weights processing
sys.path.append('src/ingestion')
import fetch_weather_weights

# S3 Configuration
s3 = boto3.client(
    's3',
    region_name='us-east-2',
    aws_access_key_id='',
    aws_secret_access_key=''
)
bucket_name = 'energy-lake-cecs'

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3"""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

def fetch_weather_weights():
    """Wrapper to get weather weights data"""
    # This mimics the logic from fetch_weather_weights.py
    INPUT_CSV = Path("local_data/bronze/Tennessee_pop.csv")
    if not INPUT_CSV.exists():
        print(f"⚠️ Population data not found: {INPUT_CSV}")
        return None

    # Run the processing logic (simplified version)
    df = pd.read_csv(INPUT_CSV)
    # Add your processing logic here or call the functions from the module
    # For now, return the processed dataframe
    return df

def main():
    print("🚀 Starting Ingestion Pipeline...")

    # Fetch EIA data
    print("\n📊 Fetching EIA data...")
    df_eia = fetch_eia_master_data()
    if df_eia is not None:
        eia_file = 'tva_eia_21_25.csv'
        df_eia.to_csv(eia_file, index=False)
        upload_to_s3(eia_file, f'ingestion/{eia_file}')
        os.remove(eia_file)  # Clean up local file

    # Fetch weather data
    print("\n🌤️ Fetching weather data...")
    df_weather = fetch_comprehensive_weather()
    if df_weather is not None:
        weather_file = 'tn_weather_top10_21_25.csv'
        df_weather.to_csv(weather_file, index=False)
        upload_to_s3(weather_file, f'ingestion/{weather_file}')
        os.remove(weather_file)  # Clean up local file

    # Fetch weather weights
    print("\n⚖️ Processing weather weights...")
    try:
        # Run the weather weights processing
        fetch_weather_weights.main()  # Call the main function
        weights_file = 'local_data/silver/tn_selected_city_population_weights.csv'
        if os.path.exists(weights_file):
            upload_to_s3(weights_file, f'ingestion/tn_selected_city_population_weights.csv')
            # Don't remove since it's in local_data
    except Exception as e:
        print(f"⚠️ Weather weights processing failed: {e}")

    print("\n✅ Ingestion Pipeline Complete!")

if __name__ == "__main__":
    main()