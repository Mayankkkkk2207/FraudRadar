from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


MODEL_DIR = Path("models")
ISOLATION_FOREST_PATH = MODEL_DIR / "isolation_forest.joblib"
AUTOENCODER_PATH = MODEL_DIR / "autoencoder.h5"
SCALER_PATH = MODEL_DIR / "scaler.joblib"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"
FEATURE_COLUMNS = [f"V{i}" for i in range(1, 29)] + ["Amount"]

_MODEL_CACHE: dict[str, Any] | None = None


def load_models() -> dict[str, Any]:
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    missing_paths = [
        path
        for path in [ISOLATION_FOREST_PATH, AUTOENCODER_PATH, SCALER_PATH, THRESHOLD_PATH]
        if not path.exists()
    ]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Missing model artifact(s): {missing}")

    import tensorflow as tf

    isolation_forest = joblib.load(ISOLATION_FOREST_PATH)
    autoencoder = tf.keras.models.load_model(AUTOENCODER_PATH, compile=False)
    scaler = joblib.load(SCALER_PATH)
    threshold_data = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    threshold = float(threshold_data.get("threshold", threshold_data.get("autoencoder_threshold")))

    _MODEL_CACHE = {
        "isolation_forest": isolation_forest,
        "autoencoder": autoencoder,
        "scaler": scaler,
        "threshold": threshold,
    }
    return _MODEL_CACHE


def score_transaction(transaction_dict: dict[str, Any]) -> dict[str, float | bool | str]:
    models = load_models()
    features = transaction_to_frame(transaction_dict)
    scaled_features = models["scaler"].transform(features).astype(np.float32)

    raw_isolation_score = float(-models["isolation_forest"].decision_function(scaled_features)[0])
    reconstructed = models["autoencoder"].predict(scaled_features, verbose=0)
    autoencoder_score = float(np.mean(np.square(scaled_features - reconstructed), axis=1)[0])

    isolation_probability = sigmoid(raw_isolation_score * 12.0)
    autoencoder_probability = np.clip(autoencoder_score / (models["threshold"] * 2.0), 0.0, 1.0)
    combined_probability = float(np.clip((0.55 * isolation_probability) + (0.45 * autoencoder_probability), 0.0, 1.0))
    risk_level = get_risk_level(combined_probability)

    return {
        "isolation_forest_score": raw_isolation_score,
        "autoencoder_score": autoencoder_score,
        "combined_fraud_probability": combined_probability,
        "is_fraud": combined_probability >= 0.6,
        "risk_level": risk_level,
    }


def transaction_to_frame(transaction_dict: dict[str, Any]) -> pd.DataFrame:
    nested_features = transaction_dict.get("features", {})
    if not isinstance(nested_features, dict):
        nested_features = {}

    values: dict[str, float] = {}
    for column in FEATURE_COLUMNS:
        if column in transaction_dict:
            raw_value = transaction_dict[column]
        elif column in nested_features:
            raw_value = nested_features[column]
        elif column == "Amount" and "amount" in transaction_dict:
            raw_value = transaction_dict["amount"]
        else:
            raw_value = 0.0

        try:
            values[column] = float(raw_value)
        except (TypeError, ValueError):
            values[column] = 0.0

    return pd.DataFrame([values], columns=FEATURE_COLUMNS)


def get_risk_level(probability: float) -> str:
    if probability < 0.3:
        return "LOW"
    if probability < 0.6:
        return "MEDIUM"
    if probability < 0.85:
        return "HIGH"
    return "CRITICAL"


def sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value)))
