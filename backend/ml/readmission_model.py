"""
Discharge+ — Readmission Risk Predictor & SHAP Explainability
Predicts 30-day readmission probability using vital trajectory, demographics,
and medication adherence, returning top 3 SHAP feature contributors.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
import pandas as pd
import shap
from config import get_settings

settings = get_settings()

MODEL_PATH = Path(__file__).resolve().parent / "models" / "readmission_model.joblib"
_cached_bundle = None
_cached_explainer = None

# Human readable names for features in SHAP output
FEATURE_DISPLAY_NAMES = {
    "age": "Patient Age",
    "days_since_discharge": "Days Since Discharge",
    "expected_recovery_days": "Expected Recovery Period",
    "fever_latest": "Latest Body Temperature",
    "fever_mean": "Average Temperature Trend",
    "fever_slope": "Rising Temperature Slope",
    "spo2_latest": "Latest SpO2 Reading",
    "spo2_mean": "Mean Oxygen Saturation",
    "spo2_declining_consecutive": "Declining Oxygen Saturation Trend",
    "systolic_bp_latest": "Systolic Blood Pressure",
    "diastolic_bp_latest": "Diastolic Blood Pressure",
    "sugar_latest": "Latest Blood Sugar",
    "sugar_mean": "Average Blood Sugar",
    "pain_latest": "Reported Pain Level",
    "pain_spike": "Recent Spike in Pain",
    "high_risk_count": "Past High-Risk Survey Count",
    "last_risk_score": "Most Recent Survey Risk Score",
    "mean_risk_score": "Average Historical Risk Score",
    "surveys_completed": "Survey Adherence / Engagement",
    "adherence_rate": "Medication Adherence Rate",
    "recent_missed": "Recent Missed Medication Doses",
    "active_med_count": "Active Prescription Burden",
    "comorb_hypertension": "Hypertension Comorbidity",
    "comorb_diabetes": "Diabetes Comorbidity",
    "comorb_copd": "COPD / Chronic Respiratory Disease",
    "comorb_coronary_artery_disease": "Coronary Artery Disease",
    "comorb_chronic_kidney_disease": "Kidney Disease History",
}


def load_readmission_bundle():
    """Load model artifact and explainer."""
    global _cached_bundle, _cached_explainer
    if _cached_bundle is not None:
        return _cached_bundle, _cached_explainer

    if MODEL_PATH.exists():
        try:
            bundle = joblib.load(MODEL_PATH)
            _cached_bundle = bundle
            model = bundle.get("model")
            try:
                _cached_explainer = shap.TreeExplainer(model)
            except Exception as se:
                print(f"⚠️ SHAP TreeExplainer initialization warning: {se}")
                _cached_explainer = None
            return _cached_bundle, _cached_explainer
        except Exception as e:
            print(f"⚠️ Failed to load readmission artifact: {e}")
            return None, None
    return None, None


def predict_readmission_risk(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict 30-day readmission probability and extract top 3 SHAP contributors.
    """
    if not settings.ml_readmission:
        return {
            "status": "disabled",
            "probability": None,
            "risk_tier": "unknown",
            "top_contributors": [],
            "as_of": snapshot.get("as_of"),
            "version": "none",
        }

    bundle, explainer = load_readmission_bundle()
    if bundle is None:
        # Graceful baseline estimation if model not yet trained
        from ml.feature_engineering import vectorize_readmission_features
        df = vectorize_readmission_features(snapshot)
        mean_risk = float(df["mean_risk_score"].iloc[0]) if "mean_risk_score" in df else 25.0
        pain_spike = float(df["pain_spike"].iloc[0]) if "pain_spike" in df else 0.0
        spo2_dec = float(df["spo2_declining_consecutive"].iloc[0]) if "spo2_declining_consecutive" in df else 0.0

        # Baseline heuristic
        base_p = 0.10 + (mean_risk / 200.0) + (0.15 * pain_spike) + (0.20 * (1.0 if spo2_dec >= 3 else 0.0))
        base_p = min(0.95, max(0.05, base_p))

        contributors = []
        if spo2_dec >= 3:
            contributors.append({"feature": "Declining Oxygen Saturation", "impact": "+18%", "direction": "increasing_risk"})
        if pain_spike > 0:
            contributors.append({"feature": "Recent Pain Spike", "impact": "+12%", "direction": "increasing_risk"})
        if mean_risk > 50:
            contributors.append({"feature": "Elevated Survey Risk History", "impact": "+15%", "direction": "increasing_risk"})
        if not contributors:
            contributors.append({"feature": "Stable Vital Trajectory", "impact": "-10%", "direction": "reducing_risk"})

        return {
            "status": "baseline_rules",
            "probability": round(base_p, 3),
            "percentage": int(round(base_p * 100)),
            "risk_tier": "high" if base_p >= 0.50 else ("medium" if base_p >= 0.25 else "low"),
            "top_contributors": contributors[:3],
            "as_of": snapshot.get("as_of"),
            "version": "baseline-heuristic-1.0",
        }

    try:
        from ml.feature_engineering import vectorize_readmission_features
        df = vectorize_readmission_features(snapshot)
        model = bundle["model"]
        feature_cols = bundle.get("features", list(df.columns))

        # Align features
        for c in feature_cols:
            if c not in df.columns:
                df[c] = 0.0
        X = df[feature_cols]

        prob_arr = model.predict_proba(X)
        prob = float(prob_arr[0][1])

        # SHAP explanation
        contributors = []
        if explainer is not None:
            try:
                shap_values = explainer.shap_values(X)
                # TreeExplainer for binary classifier may return list of 2 arrays or 1 array
                if isinstance(shap_values, list):
                    vals = shap_values[1][0]
                elif len(shap_values.shape) == 2:
                    vals = shap_values[0]
                else:
                    vals = shap_values[0, :, 1]

                # Pair with feature names and sort by absolute impact
                indexed_shaps = []
                for idx, col in enumerate(feature_cols):
                    sv = float(vals[idx])
                    indexed_shaps.append((col, sv, abs(sv), X[col].iloc[0]))

                indexed_shaps.sort(key=lambda x: x[2], reverse=True)

                for col, sv, abs_sv, raw_val in indexed_shaps[:3]:
                    display_name = FEATURE_DISPLAY_NAMES.get(col, col.replace("_", " ").title())
                    direction = "increasing_risk" if sv > 0 else "reducing_risk"
                    pct = round(abs_sv * 100, 1)
                    contributors.append({
                        "feature": display_name,
                        "raw_column": col,
                        "value": float(raw_val),
                        "impact": f"{'+' if sv > 0 else '-'}{pct}%",
                        "direction": direction,
                    })
            except Exception as se:
                print(f"⚠️ SHAP calculation error: {se}")

        return {
            "status": "ready",
            "probability": round(prob, 3),
            "percentage": int(round(prob * 100)),
            "risk_tier": "high" if prob >= 0.50 else ("medium" if prob >= 0.25 else "low"),
            "top_contributors": contributors,
            "as_of": snapshot.get("as_of"),
            "version": bundle.get("version", "xgb-readmit-1.0"),
        }

    except Exception as e:
        print(f"❌ Readmission prediction error: {e}")
        return {
            "status": "error",
            "probability": None,
            "risk_tier": "unknown",
            "top_contributors": [],
            "as_of": snapshot.get("as_of"),
            "version": bundle.get("version", "unknown"),
        }
