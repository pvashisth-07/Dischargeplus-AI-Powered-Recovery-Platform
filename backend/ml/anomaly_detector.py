"""
Discharge+ — Vital Trajectory Anomaly Detector & Cohorts
Detects vital trajectory anomalies using Isolation Forest, surfaces observable
trend alerts, provides diagnosis-cohort benchmarks, and generates clinical summaries.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
import pandas as pd
from config import get_settings
from services.ai_service import client, MODEL

settings = get_settings()

MODEL_PATH = Path(__file__).resolve().parent / "models" / "anomaly_detector.joblib"
_cached_model = None

# Reference severity quantiles by cohort for vital benchmarks
COHORT_BENCHMARKS = {
    "diabetes": {"sugar_p90": 190.0, "bp_sys_p90": 145.0},
    "cardiac": {"bp_sys_p90": 150.0, "spo2_p10": 92.0},
    "post_surgical": {"fever_p90": 100.8, "pain_p90": 7.0},
    "respiratory": {"spo2_p10": 91.0, "fever_p90": 101.2},
    "orthopedic": {"pain_p90": 7.5},
    "general": {"fever_p90": 101.0, "pain_p90": 7.0},
}


def load_anomaly_model():
    """Load Isolation Forest artifact."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            return _cached_model
        except Exception as e:
            print(f"⚠️ Failed to load anomaly detector: {e}")
            return None
    return None


