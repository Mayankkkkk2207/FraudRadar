from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.compose import ColumnTransformer
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


RANDOM_STATE = 42
DATA_PATH = Path("data") / "creditcard.csv"
MODEL_DIR = Path("models")
AUTOENCODER_PATH = MODEL_DIR / "autoencoder.h5"
SCALER_PATH = MODEL_DIR / "scaler.joblib"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"
LOSS_PLOT_PATH = MODEL_DIR / "training_loss.png"
FEATURE_COLUMNS = [f"V{i}" for i in range(1, 29)] + ["Amount"]


def load_dataset(csv_path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.Series]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    data = pd.read_csv(csv_path)
    required_columns = {"Time", "Class", *FEATURE_COLUMNS}
    missing_columns = sorted(required_columns.difference(data.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    data = data.drop(columns=["Time"])
    labels = data["Class"].astype(int)
    features = data.drop(columns=["Class"])
    return features, labels


def build_scaler() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[("amount", StandardScaler(), ["Amount"])],
        remainder="passthrough",
        verbose_feature_names_out=False,
    )


def load_or_fit_scaler(normal_training_features: pd.DataFrame) -> ColumnTransformer:
    if SCALER_PATH.exists():
        scaler = joblib.load(SCALER_PATH)
        try:
            scaler.transform(normal_training_features[FEATURE_COLUMNS].head(1))
            return scaler
        except Exception:
            pass

    scaler = build_scaler()
    scaler.fit(normal_training_features[FEATURE_COLUMNS])
    joblib.dump(scaler, SCALER_PATH)
    return scaler


def build_autoencoder(input_dim: int = 29) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=(input_dim,))
    encoded = tf.keras.layers.Dense(16, activation="relu")(inputs)
    encoded = tf.keras.layers.Dense(8, activation="relu")(encoded)
    encoded = tf.keras.layers.Dense(4, activation="relu")(encoded)
    decoded = tf.keras.layers.Dense(8, activation="relu")(encoded)
    decoded = tf.keras.layers.Dense(16, activation="relu")(decoded)
    outputs = tf.keras.layers.Dense(input_dim, activation="sigmoid")(decoded)

    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer="adam", loss="mse")
    return model


def reconstruction_errors(model: tf.keras.Model, values: np.ndarray) -> np.ndarray:
    reconstructed = model.predict(values, verbose=0)
    return np.mean(np.square(values - reconstructed), axis=1)


def save_training_loss_plot(history: tf.keras.callbacks.History) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(history.history["loss"], label="Training loss")
    if "val_loss" in history.history:
        plt.plot(history.history["val_loss"], label="Validation loss")
    plt.title("Autoencoder Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(LOSS_PLOT_PATH, dpi=150)
    plt.close()


def train() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tf.keras.utils.set_random_seed(RANDOM_STATE)

    x, y = load_dataset()
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    normal_train = x_train[y_train == 0]
    scaler = load_or_fit_scaler(normal_train)

    x_train_normal_scaled = scaler.transform(normal_train[FEATURE_COLUMNS]).astype(np.float32)
    x_test_scaled = scaler.transform(x_test[FEATURE_COLUMNS]).astype(np.float32)

    model = build_autoencoder(input_dim=x_train_normal_scaled.shape[1])
    history = model.fit(
        x_train_normal_scaled,
        x_train_normal_scaled,
        epochs=50,
        batch_size=256,
        validation_split=0.1,
        verbose=1,
    )

    train_errors = reconstruction_errors(model, x_train_normal_scaled)
    threshold = float(np.percentile(train_errors, 95))

    test_errors = reconstruction_errors(model, x_test_scaled)
    predictions = (test_errors > threshold).astype(int)

    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)

    print("Autoencoder evaluation")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1: {f1:.4f}")
    print(f"Reconstruction error threshold: {threshold:.8f}")

    model.save(AUTOENCODER_PATH)
    THRESHOLD_PATH.write_text(
        json.dumps(
            {
                "threshold": threshold,
                "autoencoder_threshold": threshold,
                "percentile": 95,
                "feature_columns": FEATURE_COLUMNS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    save_training_loss_plot(history)

    print(f"Autoencoder saved to {AUTOENCODER_PATH}")
    print(f"Threshold saved to {THRESHOLD_PATH}")
    print(f"Training loss curve saved to {LOSS_PLOT_PATH}")


if __name__ == "__main__":
    train()
