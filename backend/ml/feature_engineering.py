"""
Discharge+ — Feature Engineering
Extracts and transforms patient, vital trajectory, survey, and medication data
into consistent feature vectors for offline training and online serving.
"""

from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


# Diagnosis categories for one-hot/categorical mapping
DIAGNOSIS_CATEGORIES = [
    "diabetes",
    "cardiac",
    "post_surgical",
    "respiratory",
    "orthopedic",
    "general",
]

# Standard comorbidities to track
COMMON_COMORBIDITIES = [
    "hypertension",
    "diabetes",
    "copd",
    "coronary_artery_disease",
    "obesity",
    "chronic_kidney_disease",
]

# Standard 8 question types
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


def normalize_diagnosis(diag_str: Optional[str]) -> str:
    """Normalize free-text diagnosis into standard category."""
    if not diag_str:
        return "general"
    d = diag_str.lower()
    if any(k in d for k in ["diabet", "sugar", "t2d", "t1d"]):
        return "diabetes"
    if any(k in d for k in ["cardiac", "heart", "coronary", "hypertens", "bp", "infarct"]):
        return "cardiac"
    if any(k in d for k in ["surg", "append", "cholecyst", "hernia", "post-op", "incision", "resect"]):
        return "post_surgical"
    if any(k in d for k in ["pneumon", "asthma", "copd", "respir", "lung", "bronch", "covid"]):
        return "respiratory"
    if any(k in d for k in ["fract", "ortho", "knee", "hip", "spine", "joint"]):
        return "orthopedic"
    return "general"


def parse_bp(answer_value: Optional[str], answer_numeric: Optional[float]):
    """Extract systolic and diastolic from answer fields."""
    systolic = answer_numeric if answer_numeric is not None else 120.0
    diastolic = 80.0

    if answer_value and "/" in str(answer_value):
        try:
            parts = str(answer_value).split("/")
            s = float(parts[0].strip())
            d = float(parts[1].strip())
            if 60 <= s <= 260:
                systolic = s
            if 40 <= d <= 160:
                diastolic = d
        except Exception:
            pass

    return systolic, diastolic


def compute_vital_series_stats(values: List[float]) -> Dict[str, float]:
    """Compute rolling mean, slope, variance, and latest value for a vital series."""
    valid = [v for v in values if v is not None and not np.isnan(v)]
    if not valid:
        return {
            "mean": 0.0,
            "std": 0.0,
            "slope": 0.0,
            "latest": 0.0,
            "count": 0,
            "missing": 1.0,
        }

    arr = np.array(valid, dtype=float)
    count = len(arr)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr)) if count > 1 else 0.0
    latest_val = float(arr[-1])

    # Slope over sequence
    if count >= 2:
        slope = float((arr[-1] - arr[0]) / (count - 1))
    else:
        slope = 0.0

    return {
        "mean": mean_val,
        "std": std_val,
        "slope": slope,
        "latest": latest_val,
        "count": count,
        "missing": 0.0,
    }


