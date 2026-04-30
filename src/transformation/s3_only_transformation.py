import argparse
import boto3
import os
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

BUCKET_NAME = 'energy-lake-cecs'
DEFAULT_REGION = 'us-east-2'
S3_PREFIX = 'bronze/'

DOE_KEYS = [
    f'{S3_PREFIX}2021_DOE417.xls',
    f'{S3_PREFIX}2022_DOE417.xls',
    f'{S3_PREFIX}2023_DOE417.xls'
]

EAGLEI_KEYS = [
    f'{S3_PREFIX}eaglei_outages_2021.csv',
    f'{S3_PREFIX}eaglei_outages_2022.csv',
    f'{S3_PREFIX}eaglei_outages_2023.csv',
    f'{S3_PREFIX}eaglei_outages_2024.csv',
    f'{S3_PREFIX}eaglei_outages_2025.csv'
]

RAW_S3_KEYS = {
    'eia': f'{S3_PREFIX}tva_eia_21_25.csv',
    'weights': f'{S3_PREFIX}tn_selected_city_population_weights.csv',
    'weather': f'{S3_PREFIX}tn_weather_top10_21_25.csv'
}

DOE_LOCAL = [
    Path('local_data/bronze/2021_DOE417.xls'),
    Path('local_data/bronze/2022_DOE417.xls'),
    Path('local_data/bronze/2023_DOE417.xls')
]

EAGLEI_LOCAL = [
    Path('local_data/bronze/eaglei_outages_2021.csv'),
    Path('local_data/bronze/eaglei_outages_2022.csv'),
    Path('local_data/bronze/eaglei_outages_2023.csv'),
    Path('local_data/bronze/eaglei_outages_2024.csv'),
    Path('local_data/bronze/eaglei_outages_2025.csv')
]

CHUNK_SIZE = 200_000


def s3_client(region_name=DEFAULT_REGION):
    return boto3.client(
        's3',
        region_name=region_name,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )


def download_s3_to_tempfile(s3, key):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        s3.download_fileobj(BUCKET_NAME, key, tmp)
        tmp.close()
        return tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise


def read_csv_from_s3(s3, key, **kwargs):
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_csv(obj['Body'], **kwargs)


def read_excel_from_s3(s3, key, **kwargs):
    path = download_s3_to_tempfile(s3, key)
    try:
        return pd.read_excel(path, **kwargs)
    finally:
        os.unlink(path)


def read_csv_chunks_from_s3(s3, key, chunksize, **kwargs):
    path = download_s3_to_tempfile(s3, key)
    try:
        yield from pd.read_csv(path, chunksize=chunksize, **kwargs)
    finally:
        os.unlink(path)


def upload_file_to_s3(s3, path, key):
    s3.upload_file(str(path), BUCKET_NAME, key)
    print(f'✅ Uploaded s3://{BUCKET_NAME}/{key}')


def upload_df_to_s3(s3, df, key, fmt='csv'):
    buffer = BytesIO()
    if fmt == 'csv':
        df.to_csv(buffer, index=False)
    elif fmt == 'parquet':
        df.to_parquet(buffer, index=False)
    else:
        raise ValueError(f'Unsupported upload format: {fmt}')
    buffer.seek(0)
    s3.upload_fileobj(buffer, BUCKET_NAME, key)
    print(f'✅ Uploaded s3://{BUCKET_NAME}/{key}')


def ensure_dirs(*paths):
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def local_fallback_path(key):
    basename = Path(key).name
    if basename in {p.name for p in DOE_LOCAL}:
        return next(p for p in DOE_LOCAL if p.name == basename)
    if basename in {p.name for p in EAGLEI_LOCAL}:
        return next(p for p in EAGLEI_LOCAL if p.name == basename)
    return None


