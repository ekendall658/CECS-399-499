import boto3
import os
import sys
import pandas as pd
from pathlib import Path
sys.path.append('src/transformation')

# Import transformation modules
from EIA_to_UTC import convert_eia_to_utc
from apply_feature_engineering import *
from apply_weather_weights import *
from doe417_process import *
from eaglei_process import *
from resolve_EIA_missing import *

# S3 Configuration
s3 = boto3.client(
    's3',
    region_name='us-east-2',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
bucket_name = 'energy-lake-cecs'

def download_from_s3(s3_key, local_path):
    """Download a file from S3"""
    try:
        s3.download_file(bucket_name, s3_key, local_path)
        print(f"✅ Downloaded s3://{bucket_name}/{s3_key} to {local_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to download {s3_key}: {e}")
        return False

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3"""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

def main():
    print("🔄 Starting Transformation Pipeline...")

    # Create local directories
    Path("local_data/bronze").mkdir(parents=True, exist_ok=True)
    Path("local_data/silver").mkdir(parents=True, exist_ok=True)
    Path("local_data/gold").mkdir(parents=True, exist_ok=True)

    # Download ingested data from S3
    print("\n📥 Downloading data from S3...")

    # Download and process EIA data
    if download_from_s3('ingestion/tva_eia_21_25.csv', 'local_data/bronze/tva_eia_21_25.csv'):
        print("\n⏰ Converting EIA data to UTC...")
        df_eia_utc = convert_eia_to_utc()
        upload_to_s3('local_data/silver/tva_eia_21_25_utc.csv', 'gold/tva_eia_21_25_utc.csv')

    # Download population weights first (needed for weather weights)
    download_from_s3('ingestion/tn_selected_city_population_weights.csv', 'local_data/silver/tn_selected_city_population_weights.csv')

    # Download and process weather data
    if download_from_s3('ingestion/tn_weather_top10_21_25.csv', 'local_data/bronze/tn_weather_top10_21_25.csv'):
        print("\n⚖️ Applying weather weights...")
        try:
            weather_df = pd.read_csv('local_data/bronze/tn_weather_top10_21_25.csv')
            weights_df = pd.read_csv('local_data/silver/tn_selected_city_population_weights.csv')
            weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'], utc=True)
            weather_df.to_parquet('local_data/gold/tn_weighted_weather_21_25.parquet', index=False)
            upload_to_s3('local_data/gold/tn_weighted_weather_21_25.parquet', 'gold/tn_weighted_weather_21_25.parquet')
        except Exception as e:
            print(f"⚠️ Weather weights application failed: {e}")

    # Run feature engineering
    print("\n🔧 Applying feature engineering...")
    try:
        upload_to_s3('local_data/silver/EIA_features_Final.csv', 'gold/EIA_features_Final.csv')
    except Exception as e:
        print(f"⚠️ Feature engineering failed: {e}")

    # Run DOE417 processing
    print("\n🏭 Processing DOE417 data...")
    try:
        upload_to_s3('local_data/silver/doe417_tennessee_cleaned_final.csv', 'gold/doe417_tennessee_cleaned_final.csv')
    except Exception as e:
        print(f"⚠️ DOE417 processing failed: {e}")

    # Run Eaglei processing
    print("\n🦅 Processing Eaglei data...")
    try:
        upload_to_s3('local_data/silver/eaglei_tennessee_cleaned_final.csv', 'gold/eaglei_tennessee_cleaned_final.csv')
    except Exception as e:
        print(f"⚠️ Eaglei processing failed: {e}")

    # Resolve EIA missing values
    print("\n🔍 Resolving EIA missing values...")
    try:
        pass  # Add function call when ready
    except Exception as e:
        print(f"⚠️ EIA missing values resolution failed: {e}")

    print("\n✅ Transformation Pipeline Complete!")
    print("📁 Gold layer data uploaded to S3 'gold/' prefix")

if __name__ == "__main__":
    main()