def detect_trajectory_anomalies(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate vital trajectory against patient's own history and diagnosis cohort.
    """
    if not settings.ml_anomaly:
        return {
            "status": "disabled",
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "trend_alerts": [],
            "cohort_comparison": None,
        }

    raw_vitals = snapshot.get("raw_vitals", {})
    vital_stats = snapshot.get("vital_stats", {})
    signals = snapshot.get("signals", {})
    demo = snapshot.get("demographics", {})
    diag_cat = demo.get("diagnosis_category", "general")

    trend_alerts = []

    # 1. SpO2 declining alert
    spo2_series = raw_vitals.get("spo2", [])
    if len(spo2_series) >= 3 and spo2_series[-1] < spo2_series[-2] < spo2_series[-3]:
        trend_alerts.append({
            "type": "spo2_decline",
            "severity": "high",
            "message": f"SpO₂ declining 3 surveys in a row ({spo2_series[-3]}% → {spo2_series[-2]}% → {spo2_series[-1]}%).",
        })
    elif len(spo2_series) >= 1 and spo2_series[-1] <= 90:
        trend_alerts.append({
            "type": "spo2_critical",
            "severity": "critical",
            "message": f"Critical low SpO₂ reading: {spo2_series[-1]}%.",
        })

    # 2. Pain score spike
    pain_series = raw_vitals.get("pain", [])
    if len(pain_series) >= 2 and (pain_series[-1] - pain_series[-2] >= 3.0 or pain_series[-1] >= 8.0):
        trend_alerts.append({
            "type": "pain_spike",
            "severity": "medium" if pain_series[-1] < 8 else "high",
            "message": f"Pain score spike detected (jumped to {pain_series[-1]}/10 from {pain_series[-2]}/10).",
        })

    # 3. Fever alert
    fever_series = raw_vitals.get("fever", [])
    if len(fever_series) >= 1 and fever_series[-1] >= 100.4:
        trend_alerts.append({
            "type": "fever_spike",
            "severity": "high" if fever_series[-1] >= 102.5 else "medium",
            "message": f"Fever elevated above baseline: {fever_series[-1]}°F.",
        })

    # 4. Blood sugar spike
    sugar_series = raw_vitals.get("sugar", [])
    if len(sugar_series) >= 1 and sugar_series[-1] >= 200.0:
        trend_alerts.append({
            "type": "sugar_spike",
            "severity": "high" if sugar_series[-1] >= 300 else "medium",
            "message": f"Elevated blood sugar reading: {sugar_series[-1]} mg/dL.",
        })

    # 5. Cohort comparison
    cohort_bench = COHORT_BENCHMARKS.get(diag_cat, COHORT_BENCHMARKS["general"])
    cohort_statements = []

    if diag_cat == "post_surgical" and fever_series and fever_series[-1] >= cohort_bench.get("fever_p90", 100.8):
        cohort_statements.append("Fever severity is in the top 10% for post-surgical recovery cohorts.")
    elif diag_cat == "diabetes" and sugar_series and sugar_series[-1] >= cohort_bench.get("sugar_p90", 190.0):
        cohort_statements.append("Blood glucose fluctuations exceed the 90th percentile for diabetic cohorts.")
    elif diag_cat == "cardiac" and spo2_series and spo2_series[-1] <= cohort_bench.get("spo2_p10", 92.0):
        cohort_statements.append("Oxygen saturation is in the lowest 10% compared to cardiac recovery cohorts.")

    cohort_comparison = {
        "cohort": diag_cat.replace("_", " ").title(),
        "summary": cohort_statements[0] if cohort_statements else f"Vital parameters tracking within normal variance for {diag_cat.replace('_', ' ')} recovery.",
        "has_outlier": len(cohort_statements) > 0,
    }

    # 6. Isolation Forest model check
    iso_bundle = load_anomaly_model()
    is_anomaly = False
    anomaly_score = 0.0

    if iso_bundle is not None:
        try:
            model = iso_bundle.get("model")
            feature_cols = iso_bundle.get("features", [])
            # Build mini feature vector for current observation
            vec = {}
            for col in feature_cols:
                vec[col] = float(vital_stats.get(col, 0.0))
            df = pd.DataFrame([vec])
            pred = model.predict(df)[0]  # -1 for anomaly, 1 for normal
            score = float(-model.decision_function(df)[0])  # higher = more anomalous
            is_anomaly = bool(pred == -1 or len(trend_alerts) > 0)
            anomaly_score = round(max(0.0, score), 3)
        except Exception as e:
            print(f"⚠️ Anomaly model evaluation failed: {e}")
            is_anomaly = len(trend_alerts) > 0
            anomaly_score = 0.6 if is_anomaly else 0.1
    else:
        is_anomaly = len(trend_alerts) > 0
        anomaly_score = 0.7 if is_anomaly else 0.15

    return {
        "status": "ready",
        "is_anomaly": is_anomaly,
        "anomaly_score": anomaly_score,
        "trend_alerts": trend_alerts,
        "cohort_comparison": cohort_comparison,
        "total_surveys_evaluated": len(snapshot.get("raw_vitals", {}).get("fever", [])),
    }


def generate_clinical_insight_narrative(
    patient_name: str,
    diagnosis: str,
    readmission_result: Dict[str, Any],
    anomaly_result: Dict[str, Any],
) -> str:
    """
    Synthesize ML structured output into a concise 2-3 sentence clinical insight for doctors.
    Uses Groq LLM with deterministic clinical fallback.
    """
    prob_pct = readmission_result.get("percentage", 20)
    tier = readmission_result.get("risk_tier", "low")
    contributors = [c.get("feature") for c in readmission_result.get("top_contributors", []) if c.get("feature")]
    alerts = [a.get("message") for a in anomaly_result.get("trend_alerts", [])]
    cohort_text = anomaly_result.get("cohort_comparison", {}).get("summary", "")

    # Deterministic fallback text
    fallback_parts = []
    fallback_parts.append(f"{patient_name} ({diagnosis}) has a predicted 30-day readmission risk of {prob_pct}% ({tier.upper()}).")
    if alerts:
        fallback_parts.append(f"Notable trajectory signal: {' '.join(alerts[:2])}")
    elif contributors:
        fallback_parts.append(f"Key contributing factors include {', '.join(contributors[:2])}.")
    if cohort_text:
        fallback_parts.append(cohort_text)

    deterministic_summary = " ".join(fallback_parts)

    if not client:
        return deterministic_summary

    prompt = f"""You are a clinical decision support assistant for hospital doctors.
Summarize these structured ML findings for patient {patient_name} ({diagnosis}) into exactly 2-3 concise, professional clinical sentences:
- Predicted 30-day readmission risk: {prob_pct}% ({tier} risk)
- Top ML Risk Contributors: {', '.join(contributors) if contributors else 'None'}
- Trajectory Alerts: {'; '.join(alerts) if alerts else 'Stable trajectory'}
- Cohort Benchmark: {cohort_text}

Guidelines:
- Be clear, objective, and clinically relevant.
- Do NOT repeat instructions or use preamble.
- State facts directly."""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Groq narrative generation failed, using fallback: {e}")
        return deterministic_summary