def resolve_eia_missing(df):
    df = df.copy()
    eia_cols = [
        'demand_forecast_mwh',
        'actual_demand_mwh',
        'net_generation_mwh',
        'net_interchange_mwh'
    ]

    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    for col in eia_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.set_index('timestamp').sort_index()
    df = df.asfreq('h')
    df[eia_cols] = df[eia_cols].interpolate(
        method='time',
        limit=3,
        limit_area='inside'
    )
    return df.reset_index()


def feature_engineering(df):
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df.set_index('timestamp')

    df['balance_error'] = (
        (df['net_generation_mwh'] - df['net_interchange_mwh'])
        - df['actual_demand_mwh']
    )
    df['percent_forecast_error'] = (
        (df['actual_demand_mwh'] - df['demand_forecast_mwh'])
        / df['demand_forecast_mwh']
        * 100
    )
    df['demand_ramp_rate_pct'] = (
        df['actual_demand_mwh']
        .pct_change(fill_method=None)
        * 100
    )
    df['demand_rolling_mean_24h'] = (
        df['actual_demand_mwh']
        .rolling('24h', min_periods=1)
        .mean()
    )
    df['demand_rolling_std_24h'] = (
        df['actual_demand_mwh']
        .rolling('24h', min_periods=1)
        .std()
    )
    df['demand_residual'] = df['actual_demand_mwh'] - df['demand_rolling_mean_24h']
    df['demand_zscore'] = df['demand_residual'] / df['demand_rolling_std_24h']

    df['hour'] = df.index.hour
    df['month'] = df.index.month
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    df = df.drop(columns=['hour', 'month'])

    return df


def process_doe417(s3, upload, local_save):
    outputs = []
    all_raw_data = []

    for key, fallback in zip(DOE_KEYS, DOE_LOCAL):
        try:
            df = read_excel_from_s3(s3, key, header=1)
            print(f'✅ Loaded {key} from S3')
        except Exception as e:
            if fallback.exists():
                print(f'⚠️ S3 missing {key}, falling back to local {fallback}')
                df = pd.read_excel(fallback, header=1)
            else:
                print(f'⚠️ Skipping missing DOE file: {key} ({e})')
                continue

        rename_map = {
            'Event Month': 'Month',
            'Date Event Began ': 'Date Event Began',
            'Time Event Began ': 'Time Event Began',
            'Date of Restoration ': 'Date of Restoration',
            'Time of Restoration ': 'Time of Restoration',
            'Area Affected ': 'Area Affected',
            'Alert Criteria ': 'Alert Criteria',
            'Event Type ': 'Event Type',
            'Number of Customers Affected ': 'Number of Customers Affected'
        }
        df = df.rename(columns=rename_map)
        invalid_entries = ['Unknown', '#NAME?', 'unknown', 'n/a', 'N/A', 'NA', 'UNK', 'None']
        df = df.replace(invalid_entries, np.nan)
        df['source_year'] = int(Path(key).stem[:4])
        if 'Date Event Began' in df.columns and 'Time Event Began' in df.columns:
            df['event_start_utc'] = pd.to_datetime(df['Date Event Began'], errors='coerce').dt.strftime('%Y-%m-%d')
            df['event_start_utc'] = pd.to_datetime(df['event_start_utc'] + ' ' + df['Time Event Began'].astype(str), errors='coerce')
            df['event_start_utc'] = df['event_start_utc'].dt.tz_localize('America/Chicago', ambiguous='NaT', nonexistent='NaT').dt.tz_convert('UTC')
        if 'Date of Restoration' in df.columns and 'Time of Restoration' in df.columns:
            df['event_end_utc'] = pd.to_datetime(df['Date of Restoration'], errors='coerce').dt.strftime('%Y-%m-%d')
            df['event_end_utc'] = pd.to_datetime(df['event_end_utc'] + ' ' + df['Time of Restoration'].astype(str), errors='coerce')
            df['event_end_utc'] = df['event_end_utc'].dt.tz_localize('America/Chicago', ambiguous='NaT', nonexistent='NaT').dt.tz_convert('UTC')

        all_raw_data.append(df)

    if not all_raw_data:
        raise ValueError('No DOE417 files were available from S3 or local fallback.')

    df_master = pd.concat(all_raw_data, ignore_index=True)
    df_final = df_master[df_master['Area Affected'].astype(str).str.contains('Tennessee', case=False, na=False)].copy()
    fill_values = {
        'Event Type': 'System Operations/Other',
        'Alert Criteria': 'Not Specified',
        'Number of Customers Affected': 0,
        'Demand Loss (MW)': 0.0
    }
    df_final = df_final.fillna(value=fill_values)
    df_final['Number of Customers Affected'] = pd.to_numeric(df_final['Number of Customers Affected'], errors='coerce').fillna(0).astype(int)
    df_final['Demand Loss (MW)'] = pd.to_numeric(df_final['Demand Loss (MW)'], errors='coerce').astype(float)

    out_path = Path('silver/doe417_tennessee_cleaned_final.csv')
    if local_save:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(out_path, index=False)
        print(f'✅ Saved {out_path}')
    if upload:
        upload_file_to_s3(s3, out_path, 'gold/doe417_tennessee_cleaned_final.csv')
    return df_final


