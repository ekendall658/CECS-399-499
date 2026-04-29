import argparse
import boto3
import os
from io import BytesIO
from pathlib import Path

import pandas as pd

BUCKET_NAME = 'energy-lake-cecs'
DEFAULT_REGION = 'us-east-2'


def s3_client(region_name=DEFAULT_REGION):
    return boto3.client(
        's3',
        region_name=region_name,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )


def read_csv_from_s3(s3, key, **kwargs):
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_csv(obj['Body'], **kwargs)


def upload_df_to_s3(s3, df, s3_key, fmt='csv'):
    buffer = BytesIO()
    if fmt == 'csv':
        df.to_csv(buffer, index=False)
    elif fmt == 'parquet':
        df.to_parquet(buffer, index=False)
    else:
        raise ValueError(f'Unsupported upload format: {fmt}')

    buffer.seek(0)
    s3.upload_fileobj(buffer, BUCKET_NAME, s3_key)
    print(f"✅ Uploaded s3://{BUCKET_NAME}/{s3_key}")


def convert_eia_to_utc(df):
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=5)
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

    df = df.sort_values('timestamp')
    df = df.set_index('timestamp')

    full_range = pd.date_range(
        start='2021-01-01 00:00',
        end='2025-12-31 23:00',
        freq='h',
        tz='UTC'
    )

    df = df.reindex(full_range)
    df.index.name = 'timestamp'
    df = df.reset_index()

    df = df.rename(columns={
        'Day-ahead demand forecast': 'demand_forecast_mwh',
        'Net generation': 'net_generation_mwh',
        'Total interchange': 'net_interchange_mwh'
    })

    for col in df.columns:
        if col != 'timestamp':
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def build_weight_lookup(weights_df):
    years = [2021, 2022, 2023, 2024, 2025]
    lookup = {year: dict(zip(weights_df['city'], weights_df[f'weight_{year}'])) for year in years}
    return lookup


def apply_weather_weights(weather_df, weights_df):
    weather_df = weather_df.copy()
    weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'], utc=True, errors='coerce')
    weather_df['year'] = weather_df['timestamp'].dt.year

    lookup = build_weight_lookup(weights_df)

    cities = [
        'nashville', 'memphis', 'knoxville', 'chattanooga',
        'clarksville', 'murfreesboro', 'franklin', 'johnson_city',
        'jackson', 'hendersonville'
    ]

    metrics = [
        'temperature_2m', 'relative_humidity_2m', 'precipitation',
        'cloud_cover', 'wind_speed_10m', 'shortwave_radiation'
    ]

    for city in cities:
        weather_df[f'{city}_weight'] = weather_df['year'].map(lambda y: lookup.get(y, {}).get(city, pd.NA))

    for metric in metrics:
        weighted_col = f'weighted_{metric}'
        weather_df[weighted_col] = 0.0
        for city in cities:
            x_col = f'{city}_{metric}'
            w_col = f'{city}_weight'
            if x_col not in weather_df.columns:
                raise ValueError(f'Missing weather column: {x_col}')
            weather_df[x_col] = pd.to_numeric(weather_df[x_col], errors='coerce')
            weather_df[w_col] = pd.to_numeric(weather_df[w_col], errors='coerce')
            weather_df[weighted_col] += weather_df[x_col] * weather_df[w_col]

    return weather_df


def ensure_dirs(*paths):
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def main(upload=True, local_save=True, region=DEFAULT_REGION):
    s3 = s3_client(region)
    ensure_dirs('silver', 'gold')

    print('📥 Reading raw ingestion data from S3...')
    eia_df = read_csv_from_s3(s3, 'ingestion/tva_eia_21_25.csv')
    weights_df = read_csv_from_s3(s3, 'ingestion/tn_selected_city_population_weights.csv')
    weather_df = read_csv_from_s3(s3, 'ingestion/tn_weather_top10_21_25.csv')

    print('⏰ Converting EIA timestamps to UTC...')
    eia_utc = convert_eia_to_utc(eia_df)
    if local_save:
        eia_utc.to_csv('silver/tva_eia_21_25_utc.csv', index=False)
        print('✅ Saved silver/tva_eia_21_25_utc.csv')
    if upload:
        upload_df_to_s3(s3, eia_utc, 'gold/tva_eia_21_25_utc.csv', fmt='csv')

    print('⚖️ Applying weather weights...')
    weighted_weather = apply_weather_weights(weather_df, weights_df)
    if local_save:
        weighted_weather.to_parquet('gold/tn_weighted_weather_21_25.parquet', index=False)
        print('✅ Saved gold/tn_weighted_weather_21_25.parquet')
    if upload:
        upload_df_to_s3(s3, weighted_weather, 'gold/tn_weighted_weather_21_25.parquet', fmt='parquet')

    print('\n✅ S3-only transformation complete.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run transformation using S3 source files only.')
    parser.add_argument('--no-upload', action='store_true', help='Do not upload outputs back to S3')
    parser.add_argument('--no-local', action='store_true', help='Do not save local output files')
    parser.add_argument('--region', default=DEFAULT_REGION, help='AWS region for S3 access')
    args = parser.parse_args()

    main(upload=not args.no_upload, local_save=not args.no_local, region=args.region)
