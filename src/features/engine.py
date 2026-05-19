import pandas as pd
import numpy as np


def process_raw_to_features(raw_path: str):
    df = pd.read_csv(raw_path)
    mapping = {
        'SystemCodeNumber': 'lot_id', 'Capacity': 'capacity',
        'Occupancy': 'occupied', 'LastUpdated': 'last_updated',
    }
    df = df.rename(columns=mapping)
    expected = list(mapping.values())
    missing_cols = [c for c in expected if c not in set(df.columns.tolist())]
    if len(missing_cols) > 0:
        if len(df.columns) >= 4:
            df.columns = expected[:len(df.columns)]
        else:
            raise ValueError(f"CSV has {len(df.columns)} columns, need 4. Missing: {missing_cols}")

    df['timestamp'] = pd.to_datetime(df['last_updated'], utc=True)
    df['ts_bucket'] = df['timestamp'].dt.floor('15min')
    df['total_slots'] = df['capacity'].replace(0, np.nan)
    if df['total_slots'].isna().any():
        print(f"Warning: {df['total_slots'].isna().sum()} rows with capacity=0 filled with 500")
        df['total_slots'] = df['total_slots'].fillna(500)

    lot_ts = df.groupby(['lot_id', 'ts_bucket']).agg(
        occupied_slots=('occupied', 'mean'),
        total_slots=('total_slots', 'max')
    ).reset_index()
    lot_ts['total_slots'] = lot_ts['total_slots'].replace(0, np.nan).fillna(500).astype(int)
    lot_ts['occupancy_rate'] = lot_ts['occupied_slots'] / lot_ts['total_slots']
    lot_ts = lot_ts.sort_values(['lot_id', 'ts_bucket']).reset_index(drop=True)
    lot_ts['occupancy_rate'] = lot_ts.groupby('lot_id')['occupancy_rate'].transform(
        lambda s: s.ffill().fillna(0)
    )

    g = lot_ts.groupby('lot_id')
    lot_ts['net_flux'] = g['occupied_slots'].diff().fillna(0)
    lot_ts['occ_lag_15m'] = g['occupancy_rate'].shift(1)
    lot_ts['occ_lag_1h'] = g['occupancy_rate'].shift(4)

    lot_ts['pe_arrival_rate'] = g['occupied_slots'].transform(
        lambda s: s.diff().clip(lower=0).rolling(4, min_periods=1).mean()
    )
    lot_ts['pe_departure_rate'] = g['occupied_slots'].transform(
        lambda s: (-s.diff()).clip(lower=0).rolling(4, min_periods=1).mean()
    )
    lot_ts['pe_turnover'] = g['occupied_slots'].transform(
        lambda s: s.diff().abs().rolling(8, min_periods=1).sum()
    )
    mean_occ = g['occupancy_rate'].transform(lambda s: s.expanding().mean().shift(1))
    std_occ = g['occupancy_rate'].transform(lambda s: s.expanding().std(ddof=1).shift(1))
    lot_ts['pe_anomaly'] = ((lot_ts['occupancy_rate'] - mean_occ).abs() > 2 * std_occ).astype(float)
    lot_ts['pe_anomaly'] = lot_ts['pe_anomaly'].fillna(0)
    cusum = g['occupancy_rate'].transform(
        lambda s: (s - s.rolling(8, min_periods=1).mean()).fillna(0)
    )
    threshold = lot_ts.groupby('lot_id')['occupancy_rate'].transform(
        lambda s: ((s - s.rolling(8, min_periods=1).mean()).fillna(0)
                    .rolling(4, min_periods=1).std().fillna(0) * 1.5)
    )
    lot_ts['pe_change_point'] = (cusum.abs() > threshold).astype(float)

    lot_ts['hour'] = lot_ts['ts_bucket'].dt.hour
    lot_ts['hour_sin'] = np.sin(2 * np.pi * lot_ts['hour'] / 24)
    lot_ts['hour_cos'] = np.cos(2 * np.pi * lot_ts['hour'] / 24)
    lot_ts['hour_sq'] = (lot_ts['hour'] - 12) / 12

    lot_ts['dow'] = lot_ts['ts_bucket'].dt.dayofweek
    lot_ts['dow_sin'] = np.sin(2 * np.pi * lot_ts['dow'] / 7)
    lot_ts['dow_cos'] = np.cos(2 * np.pi * lot_ts['dow'] / 7)
    lot_ts['is_weekend'] = (lot_ts['dow'] >= 5).astype(float)

    lot_ts['occ_roll_mean_3h'] = g['occupancy_rate'].transform(
        lambda s: s.rolling(12, min_periods=1).mean().shift(1)
    )
    lot_ts['occ_roll_std_3h'] = g['occupancy_rate'].transform(
        lambda s: s.rolling(12, min_periods=1).std(ddof=1).shift(1)
    )
    lot_ts['occ_acceleration'] = g['net_flux'].diff().fillna(0)

    lot_ts['target'] = g['occupancy_rate'].shift(-1)

    pe_cols = ['pe_arrival_rate', 'pe_departure_rate', 'pe_turnover',
               'pe_anomaly', 'pe_change_point']
    drop_cols = ['target', 'occ_lag_15m', 'occ_lag_1h', 'occ_roll_mean_3h']
    lot_ts = lot_ts.dropna(subset=drop_cols)
    lot_ts[pe_cols] = lot_ts[pe_cols].fillna(0)
    lot_ts['occ_roll_std_3h'] = lot_ts['occ_roll_std_3h'].fillna(0)

    print(f"Processed {len(lot_ts)} Birmingham observations with {len(pe_cols)} PE features + time/trend features.")
    return lot_ts