def detect_outage_col(columns):
    cols = [c.strip() for c in columns]
    candidates = ['customers_out', 'sum', 'customer_out', 'outages']
    for c in candidates:
        if c in cols:
            return c
    for c in cols:
        if 'customer' in c.lower():
            return c
    raise ValueError(f'Required outage column not detected in: {cols}')


def process_eaglei(s3, upload, local_save):
    output_path = Path('silver/eaglei_tennessee_cleaned_final.csv')
    all_files = []
    for key, fallback in zip(EAGLEI_KEYS, EAGLEI_LOCAL):
        try:
            path = download_s3_to_tempfile(s3, key)
            all_files.append(path)
            print(f'✅ Downloaded {key} for EAGLE-I processing')
        except Exception:
            if fallback.exists():
                print(f'⚠️ S3 missing {key}, using local fallback {fallback}')
                all_files.append(str(fallback))
            else:
                print(f'⚠️ Skipping missing EAGLE-I source file: {key}')

    if not all_files:
        raise ValueError('No EAGLE-I source files were available from S3 or local fallback.')

    write_header = True
    for file_path in all_files:
        for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
            if write_header and output_path.exists():
                output_path.unlink()
            outage_col = detect_outage_col(chunk.columns)
            chunk = chunk[chunk['state'] == 'Tennessee'].copy()
            if chunk.empty:
                continue
            chunk['run_start_time'] = pd.to_datetime(chunk['run_start_time'], errors='coerce')
            chunk = chunk.dropna(subset=['run_start_time'])
            if chunk['run_start_time'].dt.tz is None:
                chunk['run_start_time'] = chunk['run_start_time'].dt.tz_localize('UTC')
            chunk['run_start_time'] = chunk['run_start_time'].dt.tz_convert('US/Central')
            chunk['date'] = chunk['run_start_time'].dt.date
            daily = chunk.groupby(['county', 'date'], as_index=False)[outage_col].max()
            daily = daily.rename(columns={outage_col: 'customers_out'})
            daily['customers_out'] = pd.to_numeric(daily['customers_out'], errors='coerce').fillna(0).astype(int)
            daily.to_csv(output_path, mode='a', header=write_header, index=False)
            write_header = False
        if str(file_path).startswith(tempfile.gettempdir()):
            os.unlink(file_path)

    if not output_path.exists():
        raise ValueError('EAGLE-I output was not written.')

    df_final = pd.read_csv(output_path)
    df_final = df_final.groupby(['county', 'date'], as_index=False)['customers_out'].max()
    df_final['customers_out'] = df_final['customers_out'].astype(int)
    df_final = df_final.sort_values(by=['date', 'county'])
    df_final.to_csv(output_path, index=False)

    if local_save:
        print(f'✅ Saved {output_path}')
    if upload:
        upload_file_to_s3(s3, output_path, 'gold/eaglei_tennessee_cleaned_final.csv')

    return df_final


