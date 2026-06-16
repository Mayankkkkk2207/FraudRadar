from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np


PCA_COLUMNS = [f"V{i}" for i in range(1, 29)]
FEATURE_COLUMNS = ["Time", *PCA_COLUMNS, "Amount"]


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def normalize_feature_payload(payload: Mapping[str, Any]) -> dict[str, float]:
    features = payload.get("features", {})
    merged: dict[str, Any] = {}
    if isinstance(features, Mapping):
        merged.update(features)
    merged.update({k: v for k, v in payload.items() if k in FEATURE_COLUMNS})

    normalized: dict[str, float] = {}
    for column in FEATURE_COLUMNS:
        value = merged.get(column, 0.0)
        try:
            normalized[column] = float(value)
        except (TypeError, ValueError):
            normalized[column] = 0.0
    return normalized


def feature_vector(payload: Mapping[str, Any]) -> np.ndarray:
    normalized = normalize_feature_payload(payload)
    return np.asarray([[normalized[column] for column in FEATURE_COLUMNS]], dtype=np.float32)


def amount_from_payload(payload: Mapping[str, Any]) -> float:
    amount = payload.get("amount")
    if amount is None and isinstance(payload.get("features"), Mapping):
        amount = payload["features"].get("Amount")
    try:
        return float(amount)
    except (TypeError, ValueError):
        return 0.0


def model_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_feature_payload(payload)
    return {
        "transaction_id": str(payload.get("transaction_id") or payload.get("id") or ""),
        "timestamp": str(payload.get("timestamp") or utc_now_iso()),
        "amount": amount_from_payload(payload),
        "currency": str(payload.get("currency") or "USD"),
        "merchant": str(payload.get("merchant") or "unknown"),
        "category": str(payload.get("category") or "unknown"),
        "card_id": str(payload.get("card_id") or "unknown"),
        "customer_id": str(payload.get("customer_id") or "unknown"),
        "country": str(payload.get("country") or "unknown"),
        "ip_address": str(payload.get("ip_address") or ""),
        "device_id": str(payload.get("device_id") or ""),
        "features": normalized,
    }
