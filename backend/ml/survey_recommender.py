"""
Discharge+ — Survey Recommender
Multi-label question type recommendation:
- Cold-start disease rules
- Trained Multi-label XGBoost classifier
- Doctor reason generation via Groq or deterministic fallback
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
from config import get_settings

settings = get_settings()

QUESTION_TYPES = [
    "fever",
    "spo2",
    "bp",
    "sugar",
    "pain",
    "photo",
    "voice",
    "custom_text",
]

# Cold-start clinical rule mapping
DISEASE_RULES = {
    "diabetes": {
        "selected": ["sugar", "bp"],
        "scores": {"sugar": 0.98, "bp": 0.85, "pain": 0.40, "fever": 0.35, "photo": 0.20, "voice": 0.15, "custom_text": 0.30, "spo2": 0.25},
        "reasons": {
            "sugar": "Monitor blood glucose fluctuations post-discharge.",
            "bp": "Evaluate vascular status and diabetic hypertension risk.",
        },
    },
    "cardiac": {
        "selected": ["bp", "spo2"],
        "scores": {"bp": 0.99, "spo2": 0.92, "pain": 0.50, "fever": 0.30, "sugar": 0.35, "photo": 0.10, "voice": 0.20, "custom_text": 0.35},
        "reasons": {
            "bp": "Track cardiovascular hemodynamic stability.",
            "spo2": "Detect cardiopulmonary desaturation and early fluid overload.",
        },
    },
    "post_surgical": {
        "selected": ["pain", "photo", "fever"],
        "scores": {"pain": 0.97, "photo": 0.92, "fever": 0.88, "bp": 0.40, "spo2": 0.35, "sugar": 0.30, "voice": 0.15, "custom_text": 0.40},
        "reasons": {
            "pain": "Quantify post-operative pain trajectory and analgesia efficacy.",
            "photo": "Assess surgical incision site healing and inspect for infection.",
            "fever": "Detect early surgical site or systemic infection.",
        },
    },
    "respiratory": {
        "selected": ["spo2", "fever", "voice"],
        "scores": {"spo2": 0.99, "fever": 0.89, "voice": 0.78, "bp": 0.40, "pain": 0.35, "sugar": 0.25, "photo": 0.10, "custom_text": 0.50},
        "reasons": {
            "spo2": "Continuous monitoring of oxygenation and respiratory reserve.",
            "fever": "Identify worsening pneumonia or secondary infection.",
            "voice": "Acoustic assessment of dyspnea, wheezing, or cough severity.",
        },
    },
    "orthopedic": {
        "selected": ["pain", "photo"],
        "scores": {"pain": 0.96, "photo": 0.82, "fever": 0.65, "bp": 0.35, "spo2": 0.30, "sugar": 0.25, "voice": 0.15, "custom_text": 0.45},
        "reasons": {
            "pain": "Evaluate mobility comfort and orthopedic recovery progression.",
            "photo": "Monitor wound margin integrity and swelling at operative site.",
        },
    },
    "general": {
        "selected": ["fever", "pain", "custom_text"],
        "scores": {"fever": 0.75, "pain": 0.70, "custom_text": 0.65, "bp": 0.45, "spo2": 0.40, "sugar": 0.30, "photo": 0.25, "voice": 0.20},
        "reasons": {
            "fever": "Baseline vital monitoring for early systemic infection.",
            "pain": "General recovery comfort assessment.",
            "custom_text": "Allow patient to report non-specific symptoms.",
        },
    },
}

MODEL_PATH = Path(__file__).resolve().parent / "models" / "survey_recommender.joblib"
_cached_model = None


def load_recommender_model():
    """Load model artifact from disk with caching."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            return _cached_model
        except Exception as e:
            print(f"⚠️ Failed to load recommender artifact: {e}")
            return None
    return None


def recommend_survey_questions(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate ordered question recommendations for a patient based on diagnosis,
    recovery days, and historical vitals.
    """
    demo = snapshot.get("demographics", {})
    diag_cat = demo.get("diagnosis_category", "general")
    diagnosis_name = demo.get("diagnosis") or diag_cat

    # Check model availability
    model_bundle = load_recommender_model() if settings.ml_survey_recommender else None

    recommendations = []
    mode = "rules"
    version = "rules-1.0.0"

    if model_bundle is not None:
        try:
            from ml.feature_engineering import vectorize_readmission_features
            df = vectorize_readmission_features(snapshot)
            clf = model_bundle.get("model")
            feature_cols = model_bundle.get("features", list(df.columns))

            # Align features
            for c in feature_cols:
                if c not in df.columns:
                    df[c] = 0.0
            X = df[feature_cols]

            # Predict probabilities
            if hasattr(clf, "predict_proba"):
                probs_list = clf.predict_proba(X)
                # MultiOutputClassifier returns list of arrays of shape (n_samples, 2)
                probs = {}
                for idx, q_type in enumerate(QUESTION_TYPES):
                    if idx < len(probs_list):
                        p_arr = probs_list[idx]
                        probs[q_type] = float(p_arr[0][1]) if p_arr.shape[1] > 1 else float(p_arr[0][0])
                    else:
                        probs[q_type] = 0.2
            else:
                probs = {q: 0.5 for q in QUESTION_TYPES}

            mode = "model"
            version = model_bundle.get("version", "xgb-multi-1.0")

            # Fallback reasons template
            rule_entry = DISEASE_RULES.get(diag_cat, DISEASE_RULES["general"])
            for q in QUESTION_TYPES:
                prob = probs.get(q, 0.2)
                selected = prob >= 0.40 or q in rule_entry["selected"]
                reason = rule_entry["reasons"].get(q, f"Indicated by ML profile for {diagnosis_name}.")
                recommendations.append({
                    "id": q,
                    "probability": round(prob, 3),
                    "selected": selected,
                    "reason": reason,
                })

        except Exception as e:
            print(f"⚠️ Recommender model inference failed, falling back to rules: {e}")
            model_bundle = None

    if model_bundle is None:
        # Cold start rules
        rule_entry = DISEASE_RULES.get(diag_cat, DISEASE_RULES["general"])
        for q in QUESTION_TYPES:
            score = rule_entry["scores"].get(q, 0.25)
            selected = q in rule_entry["selected"]
            reason = rule_entry["reasons"].get(q, f"Clinical protocol recommendation for {diagnosis_name}.")
            recommendations.append({
                "id": q,
                "probability": score,
                "selected": selected,
                "reason": reason,
            })

    # Sort recommendations descending by probability
    recommendations.sort(key=lambda x: x["probability"], reverse=True)

    return {
        "patient_id": snapshot.get("patient_id"),
        "diagnosis": diagnosis_name,
        "diagnosis_category": diag_cat,
        "mode": mode,
        "version": version,
        "recommendations": recommendations,
    }