def apply_weather_weights_from_data(weather_df, weights_df, upload, local_save):
    weighted = weather_df.copy()
    weighted['timestamp'] = pd.to_datetime(weighted['timestamp'], utc=True, errors='coerce')
    weighted['year'] = weighted['timestamp'].dt.year
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
        weighted[f'{city}_weight'] = weighted['year'].map(lambda y: lookup.get(y, {}).get(city, pd.NA))
    for metric in metrics:
        weighted_col = f'weighted_{metric}'
        weighted[weighted_col] = 0.0
        for city in cities:
            x_col = f'{city}_{metric}'
            w_col = f'{city}_weight'
            if x_col not in weighted.columns:
                raise ValueError(f'Missing weather column: {x_col}')
            weighted[x_col] = pd.to_numeric(weighted[x_col], errors='coerce')
            weighted[w_col] = pd.to_numeric(weighted[w_col], errors='coerce')
            weighted[weighted_col] += weighted[x_col] * weighted[w_col]
    out_path = Path('gold/tn_weighted_weather_21_25.parquet')
    if local_save:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        weighted.to_parquet(out_path, index=False)
        print(f'✅ Saved {out_path}')
    if upload:
        upload_df_to_s3(s3, weighted, 'gold/tn_weighted_weather_21_25.parquet', fmt='parquet')
    return weighted


def main(upload=True, local_save=True, region=DEFAULT_REGION):
    s3 = s3_client(region)
    ensure_dirs('silver', 'gold')

    print('📥 Reading raw ingestion data from S3...')
    eia_df = read_csv_from_s3(s3, RAW_S3_KEYS['eia'])
    weights_df = read_csv_from_s3(s3, RAW_S3_KEYS['weights'])
    weather_df = read_csv_from_s3(s3, RAW_S3_KEYS['weather'])

    print('⏰ Converting EIA timestamps to UTC...')
    eia_utc = convert_eia_to_utc(eia_df)
    silver_eia_utc = Path('silver/tva_eia_21_25_utc.csv')
    if local_save:
        eia_utc.to_csv(silver_eia_utc, index=False)
        print(f'✅ Saved {silver_eia_utc}')
    if upload:
        upload_df_to_s3(s3, eia_utc, 'gold/tva_eia_21_25_utc.csv', fmt='csv')

    print('🧹 Resolving EIA missing values...')
    eia_pre_feature = resolve_eia_missing(eia_utc)
    silver_pre_feature = Path('silver/EIA_pre_feature.csv')
    if local_save:
        eia_pre_feature.to_csv(silver_pre_feature, index=False)
        print(f'✅ Saved {silver_pre_feature}')

    print('🔧 Running feature engineering...')
    features = feature_engineering(eia_pre_feature)
    features_path = Path('silver/EIA_features_Final.csv')
    if local_save:
        features.to_csv(features_path, index=False)
        print(f'✅ Saved {features_path}')
    if upload:
        upload_df_to_s3(s3, features, 'gold/EIA_features_Final.csv', fmt='csv')

    print('⚖️ Applying weather weights...')
    apply_weather_weights_from_data(weather_df, weights_df, upload=upload, local_save=local_save)

    print('🏭 Processing DOE417 data...')
    process_doe417(s3, upload=upload, local_save=local_save)

    print('🦅 Processing EAGLE-I data...')
    process_eaglei(s3, upload=upload, local_save=local_save)

    print('\n✅ Full S3-only transformation complete.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run full transformation pipeline with S3 source files.')
    parser.add_argument('--no-upload', action='store_true', help='Do not upload outputs back to S3')
    parser.add_argument('--no-local', action='store_true', help='Do not save local output files')
    parser.add_argument('--region', default=DEFAULT_REGION, help='AWS region for S3 access')
    args = parser.parse_args()

    main(upload=not args.no_upload, local_save=not args.no_local, region=args.region)
