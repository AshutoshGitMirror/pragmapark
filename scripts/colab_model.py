# -*- coding: utf-8 -*-
"""colab_model.py

Standalone training script (shell-agnostic, no !-operators).
Original Colab source: https://colab.research.google.com/drive/1TljK1poENURu7N8lWGDeqDfUudcYNsZu
"""

import subprocess
import sys
import os
import zipfile
import io
import requests

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

import warnings
warnings.filterwarnings("ignore")


def _run(cmd: str) -> None:
    subprocess.check_call(cmd, shell=True)


def _pip_install(packages: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages.split())


def _download_data(data_dir: str = "./data") -> str:
    os.makedirs(data_dir, exist_ok=True)
    zip_path = os.path.join(data_dir, "dataset.zip")
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00482/dataset.zip"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        csv_files = [f for f in z.namelist() if f.endswith(".csv")]
        if not csv_files:
            raise RuntimeError("No CSV found in dataset archive")
        target = os.path.join(data_dir, csv_files[0])
        z.extract(csv_files[0], data_dir)
    return target


def main():
    csv_path = _download_data()
    print(f"Extracted: {csv_path}")
    df = pd.read_csv(csv_path)

    datetime_col = "LastUpdated"
    print(f"Using column '{datetime_col}' for datetime features.")
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors="coerce")
    df = df.dropna(subset=[datetime_col])
    df = df.sort_values(by=datetime_col).reset_index(drop=True)

    df["Hour"] = df[datetime_col].dt.hour
    df["DayOfWeek"] = df[datetime_col].dt.dayofweek
    df["Month"] = df[datetime_col].dt.month

    print(f"Rows remaining: {len(df)}")
    print(df.head().to_string())

    periods = {"Hour": 24, "DayOfWeek": 7, "Month": 12}
    for col, max_val in periods.items():
        df[f"{col}_sin"] = np.sin(2 * np.pi * df[col] / max_val)
        df[f"{col}_cos"] = np.cos(2 * np.pi * df[col] / max_val)

    cols_to_drop = ["Hour", "DayOfWeek", "Month", "LastUpdated"]
    df = df.drop(columns=cols_to_drop)
    print(f"Columns after cyclical encoding: {df.columns.tolist()}")
    print(df.head().to_string())

    df_encoded = pd.get_dummies(df, columns=["SystemCodeNumber"], prefix="ID")
    y = df_encoded["Occupancy"]
    X = df_encoded.drop(columns=["Occupancy", "Capacity"])
    print(f"Feature matrix X: {X.shape}, target y: {y.shape}")
    print(X.head().to_string())

    tscv = TimeSeriesSplit(n_splits=5)
    rf_model = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)

    mse_scores, mae_scores, r2_scores = [], [], []
    print(f"Starting TimeSeriesSplit training on {len(X)} samples...\n")

    for fold, (train_index, test_index) in enumerate(tscv.split(X), 1):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        rf_model.fit(X_train, y_train)
        y_pred = rf_model.predict(X_test)
        mse_scores.append(mean_squared_error(y_test, y_pred))
        mae_scores.append(mean_absolute_error(y_test, y_pred))
        r2_scores.append(r2_score(y_test, y_pred))
        print(f"Fold {fold}: MSE={mse_scores[-1]:.4f} MAE={mae_scores[-1]:.4f} R2={r2_scores[-1]:.4f}")
        print("-" * 20)

    avg_mse = np.mean(mse_scores)
    avg_mae = np.mean(mae_scores)
    avg_r2 = np.mean(r2_scores)
    print("--- Final Model Performance Summary ---")
    print(f"Average MSE: {avg_mse:.4f}")
    print(f"Average MAE: {avg_mae:.4f}")
    print(f"Average R2:  {avg_r2:.4f}")
    print("-" * 39)
    interpretation = (
        "The model shows high predictive power with an R2 above 0.8."
        if avg_r2 > 0.8
        else "Model performance is moderate; further feature engineering may help."
    )
    print(f"Interpretation: {interpretation}")


if __name__ == "__main__":
    main()
