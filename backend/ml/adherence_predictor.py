"""
Discharge+ — Medication Adherence Predictor
Logistic regression model predicting the likelihood of missing scheduled doses
within the next 48 hours based on 14-day history, prescription burden, and diagnosis.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from config import get_settings

settings = get_settings()

MODEL_PATH = Path(__file__).resolve().parent / "models" / "adherence_model.joblib"
_cached_model = None


def load_adherence_model():
    """Load adherence predictor artifact."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            return _cached_model
        except Exception as e:
            print(f"⚠️ Failed to load adherence artifact: {e}")
            return None
    return None


def predict_adherence_risk(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict likelihood of missing a medication dose in the next 48 hours.
    """
    if not settings.ml_adherence:
        return {
            "status": "disabled",
            "miss_probability": None,
            "adherence_risk": "low",
            "streak_days": 0,
            "nudge": None,
        }

    meds = snapshot.get("medications", {})
    demo = snapshot.get("demographics", {})
    hist_adherence = float(meds.get("adherence_rate", 1.0))
    recent_missed = int(meds.get("recent_missed", 0))
    active_meds = int(meds.get("active_med_count", 0))
    taken_count = int(meds.get("taken_count", 0))

    # Compute streak (simple estimate based on consecutive taken count)
    streak_days = max(1, min(30, taken_count // max(1, active_meds)))

    bundle = load_adherence_model()
    prob = 0.15

    if bundle is not None:
        try:
            from ml.feature_engineering import vectorize_adherence_features
            df = vectorize_adherence_features(snapshot)
            model = bundle["model"]
            cols = bundle.get("features", list(df.columns))

            for c in cols:
                if c not in df.columns:
                    df[c] = 0.0

            prob_arr = model.predict_proba(df[cols])
            prob = float(prob_arr[0][1])
        except Exception as e:
            print(f"⚠️ Adherence model evaluation failed, using baseline: {e}")
            # Baseline calculation
            prob = (1.0 - hist_adherence) * 0.7 + (0.2 if recent_missed > 0 else 0.05) + (0.1 if active_meds > 3 else 0.0)
    else:
        # Baseline calculation
        prob = (1.0 - hist_adherence) * 0.7 + (0.2 if recent_missed > 0 else 0.05) + (0.1 if active_meds > 3 else 0.0)

    prob = min(0.95, max(0.05, prob))

    if prob >= 0.50:
        risk_tier = "high"
        nudge = "⚠️ You're at risk of missing your upcoming scheduled dose. Staying consistent keeps your recovery on track!"
    elif prob >= 0.25:
        risk_tier = "medium"
        nudge = "💊 Friendly reminder: remember to take your evening medications as prescribed."
    else:
        risk_tier = "low"
        nudge = f"🔥 Great job! You have a {streak_days}-day medication adherence streak."

    return {
        "status": "ready",
        "miss_probability": round(prob, 3),
        "adherence_risk": risk_tier,
        "streak_days": streak_days,
        "nudge": nudge,
        "active_medications": active_meds,
        "historical_adherence_rate": round(hist_adherence * 100, 1),
    }
