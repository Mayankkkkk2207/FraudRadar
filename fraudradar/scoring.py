from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np

from fraudradar.features import FEATURE_COLUMNS, amount_from_payload, feature_vector
from fraudradar.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreResult:
    risk_score: float
    risk_level: str
    is_fraud: bool
    isolation_forest_score: float
    isolation_forest_anomaly: float
    autoencoder_mse: float
    autoencoder_anomaly: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FraudScorer:
    def __init__(self, model_dir: Path | str | None = None) -> None:
        self.model_dir = Path(model_dir or settings.model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._isolation_forest = None
        self._autoencoder = None
        self._scaler = None
        self._thresholds: dict[str, float] = {}

    def load(self) -> None:
        ensure_model_artifacts(self.model_dir)
        import tensorflow as tf

        self._isolation_forest = joblib.load(self.model_dir / "isolation_forest.joblib")
        self._scaler = joblib.load(self.model_dir / "scaler.joblib")
        self._autoencoder = tf.keras.models.load_model(self.model_dir / "autoencoder.keras")
        with (self.model_dir / "thresholds.json").open("r", encoding="utf-8") as f:
            self._thresholds = json.load(f)
        logger.info("Loaded FraudRadar model artifacts from %s", self.model_dir)

    def score(self, payload: Mapping[str, Any]) -> ScoreResult:
        if self._isolation_forest is None or self._autoencoder is None or self._scaler is None:
            self.load()

        vector = feature_vector(payload)
        scaled = self._scaler.transform(vector)

        if_score = float(self._isolation_forest.decision_function(scaled)[0])
        if_threshold = float(self._thresholds.get("isolation_forest_decision_threshold", -0.02))
        if_anomaly = _bounded((if_threshold - if_score) / max(abs(if_threshold), 0.05))

        reconstructed = self._autoencoder.predict(scaled, verbose=0)
        mse = float(np.mean(np.square(scaled - reconstructed)))
        ae_threshold = float(self._thresholds.get("autoencoder_mse_threshold", 1.0))
        ae_anomaly = _bounded(mse / max(ae_threshold, 1e-9) - 0.65)

        heuristic = heuristic_anomaly(payload)
        risk_score = float(np.clip((if_anomaly * 42.0) + (ae_anomaly * 42.0) + (heuristic * 16.0), 0.0, 100.0))
        risk_level = risk_level_for_score(risk_score)
        reasons = reasons_for(payload, if_anomaly, ae_anomaly, heuristic)
        return ScoreResult(
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            is_fraud=risk_level == "high",
            isolation_forest_score=round(if_score, 6),
            isolation_forest_anomaly=round(float(if_anomaly), 6),
            autoencoder_mse=round(mse, 6),
            autoencoder_anomaly=round(float(ae_anomaly), 6),
            reasons=reasons,
        )


def risk_level_for_score(score: float) -> str:
    if score >= settings.high_risk_threshold:
        return "high"
    if score >= settings.medium_risk_threshold:
        return "medium"
    return "low"


def heuristic_anomaly(payload: Mapping[str, Any]) -> float:
    amount = amount_from_payload(payload)
    country = str(payload.get("country") or "").upper()
    category = str(payload.get("category") or "").lower()
    score = 0.0
    if amount >= 1500:
        score += 0.35
    elif amount >= 600:
        score += 0.2
    if country in {"NG", "RU", "KP", "IR"}:
        score += 0.25
    if category in {"crypto", "gift_card", "gambling", "wire_transfer"}:
        score += 0.25
    if not payload.get("device_id"):
        score += 0.1
    return _bounded(score)


def reasons_for(payload: Mapping[str, Any], if_anomaly: float, ae_anomaly: float, heuristic: float) -> list[str]:
    reasons: list[str] = []
    if if_anomaly >= 0.65:
        reasons.append("Isolation Forest marked the feature vector as unusual")
    if ae_anomaly >= 0.65:
        reasons.append("Autoencoder reconstruction error exceeded the learned baseline")
    amount = amount_from_payload(payload)
    if amount >= 1500:
        reasons.append("Transaction amount is unusually high")
    category = str(payload.get("category") or "").lower()
    if category in {"crypto", "gift_card", "gambling", "wire_transfer"}:
        reasons.append(f"Merchant category '{category}' carries elevated fraud risk")
    if heuristic >= 0.55:
        reasons.append("Rules-based risk signals compounded the model score")
    if not reasons:
        reasons.append("No strong fraud indicators detected")
    return reasons


def ensure_model_artifacts(model_dir: Path) -> None:
    required = [
        model_dir / "isolation_forest.joblib",
        model_dir / "scaler.joblib",
        model_dir / "autoencoder.keras",
        model_dir / "thresholds.json",
    ]
    if all(path.exists() for path in required):
        return
    logger.warning("Model artifacts missing in %s; training compact bootstrap models", model_dir)
    train_bootstrap_models(model_dir)


def train_bootstrap_models(model_dir: Path) -> None:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import tensorflow as tf

    rng = np.random.default_rng(settings.random_seed)
    n_normal = 8000
    n_anomaly = 400

    normal = rng.normal(loc=0.0, scale=1.0, size=(n_normal, len(FEATURE_COLUMNS))).astype(np.float32)
    normal[:, 0] = rng.uniform(0, 172800, size=n_normal)
    normal[:, -1] = rng.lognormal(mean=3.35, sigma=0.85, size=n_normal)

    anomaly = rng.normal(loc=0.0, scale=2.5, size=(n_anomaly, len(FEATURE_COLUMNS))).astype(np.float32)
    anomaly[:, 0] = rng.uniform(0, 172800, size=n_anomaly)
    anomaly[:, -1] = rng.lognormal(mean=6.2, sigma=1.0, size=n_anomaly)

    scaler = StandardScaler()
    scaled_normal = scaler.fit_transform(normal)
    scaled_all = scaler.transform(np.vstack([normal, anomaly]))

    isolation_forest = IsolationForest(
        n_estimators=180,
        contamination=0.04,
        random_state=settings.random_seed,
        n_jobs=-1,
    )
    isolation_forest.fit(scaled_normal)

    inputs = tf.keras.Input(shape=(len(FEATURE_COLUMNS),))
    x = tf.keras.layers.Dense(20, activation="relu")(inputs)
    x = tf.keras.layers.Dense(10, activation="relu")(x)
    x = tf.keras.layers.Dense(20, activation="relu")(x)
    outputs = tf.keras.layers.Dense(len(FEATURE_COLUMNS), activation="linear")(x)
    autoencoder = tf.keras.Model(inputs, outputs)
    autoencoder.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001), loss="mse")
    autoencoder.fit(scaled_normal, scaled_normal, epochs=8, batch_size=128, validation_split=0.1, verbose=0)

    recon = autoencoder.predict(scaled_normal, verbose=0)
    mse = np.mean(np.square(scaled_normal - recon), axis=1)
    if_scores = isolation_forest.decision_function(scaled_all)
    thresholds = {
        "feature_columns": FEATURE_COLUMNS,
        "autoencoder_mse_threshold": float(np.quantile(mse, 0.985)),
        "isolation_forest_decision_threshold": float(np.quantile(if_scores, 0.04)),
        "source": "bootstrap_synthetic",
    }

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(isolation_forest, model_dir / "isolation_forest.joblib")
    joblib.dump(scaler, model_dir / "scaler.joblib")
    autoencoder.save(model_dir / "autoencoder.keras")
    with (model_dir / "thresholds.json").open("w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)


def _bounded(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))
