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
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
bucket_name = 'energy-lake-cecs'

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3"""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

def main():
    print("🚀 Starting Ingestion Pipeline...")

    # Ensure local folders exist
    Path("bronze").mkdir(parents=True, exist_ok=True)
    Path("silver").mkdir(parents=True, exist_ok=True)

    # Fetch EIA data
    print("\n📊 Fetching EIA data...")
    df_eia = fetch_eia_master_data()
    if df_eia is not None:
        eia_file = Path("bronze/tva_eia_21_25.csv")
        df_eia.to_csv(eia_file, index=False)
        upload_to_s3(str(eia_file), f'ingestion/{eia_file.name}')

    # Fetch weather data
    print("\n🌤️ Fetching weather data...")
    df_weather = fetch_comprehensive_weather()
    if df_weather is not None:
        weather_file = Path("bronze/tn_weather_top10_21_25.csv")
        df_weather.to_csv(weather_file, index=False)
        upload_to_s3(str(weather_file), f'ingestion/{weather_file.name}')

    # Fetch weather weights
    print("\n⚖️ Processing weather weights...")
    try:
        fetch_weather_weights.main()  # Call the module's main function
        weights_file = Path('silver/tn_selected_city_population_weights.csv')
        if weights_file.exists():
            upload_to_s3(str(weights_file), f'ingestion/{weights_file.name}')
    except Exception as e:
        print(f"⚠️ Weather weights processing failed: {e}")

    print("\n✅ Ingestion Pipeline Complete!")

if __name__ == "__main__":
    main()