def build_patient_feature_snapshot(
    patient_id: str,
    hospital_id: str,
    supabase: Any,
    cutoff: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch scoped snapshot of patient demographics, recent survey responses, vitals,
    risk scores, and medication logs up to cutoff timestamp.
    """
    if cutoff is None:
        cutoff = datetime.now(timezone.utc)

    # 1. Fetch Patient Record
    p_res = supabase.table("patients") \
        .select("*, users(full_name, email)") \
        .eq("id", patient_id) \
        .eq("hospital_id", hospital_id) \
        .single() \
        .execute()

    patient = p_res.data or {}
    if not patient:
        raise ValueError(f"Patient {patient_id} not found in hospital {hospital_id}")

    # Compute Demographics
    dob = patient.get("date_of_birth")
    age = 50.0
    if dob:
        try:
            b_date = datetime.strptime(str(dob)[:10], "%Y-%m-%d").date()
            c_date = cutoff.date() if isinstance(cutoff, datetime) else cutoff
            age = float(c_date.year - b_date.year - ((c_date.month, c_date.day) < (b_date.month, b_date.day)))
        except Exception:
            pass

    diag_cat = normalize_diagnosis(patient.get("diagnosis"))
    comorbidities = patient.get("comorbidities") or []
    comorb_flags = {
        f"comorb_{c}": 1.0 if any(c in str(item).lower() for item in comorbidities) else 0.0
        for c in COMMON_COMORBIDITIES
    }

    discharge_date = patient.get("discharge_date")
    days_since_discharge = 0.0
    if discharge_date:
        try:
            d_date = datetime.strptime(str(discharge_date)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            delta = cutoff - d_date
            days_since_discharge = max(0.0, float(delta.days))
        except Exception:
            pass

    expected_recovery = float(patient.get("expected_recovery_days") or 30)

    # 2. Fetch Recent Survey Responses (up to 20) with answers
    cutoff_iso = cutoff.isoformat() if hasattr(cutoff, "isoformat") else str(cutoff)
    sr_res = supabase.table("survey_responses") \
        .select("id, submitted_at, created_at, response_answers(*)") \
        .eq("patient_id", patient_id) \
        .eq("hospital_id", hospital_id) \
        .lte("created_at", cutoff_iso) \
        .order("created_at", desc=False) \
        .limit(20) \
        .execute()

    survey_responses = sr_res.data or []

    # Aggregate vital streams
    vitals = {
        "fever": [],
        "spo2": [],
        "systolic_bp": [],
        "diastolic_bp": [],
        "sugar": [],
        "pain": [],
    }
    media_flags = {"photo_count": 0, "voice_count": 0}

    for sr in survey_responses:
        answers = sr.get("response_answers") or []
        for ans in answers:
            q_type = ans.get("question_type")
            num_val = ans.get("answer_numeric")
            str_val = ans.get("answer_value")

            if q_type == "fever" and num_val is not None:
                vitals["fever"].append(float(num_val))
            elif q_type == "spo2" and num_val is not None:
                vitals["spo2"].append(float(num_val))
            elif q_type == "sugar" and num_val is not None:
                vitals["sugar"].append(float(num_val))
            elif q_type == "pain" and num_val is not None:
                vitals["pain"].append(float(num_val))
            elif q_type == "bp":
                sys_bp, dia_bp = parse_bp(str_val, num_val)
                vitals["systolic_bp"].append(sys_bp)
                vitals["diastolic_bp"].append(dia_bp)
            elif q_type == "photo" and (ans.get("file_url") or str_val):
                media_flags["photo_count"] += 1
            elif q_type == "voice" and (ans.get("file_url") or str_val):
                media_flags["voice_count"] += 1

    vital_stats = {}
    for vital_name, series in vitals.items():
        stats = compute_vital_series_stats(series)
        for k, v in stats.items():
            vital_stats[f"{vital_name}_{k}"] = v

    # Consecutive SpO2 decline check
    spo2_series = vitals["spo2"]
    spo2_declining_consecutive = 0
    if len(spo2_series) >= 3:
        if spo2_series[-1] < spo2_series[-2] < spo2_series[-3]:
            spo2_declining_consecutive = 3

    # Pain spike check
    pain_series = vitals["pain"]
    pain_spike = 0.0
    if len(pain_series) >= 2:
        diff = pain_series[-1] - pain_series[-2]
        if diff >= 3.0 or pain_series[-1] >= 8.0:
            pain_spike = 1.0

    # 3. Fetch Risk Scores History
    rs_res = supabase.table("risk_scores") \
        .select("score, risk_level, created_at") \
        .eq("patient_id", patient_id) \
        .eq("hospital_id", hospital_id) \
        .lte("created_at", cutoff_iso) \
        .order("created_at", desc=False) \
        .execute()

    risk_rows = rs_res.data or []
    scores = [float(r["score"]) for r in risk_rows if r.get("score") is not None]
    high_risk_count = sum(1 for r in risk_rows if r.get("risk_level") == "high")
    last_risk_score = scores[-1] if scores else 20.0
    mean_risk_score = float(np.mean(scores)) if scores else 20.0

    # 4. Fetch Medications & Logs (last 14 days)
    meds_res = supabase.table("medications") \
        .select("id, name, is_active, frequency") \
        .eq("patient_id", patient_id) \
        .eq("hospital_id", hospital_id) \
        .execute()
    meds = meds_res.data or []
    med_count = len(meds)
    active_med_count = sum(1 for m in meds if m.get("is_active", True))

    logs_res = supabase.table("medication_logs") \
        .select("status, taken_at") \
        .eq("patient_id", patient_id) \
        .eq("hospital_id", hospital_id) \
        .lte("taken_at", cutoff_iso) \
        .order("taken_at", desc=True) \
        .limit(50) \
        .execute()
    logs = logs_res.data or []

    taken_count = sum(1 for l in logs if l.get("status") == "taken")
    missed_count = sum(1 for l in logs if l.get("status") == "missed")
    total_logs = taken_count + missed_count
    adherence_rate = (taken_count / total_logs) if total_logs > 0 else 1.0

    # Recent misses in last 72h
    recent_missed = 0
    now_ts = cutoff.timestamp()
    for l in logs:
        if l.get("status") == "missed":
            try:
                l_ts = datetime.fromisoformat(l["taken_at"].replace("Z", "+00:00")).timestamp()
                if (now_ts - l_ts) <= 72 * 3600:
                    recent_missed += 1
            except Exception:
                pass

    snapshot = {
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "as_of": cutoff_iso,
        "demographics": {
            "age": age,
            "gender": patient.get("gender", "unknown"),
            "diagnosis": patient.get("diagnosis", ""),
            "diagnosis_category": diag_cat,
            "days_since_discharge": days_since_discharge,
            "expected_recovery_days": expected_recovery,
            "comorbidities": comorb_flags,
            "is_readmitted": bool(patient.get("is_readmitted", False)),
        },
        "vital_stats": vital_stats,
        "raw_vitals": vitals,
        "signals": {
            "spo2_declining_consecutive": spo2_declining_consecutive,
            "pain_spike": pain_spike,
            "high_risk_count": high_risk_count,
            "last_risk_score": last_risk_score,
            "mean_risk_score": mean_risk_score,
            "surveys_completed": len(survey_responses),
        },
        "medications": {
            "med_count": med_count,
            "active_med_count": active_med_count,
            "total_logs": total_logs,
            "taken_count": taken_count,
            "missed_count": missed_count,
            "recent_missed": recent_missed,
            "adherence_rate": adherence_rate,
        },
    }

    return snapshot


def vectorize_readmission_features(snapshot: Dict[str, Any]) -> pd.DataFrame:
    """Build a fixed-column feature vector for 30-day readmission prediction."""
    demo = snapshot.get("demographics", {})
    vitals = snapshot.get("vital_stats", {})
    signals = snapshot.get("signals", {})
    meds = snapshot.get("medications", {})

    data = {
        "age": float(demo.get("age", 50.0)),
        "days_since_discharge": float(demo.get("days_since_discharge", 0.0)),
        "expected_recovery_days": float(demo.get("expected_recovery_days", 30.0)),
        "is_male": 1.0 if str(demo.get("gender", "")).lower() == "male" else 0.0,
    }

    # Diagnosis categories
    diag_cat = demo.get("diagnosis_category", "general")
    for cat in DIAGNOSIS_CATEGORIES:
        data[f"diag_{cat}"] = 1.0 if diag_cat == cat else 0.0

    # Comorbidities
    comorbs = demo.get("comorbidities", {})
    for c in COMMON_COMORBIDITIES:
        data[f"comorb_{c}"] = float(comorbs.get(f"comorb_{c}", 0.0))

    # Vitals
    for k, v in vitals.items():
        data[k] = float(v) if v is not None else 0.0

    # Signals
    data["high_risk_count"] = float(signals.get("high_risk_count", 0.0))
    data["last_risk_score"] = float(signals.get("last_risk_score", 20.0))
    data["mean_risk_score"] = float(signals.get("mean_risk_score", 20.0))
    data["surveys_completed"] = float(signals.get("surveys_completed", 0.0))
    data["pain_spike"] = float(signals.get("pain_spike", 0.0))
    data["spo2_declining_consecutive"] = float(signals.get("spo2_declining_consecutive", 0.0))

    # Medications
    data["active_med_count"] = float(meds.get("active_med_count", 1.0))
    data["adherence_rate"] = float(meds.get("adherence_rate", 1.0))
    data["recent_missed"] = float(meds.get("recent_missed", 0.0))

    df = pd.DataFrame([data])
    return df


def vectorize_adherence_features(snapshot: Dict[str, Any]) -> pd.DataFrame:
    """Build feature vector for medication non-adherence prediction."""
    demo = snapshot.get("demographics", {})
    meds = snapshot.get("medications", {})
    signals = snapshot.get("signals", {})

    data = {
        "age": float(demo.get("age", 50.0)),
        "days_since_discharge": float(demo.get("days_since_discharge", 0.0)),
        "active_med_count": float(meds.get("active_med_count", 1.0)),
        "total_med_count": float(meds.get("med_count", 1.0)),
        "adherence_rate": float(meds.get("adherence_rate", 1.0)),
        "recent_missed": float(meds.get("recent_missed", 0.0)),
        "total_logs": float(meds.get("total_logs", 0.0)),
        "last_risk_score": float(signals.get("last_risk_score", 20.0)),
    }

    diag_cat = demo.get("diagnosis_category", "general")
    for cat in DIAGNOSIS_CATEGORIES:
        data[f"diag_{cat}"] = 1.0 if diag_cat == cat else 0.0

    return pd.DataFrame([data])


def extract_survey_answer_features(answers: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Extract normalized vital measurements from a submitted survey response.
    Preserves valid zero (such as pain=0).
    """
    feats = {
        "fever": 98.6,
        "fever_present": 0.0,
        "spo2": 98.0,
        "spo2_present": 0.0,
        "systolic_bp": 120.0,
        "diastolic_bp": 80.0,
        "bp_present": 0.0,
        "sugar": 100.0,
        "sugar_present": 0.0,
        "pain": 0.0,
        "pain_present": 0.0,
        "photo_present": 0.0,
        "voice_present": 0.0,
        "custom_text_present": 0.0,
    }

    for a in answers:
        q_type = a.get("question_type")
        num_val = a.get("answer_numeric")
        val_str = a.get("answer_value") or a.get("answer") or ""

        # Attempt to parse numeric if None
        if num_val is None and val_str:
            try:
                # Extract first float found
                import re
                m = re.search(r"[-+]?(?:\d*\.\d+|\d+)", str(val_str))
                if m:
                    num_val = float(m.group(0))
            except Exception:
                num_val = None

        if q_type == "fever":
            if num_val is not None:
                feats["fever"] = float(num_val)
                feats["fever_present"] = 1.0
        elif q_type == "spo2":
            if num_val is not None:
                feats["spo2"] = float(num_val)
                feats["spo2_present"] = 1.0
        elif q_type == "sugar":
            if num_val is not None:
                feats["sugar"] = float(num_val)
                feats["sugar_present"] = 1.0
        elif q_type == "pain":
            if num_val is not None:
                feats["pain"] = max(0.0, min(10.0, float(num_val)))
                feats["pain_present"] = 1.0
        elif q_type == "bp":
            sys_bp, dia_bp = parse_bp(val_str, num_val)
            feats["systolic_bp"] = sys_bp
            feats["diastolic_bp"] = dia_bp
            feats["bp_present"] = 1.0
        elif q_type == "photo":
            if a.get("file_url") or val_str:
                feats["photo_present"] = 1.0
        elif q_type == "voice":
            if a.get("file_url") or val_str:
                feats["voice_present"] = 1.0
        elif q_type == "custom_text":
            if val_str and len(str(val_str).strip()) > 0:
                feats["custom_text_present"] = 1.0

    return feats
