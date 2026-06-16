from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


RANDOM_STATE = 42
DATA_PATH = Path("data") / "creditcard.csv"
MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "isolation_forest.joblib"
SCALER_PATH = MODEL_DIR / "scaler.joblib"
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


def file_size(path: Path) -> str:
    size_bytes = path.stat().st_size
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def train() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    x, y = load_dataset()
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    scaler = build_scaler()
    x_train_scaled = scaler.fit_transform(x_train[FEATURE_COLUMNS])
    x_test_scaled = scaler.transform(x_test[FEATURE_COLUMNS])

    model = IsolationForest(
        n_estimators=100,
        contamination=0.001,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(x_train_scaled)

    predictions = (model.predict(x_test_scaled) == -1).astype(int)

    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)
    matrix = confusion_matrix(y_test, predictions)

    print("Isolation Forest evaluation")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1: {f1:.4f}")
    print("Confusion matrix:")
    print(matrix)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    print("Model saved successfully")
    print(f"{MODEL_PATH}: {file_size(MODEL_PATH)}")
    print(f"{SCALER_PATH}: {file_size(SCALER_PATH)}")


if __name__ == "__main__":
    train()
