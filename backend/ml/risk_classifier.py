"""
Discharge+ — Hybrid Survey Risk Classifier
Combines XGBoost 3-class classification with a deterministic clinical safety floor.
"""

from pathlib import Path
from typing import Dict, Any, List, Tuple
import joblib
import numpy as np
import pandas as pd
from config import get_settings
from ml.feature_engineering import extract_survey_answer_features

settings = get_settings()

MODEL_PATH = Path(__file__).resolve().parent / "models" / "risk_classifier.joblib"
_cached_model = None


def load_risk_model():
    """Load trained 3-class XGBoost risk classifier."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            return _cached_model
        except Exception as e:
            print(f"⚠️ Failed to load risk classifier artifact: {e}")
            return None
    return None


def evaluate_clinical_rules(feats: Dict[str, float]) -> Tuple[str, int, Dict[str, str], List[str]]:
    """
    Deterministic clinical safety floor based on standard emergency and post-discharge criteria:
    Fever: > 100.4 concerning, >= 103 or <= 95 critical
    SpO2: < 94 concerning, <= 90 critical
    Systolic BP: > 140 or < 90 concerning, >= 180 or <= 80 critical
    Diastolic BP: > 90 or < 60 concerning, >= 120 or <= 50 critical
    Blood sugar: > 200 or < 70 concerning, >= 300 or <= 50 critical
    Pain level: 4-7 concerning, 8-10 critical
    """
    factors = {
        "fever": "normal",
        "spo2": "normal",
        "bp": "normal",
        "sugar": "normal",
        "pain": "normal",
        "overall": "stable",
    }
    reasons = []
    concerning_count = 0
    critical_count = 0

    # Fever
    if feats.get("fever_present"):
        f = feats["fever"]
        if f >= 103.0 or f <= 95.0:
            factors["fever"] = "critical"
            critical_count += 1
            reasons.append(f"Critical temperature: {f}°F.")
        elif f > 100.4:
            factors["fever"] = "concerning"
            concerning_count += 1
            reasons.append(f"Elevated fever: {f}°F.")

    # SpO2
    if feats.get("spo2_present"):
        s = feats["spo2"]
        if s <= 90.0:
            factors["spo2"] = "critical"
            critical_count += 1
            reasons.append(f"Critical SpO₂ desaturation: {s}%.")
        elif s < 94.0:
            factors["spo2"] = "concerning"
            concerning_count += 1
            reasons.append(f"Low SpO₂: {s}%.")

    # BP
    if feats.get("bp_present"):
        sys_bp = feats["systolic_bp"]
        dia_bp = feats["diastolic_bp"]
        if sys_bp >= 180.0 or sys_bp <= 80.0 or dia_bp >= 120.0 or dia_bp <= 50.0:
            factors["bp"] = "critical"
            critical_count += 1
            reasons.append(f"Critical blood pressure: {int(sys_bp)}/{int(dia_bp)} mmHg.")
        elif sys_bp > 140.0 or sys_bp < 90.0 or dia_bp > 90.0 or dia_bp < 60.0:
            factors["bp"] = "concerning"
            concerning_count += 1
            reasons.append(f"Abnormal blood pressure: {int(sys_bp)}/{int(dia_bp)} mmHg.")

    # Blood sugar
    if feats.get("sugar_present"):
        glu = feats["sugar"]
        if glu >= 300.0 or glu <= 50.0:
            factors["sugar"] = "critical"
            critical_count += 1
            reasons.append(f"Critical blood sugar level: {int(glu)} mg/dL.")
        elif glu > 200.0 or glu < 70.0:
            factors["sugar"] = "concerning"
            concerning_count += 1
            reasons.append(f"Elevated blood sugar: {int(glu)} mg/dL.")

    # Pain
    if feats.get("pain_present"):
        p = feats["pain"]
        if p >= 8.0:
            factors["pain"] = "critical"
            critical_count += 1
            reasons.append(f"Severe pain score: {int(p)}/10.")
        elif p >= 4.0:
            factors["pain"] = "concerning"
            concerning_count += 1
            reasons.append(f"Moderate pain: {int(p)}/10.")

    # Scoring decision
    if critical_count > 0 or concerning_count >= 2:
        risk_level = "high"
        factors["overall"] = "urgent"
        base_score = 75 + min(24, critical_count * 10 + concerning_count * 4)
    elif concerning_count == 1:
        risk_level = "medium"
        factors["overall"] = "needs_attention"
        base_score = 45 + min(20, concerning_count * 8)
    else:
        risk_level = "low"
        factors["overall"] = "stable"
        base_score = 15

    return risk_level, base_score, factors, reasons


def classify_survey_risk(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Score a survey response using XGBoost + deterministic safety floor.
    """
    feats = extract_survey_answer_features(answers)
    rule_level, rule_score, factors, reasons = evaluate_clinical_rules(feats)

    level_rank = {"low": 0, "medium": 1, "high": 2}
    rank_level = {0: "low", 1: "medium", 2: "high"}

    final_level = rule_level
    final_score = rule_score

    # Check ML model
    bundle = load_risk_model() if settings.ml_hybrid_risk else None
    if bundle is not None:
        try:
            model = bundle["model"]
            feature_cols = bundle.get("features", list(feats.keys()))

            df = pd.DataFrame([feats])
            for col in feature_cols:
                if col not in df.columns:
                    df[col] = 0.0

            X = df[feature_cols]
            probs = model.predict_proba(X)[0]
            # classes: 0=low, 1=medium, 2=high
            ml_class_idx = int(np.argmax(probs))
            ml_level = rank_level.get(ml_class_idx, "low")

            # Score mapping:
            # low: 0-30, medium: 31-70, high: 71-100
            ml_score = int(round(probs[0] * 20 + probs[1] * 50 + probs[2] * 85))

            # Apply clinical safety floor: cannot downgrade below rule level!
            if level_rank[ml_level] > level_rank[rule_level]:
                final_level = ml_level
                final_score = max(final_score, ml_score)
            else:
                final_level = rule_level
                final_score = max(rule_score, ml_score)

        except Exception as e:
            print(f"⚠️ Risk model evaluation failed, using safety rules: {e}")

    # Ensure score stays in valid tier bracket
    if final_level == "high":
        final_score = max(71, min(100, final_score))
    elif final_level == "medium":
        final_score = max(31, min(70, final_score))
    else:
        final_score = max(5, min(30, final_score))

    # Construct clean reasoning text
    if reasons:
        reasoning = f"Patient flagged as {final_level.upper()} risk due to: {'; '.join(reasons)}"
    else:
        reasoning = "All monitored vital signs and reported symptoms are within normal baseline ranges."

    return {
        "risk_level": final_level,
        "score": final_score,
        "reasoning": reasoning,
        "factors": factors,
    }
