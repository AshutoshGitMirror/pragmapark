import pandas as pd
import numpy as np


def add_pe_features(lot_ts: pd.DataFrame) -> pd.DataFrame:
    """Add parking-entropy features to a single-lot time series."""
    df = lot_ts.copy()
    total = df['total_slots'].iloc[0] if 'total_slots' in df.columns else 500

    df['net_flux'] = df['occupied_slots'].diff().fillna(0)
    df['occupancy_rate'] = df['occupied_slots'] / total

    df['occ_lag_15m'] = df['occupancy_rate'].shift(1).fillna(method='bfill')
    df['occ_lag_1h'] = df['occupancy_rate'].shift(4).fillna(method='bfill')

    df['pe_arrival_rate'] = df['net_flux'].clip(lower=0).rolling(4, min_periods=1).mean()
    df['pe_departure_rate'] = (-df['net_flux'].clip(upper=0)).rolling(4, min_periods=1).mean()
    df['pe_turnover'] = (df['pe_arrival_rate'] + df['pe_departure_rate']).clip(upper=1.0)
    scaled = df['occupied_slots'] / max(total, 1)
    df['pe_anomaly'] = ((scaled - scaled.rolling(24, min_periods=1).mean()).abs()
                        / scaled.rolling(24, min_periods=1).std(ddof=1).replace(0, 1))

    ts = df['occupied_slots'].values
    n = len(ts)
    if n >= 10:
        mu = np.mean(ts)
        cumsum = np.cumsum(ts - mu)
        S = np.max(cumsum) - np.min(cumsum)
        if S > 1e-9:
            diff = np.max(cumsum) - np.min(cumsum)
            df['pe_change_point'] = diff / max(n * np.std(ts, ddof=1), 1e-9)
        else:
            df['pe_change_point'] = 0.0
    else:
        df['pe_change_point'] = 0.0

    pe_cols = ['pe_arrival_rate', 'pe_departure_rate', 'pe_turnover', 'pe_anomaly', 'pe_change_point']
    lot_ts[pe_cols] = lot_ts[pe_cols].fillna(0)
    return df


def process_raw_to_features(csv_path: str) -> pd.DataFrame:
    raw = pd.read_csv(csv_path, parse_dates=['LastUpdated'])
    raw = raw.sort_values(['LotCode', 'LastUpdated']).reset_index(drop=True)

    raw.rename(columns={
        'LastUpdated': 'ts_bucket',
        'LotCode': 'lot_id',
        'Occupied': 'occupied_slots',
        'Capacity': 'total_slots',
    }, inplace=True)
    raw['ts_bucket'] = pd.to_datetime(raw['ts_bucket'])

    groups = []
    for lot_id, lot_df in raw.groupby('lot_id'):
        lot_df = lot_df.sort_values('ts_bucket').reset_index(drop=True)
        lot_df = add_pe_features(lot_df)
        groups.append(lot_df)
    df = pd.concat(groups, ignore_index=True)

    df['target'] = df['occupancy_rate']
    df = df.dropna(subset=['target'])
    print(f"Processed {len(df)} Birmingham observations with 6 PE features.")
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features required by training."""
    df = df.sort_values('ts_bucket').reset_index(drop=True)
    df['hour'] = df['ts_bucket'].dt.hour
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['hour_sq'] = (df['hour'] - 12) / 12
    df['dow'] = df['ts_bucket'].dt.dayofweek
    df['dow_sin'] = np.sin(2 * np.pi * df['dow'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['dow'] / 7)
    df['is_weekend'] = (df['dow'] >= 5).astype(float)
    return df
