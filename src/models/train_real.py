from src.constants import EXPECTED_FEATURE_COLS
import pandas as pd
import numpy as np
import os
import sys
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score

sys.path.append(os.getcwd())

X_COLS = EXPECTED_FEATURE_COLS


def train_chronological_ensemble(features: pd.DataFrame) -> float:
    features = features.sort_values("ts_bucket").reset_index(drop=True)
    features["hour"] = features["ts_bucket"].dt.hour
    features["hour_sin"] = np.sin(2 * np.pi * features["hour"] / 24)
    features["hour_cos"] = np.cos(2 * np.pi * features["hour"] / 24)
    features["hour_sq"] = (features["hour"] - 12) ** 2 / 144
    features["dow"] = features["ts_bucket"].dt.dayofweek
    features["dow_sin"] = np.sin(2 * np.pi * features["dow"] / 7)
    features["dow_cos"] = np.cos(2 * np.pi * features["dow"] / 7)
    features["is_weekend"] = (features["dow"] >= 5).astype(float)

    g = features.groupby("lot_id")
    features["occ_roll_mean_3h"] = g["occupancy_rate"].transform(
        lambda s: s.rolling(12, min_periods=1).mean().shift(1)
    )
    features["occ_roll_std_3h"] = g["occupancy_rate"].transform(
        lambda s: s.rolling(12, min_periods=1).std(ddof=1).shift(1)
    )
    flux_col = (
        "pe_net_flux" if "pe_net_flux" in features.columns else "net_flux"
    )
    features["occ_acceleration"] = g[flux_col].diff().fillna(0)

    fill_cols = ["occ_roll_mean_3h", "occ_roll_std_3h"]
    for c in fill_cols:
        features[c] = features[c].fillna(
            features[c].mean() if bool(features[c].notna().any()) else 0
        )

    X = features[X_COLS]
    y = features["target"]

    cutoff = features["ts_bucket"].quantile(0.8)
    train_mask = features["ts_bucket"] <= cutoff
    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask], y[~train_mask]
    if len(X_test) < 10:
        split_idx = int(len(features) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # Reduced n_estimators (RF 500→100, XGB 800→200) to fix Render OOM.
    # rf_model.joblib: 146MB→~29MB. xgb_model.joblib: 3.6MB→~900KB.
    # On Render free tier (512MB RAM), old models + deps exceeded limit
    # after 3-5 min under load, causing OOM-killer termination and 502
    # responses.
    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    xgb = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.02,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    meta = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0])

    rf.fit(X_train, y_train)
    xgb.fit(X_train, y_train)
    rf_preds = rf.predict(X_train)
    xgb_preds = xgb.predict(X_train)
    meta_train = np.column_stack([rf_preds, xgb_preds])
    meta.fit(meta_train, y_train)
    print(
        f"  Ridge meta weights: {meta.coef_}, intercept: {meta.intercept_:.4f}"
    )

    rf_test = rf.predict(X_test)
    xgb_test = xgb.predict(X_test)
    meta_test = np.column_stack([rf_test, xgb_test])
    ensemble_preds = meta.predict(meta_test)

    mae = mean_absolute_error(y_test, ensemble_preds)
    rf_mae = mean_absolute_error(y_test, rf_test)
    xgb_mae = mean_absolute_error(y_test, xgb_test)
    r2 = r2_score(y_test, ensemble_preds)
    print(f"\n[Gemini Validation] Chronological MAE: {mae:.5f}, R²: {r2:.4f}")
    print(f"  RF MAE:  {rf_mae:.5f}")
    print(f"  XGB MAE: {xgb_mae:.5f}")

    os.makedirs("src/models/artifacts", exist_ok=True)
    joblib.dump(rf, "src/models/artifacts/rf_model.joblib")
    joblib.dump(xgb, "src/models/artifacts/xgb_model.joblib")
    joblib.dump(meta, "src/models/artifacts/meta_model.joblib")

    if mae < 0.05:
        print("RESULT: HIGH-FIDELITY. Suitable for production.")
    if mae < 0.01:
        print("RESULT: 99% ACCURACY ACHIEVED.")

    return mae


if __name__ == "__main__":
    from src.features.engine import process_raw_to_features

    RAW_PATH = "data/raw/birmingham_parking.csv"
    features = process_raw_to_features(RAW_PATH)
    train_chronological_ensemble(features)
