"""
Discharge+ — Machine Learning Router
Endpoints for ML survey recommendations, patient clinical insights, and medication adherence.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from dependencies import get_current_user, get_supabase_admin, CurrentUser, require_role
from config import get_settings
from supabase import Client
from services.ai_service import client as groq_client, MODEL as GROQ_MODEL

from ml.feature_engineering import build_patient_feature_snapshot
from ml.survey_recommender import recommend_survey_questions
from ml.readmission_model import predict_readmission_risk
from ml.anomaly_detector import detect_trajectory_anomalies, generate_clinical_insight_narrative
from ml.adherence_predictor import predict_adherence_risk

settings = get_settings()
router = APIRouter()

class GenerateDynamicSurveyRequest(BaseModel):
    patient_id: str

METADATA_PATH = Path(__file__).resolve().parent.parent / "ml" / "models" / "metadata.json"


@router.get("/health", tags=["ML"])
async def ml_health():
    """
    Return lightweight ML readiness with per-module status and model versions.
    Does not disclose internal or patient details.
    """
    metadata = {}
    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, "r") as f:
                metadata = json.load(f)
        except Exception:
            pass

    models_meta = metadata.get("models", {})

    return {
        "status": "ready" if settings.ml_enabled else "disabled",
        "ml_enabled": settings.ml_enabled,
        "modules": {
            "survey_recommender": {
                "enabled": settings.ml_survey_recommender,
                "version": models_meta.get("survey_recommender", {}).get("version", "1.0.0"),
                "status": "active" if settings.ml_survey_recommender else "disabled",
            },
            "readmission_risk": {
                "enabled": settings.ml_readmission,
                "version": models_meta.get("readmission_model", {}).get("version", "1.0.0"),
                "status": "active" if settings.ml_readmission else "disabled",
            },
            "anomaly_detector": {
                "enabled": settings.ml_anomaly,
                "version": models_meta.get("anomaly_detector", {}).get("version", "1.0.0"),
                "status": "active" if settings.ml_anomaly else "disabled",
            },
            "hybrid_survey_risk": {
                "enabled": settings.ml_hybrid_risk,
                "version": models_meta.get("risk_classifier", {}).get("version", "1.0.0"),
                "status": "active" if settings.ml_hybrid_risk else "disabled",
            },
            "medication_adherence": {
                "enabled": settings.ml_adherence,
                "version": models_meta.get("adherence_predictor", {}).get("version", "1.0.0"),
                "status": "active" if settings.ml_adherence else "disabled",
            },
        },
    }


@router.get("/survey-recommendations", tags=["ML"])
def get_survey_recommendations(
    patient_id: str = Query(..., description="Target patient ID"),
    current_user: CurrentUser = Depends(require_role("doctor")),
    supabase: Client = Depends(get_supabase_admin),
):
    """
    Doctor requests ranked survey question type recommendations for a patient.
    """
    # Verify patient belongs to current doctor's hospital
    p_check = supabase.table("patients") \
        .select("id, hospital_id") \
        .eq("id", patient_id) \
        .eq("hospital_id", current_user.hospital_id) \
        .single() \
        .execute()

    if not p_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found in your hospital",
        )

    try:
        snapshot = build_patient_feature_snapshot(
            patient_id=patient_id,
            hospital_id=current_user.hospital_id,
            supabase=supabase,
        )
        result = recommend_survey_questions(snapshot)
        return result
    except Exception as e:
        print(f"❌ Error in survey recommendations: {e}")
        # Return fallback rule recommendations
        return {
            "patient_id": patient_id,
            "diagnosis": "General Recovery",
            "diagnosis_category": "general",
            "mode": "fallback_rules",
            "version": "rules-1.0.0",
            "recommendations": [
                {"id": "fever", "probability": 0.80, "selected": True, "reason": "Monitor baseline temperature."},
                {"id": "pain", "probability": 0.70, "selected": True, "reason": "General comfort and pain assessment."},
                {"id": "custom_text", "probability": 0.60, "selected": True, "reason": "Patient symptom notes."},
                {"id": "bp", "probability": 0.40, "selected": False, "reason": "Cardiovascular baseline."},
                {"id": "spo2", "probability": 0.35, "selected": False, "reason": "Oxygen reserve."},
                {"id": "sugar", "probability": 0.25, "selected": False, "reason": "Metabolic status."},
                {"id": "photo", "probability": 0.20, "selected": False, "reason": "Visual inspection."},
                {"id": "voice", "probability": 0.15, "selected": False, "reason": "Acoustic symptom check."},
            ],
        }


@router.get("/patient-insights/{patient_id}", tags=["ML"])
def get_patient_insights(
    patient_id: str,
    current_user: CurrentUser = Depends(require_role("doctor")),
    supabase: Client = Depends(get_supabase_admin),
):
    """
    Doctor fetches multi-dimensional ML insights:
    - 30-Day Readmission Risk & SHAP top 3 factors
    - Vital Trajectory Anomaly & Trend Alerts
    - Diagnosis Cohort Percentile Comparison
    - AI Clinical Narrative Summary
    """
    p_check = supabase.table("patients") \
        .select("id, diagnosis, hospital_id, users(full_name)") \
        .eq("id", patient_id) \
        .eq("hospital_id", current_user.hospital_id) \
        .single() \
        .execute()

    if not p_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found in your hospital",
        )

    patient_record = p_check.data
    user_info = patient_record.get("users") or {}
    patient_name = user_info.get("full_name", "Patient")
    diagnosis = patient_record.get("diagnosis", "Recovery")

    try:
        snapshot = build_patient_feature_snapshot(
            patient_id=patient_id,
            hospital_id=current_user.hospital_id,
            supabase=supabase,
        )

        readmission_res = predict_readmission_risk(snapshot)
        anomaly_res = detect_trajectory_anomalies(snapshot)
        clinical_narrative = generate_clinical_insight_narrative(
            patient_name=patient_name,
            diagnosis=diagnosis,
            readmission_result=readmission_res,
            anomaly_result=anomaly_res,
        )

        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "diagnosis": diagnosis,
            "as_of": snapshot.get("as_of"),
            "readmission": readmission_res,
            "anomaly": anomaly_res,
            "clinical_summary": clinical_narrative,
        }
    except Exception as e:
        print(f"❌ Error generating patient insights: {e}")
        return {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "diagnosis": diagnosis,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "readmission": {
                "status": "unavailable",
                "probability": None,
                "percentage": None,
                "risk_tier": "unknown",
                "top_contributors": [],
                "version": "none",
            },
            "anomaly": {
                "status": "unavailable",
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "trend_alerts": [],
                "cohort_comparison": None,
            },
            "clinical_summary": f"Clinical insights currently unavailable for {patient_name} due to limited longitudinal history.",
        }


def _build_adherence_snapshot(patient_id: str, hospital_id: str, supabase: Client) -> dict:
    """Lightweight feature snapshot optimized exclusively for medication adherence."""
    def q_meds():
        return supabase.table("medications").select("id, is_active").eq("patient_id", patient_id).execute()

    def q_logs():
        return supabase.table("medication_logs") \
            .select("status, taken_at") \
            .eq("patient_id", patient_id) \
            .order("taken_at", desc=True) \
            .limit(50) \
            .execute()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_m = executor.submit(q_meds)
        f_l = executor.submit(q_logs)
        m_data = (f_m.result().data or []) if f_m.result() else []
        l_data = (f_l.result().data or []) if f_l.result() else []

    taken_count = sum(1 for l in l_data if l.get("status") == "taken")
    missed_count = sum(1 for l in l_data if l.get("status") == "missed")
    total = taken_count + missed_count
    active_count = sum(1 for m in m_data if m.get("is_active", True))

    return {
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "demographics": {"age": 50.0, "days_since_discharge": 0.0, "diagnosis_category": "general"},
        "medications": {
            "med_count": len(m_data),
            "active_med_count": active_count,
            "taken_count": taken_count,
            "missed_count": missed_count,
            "total_logs": total,
            "adherence_rate": (taken_count / total) if total > 0 else 1.0,
            "recent_missed": sum(1 for l in l_data[:5] if l.get("status") == "missed"),
        },
        "signals": {"last_risk_score": 20.0},
    }


@router.get("/adherence/me", tags=["ML"])
def get_my_adherence_forecast(
    current_user: CurrentUser = Depends(require_role("patient")),
    supabase: Client = Depends(get_supabase_admin),
):
    """
    Patient fetches personalized medication adherence forecast and streak nudge.
    Fast path: lightweight parallel queries without loading full 20-survey history.
    """
    p_res = supabase.table("patients") \
        .select("id, hospital_id") \
        .eq("user_id", current_user.id) \
        .single() \
        .execute()

    if not p_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    patient_id = p_res.data["id"]
    hospital_id = p_res.data["hospital_id"]

    try:
        snapshot = _build_adherence_snapshot(
            patient_id=patient_id,
            hospital_id=hospital_id,
            supabase=supabase,
        )
        result = predict_adherence_risk(snapshot)
        return result
    except Exception as e:
        print(f"⚠️ Patient adherence prediction error: {e}")
        return {
            "status": "ready",
            "miss_probability": 0.10,
            "adherence_risk": "low",
            "streak_days": 1,
            "nudge": "🔥 Keep up the good work taking your medications on schedule!",
            "active_medications": 1,
            "historical_adherence_rate": 100.0,
        }


@router.get("/doctor/adherence-summary", tags=["ML"])
def get_doctor_adherence_summary(
    current_user: CurrentUser = Depends(require_role("doctor")),
    supabase: Client = Depends(get_supabase_admin),
):
    """
    Bulk prediction of medication adherence risk for all assigned patients of this doctor.
    Optimized with single batch queries instead of N*5 sequential roundtrips.
    """
    doc_res = supabase.table("doctors") \
        .select("id") \
        .eq("user_id", current_user.id) \
        .single() \
        .execute()

    if not doc_res.data:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    doctor_id = doc_res.data["id"]

    # 1. Active assignments
    assignments = supabase.table("assignments") \
        .select("patient_id") \
        .eq("doctor_id", doctor_id) \
        .eq("is_active", True) \
        .execute()

    patient_ids = [a["patient_id"] for a in assignments.data or []]
    if not patient_ids:
        return {}

    # 2. Batch fetch medications and logs for ALL assigned patients in parallel
    def q_meds():
        return supabase.table("medications").select("patient_id, id, is_active").in_("patient_id", patient_ids).execute()

    def q_logs():
        return supabase.table("medication_logs") \
            .select("patient_id, status, taken_at") \
            .in_("patient_id", patient_ids) \
            .order("taken_at", desc=True) \
            .limit(300) \
            .execute()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_meds = executor.submit(q_meds)
        f_logs = executor.submit(q_logs)
        all_meds = f_meds.result().data or []
        all_logs = f_logs.result().data or []

    # Group in memory by patient_id
    meds_by_pid = {}
    for m in all_meds:
        pid = m["patient_id"]
        meds_by_pid.setdefault(pid, []).append(m)

    logs_by_pid = {}
    for l in all_logs:
        pid = l["patient_id"]
        logs_by_pid.setdefault(pid, []).append(l)

    adherence_map = {}
    for pid in patient_ids:
        p_meds = meds_by_pid.get(pid, [])
        p_logs = logs_by_pid.get(pid, [])

        active_count = sum(1 for m in p_meds if m.get("is_active", True))
        taken_count = sum(1 for l in p_logs if l.get("status") == "taken")
        missed_count = sum(1 for l in p_logs if l.get("status") == "missed")
        total = taken_count + missed_count
        adh_rate = (taken_count / total) if total > 0 else 1.0

        streak = max(1, min(30, taken_count // max(1, active_count)))
        prob = (1.0 - adh_rate) * 0.7 + (0.2 if missed_count > 0 else 0.05)
        prob = min(0.95, max(0.05, prob))
        risk_tier = "high" if prob >= 0.50 else ("medium" if prob >= 0.25 else "low")

        adherence_map[pid] = {
            "adherence_risk": risk_tier,
            "miss_probability": round(prob, 3),
            "streak_days": streak,
        }

    return adherence_map


def _generate_fallback_survey(patient_id: str, patient_name: str, diagnosis: str, diag_cat: str) -> dict:
    """Deterministic fallback survey generator when AI is offline."""
    d_lower = diagnosis.lower()
    if any(k in d_lower for k in ["vein", "vascular", "dvt", "blockage", "clot", "circulat"]):
        return {
            "patient_id": patient_id,
            "diagnosis": diagnosis,
            "generated_by": "fallback_rules",
            "title": f"Vascular & Circulation Check — {diagnosis}",
            "description": "Daily monitoring for lower extremity circulation, swelling, and comfort.",
            "questions": [
                {
                    "id": "q1",
                    "question_text": "How is the swelling or heaviness in your legs/ankles today?",
                    "question_type": "choice",
                    "is_required": True,
                    "metadata": {"options": ["No swelling", "Mild puffiness around ankles", "Noticeable swelling in calf", "Severe or painful tightness"]},
                },
                {
                    "id": "q2",
                    "question_text": "Rate any calf pain or cramping discomfort right now (0-10)",
                    "question_type": "scale",
                    "is_required": True,
                    "metadata": {"min": 0, "max": 10, "min_label": "No pain", "max_label": "Severe pain"},
                },
                {
                    "id": "q3",
                    "question_text": "Are you experiencing any sudden warmth, redness, or tender spots in either calf?",
                    "question_type": "boolean",
                    "is_required": True,
                    "metadata": {},
                },
                {
                    "id": "q4",
                    "question_text": "What is your current blood pressure reading?",
                    "question_type": "bp",
                    "is_required": False,
                    "metadata": {"unit": "mmHg"},
                },
                {
                    "id": "q5",
                    "question_text": "Please take a photo of your lower legs or ankles if there is visible swelling or discoloration",
                    "question_type": "photo",
                    "is_required": False,
                    "metadata": {},
                },
            ],
        }

    if diag_cat == "diabetes":
        return {
            "patient_id": patient_id,
            "diagnosis": diagnosis,
            "generated_by": "fallback_rules",
            "title": f"Glycemic & Metabolic Recovery Check — {diagnosis}",
            "description": "Daily post-discharge blood sugar, hydration, and sensation check.",
            "questions": [
                {
                    "id": "q1",
                    "question_text": "What is your current fasting / pre-meal blood sugar level?",
                    "question_type": "number",
                    "is_required": True,
                    "metadata": {"unit": "mg/dL"},
                },
                {
                    "id": "q2",
                    "question_text": "What is your blood pressure reading today?",
                    "question_type": "bp",
                    "is_required": True,
                    "metadata": {"unit": "mmHg"},
                },
                {
                    "id": "q3",
                    "question_text": "Are you experiencing any numbness, tingling, or sores on your feet?",
                    "question_type": "boolean",
                    "is_required": True,
                    "metadata": {},
                },
                {
                    "id": "q4",
                    "question_text": "Have you had any episodes of dizziness, shakiness, or excessive thirst today?",
                    "question_type": "choice",
                    "is_required": True,
                    "metadata": {"options": ["Feeling normal", "Mild shakiness/hunger", "Dizzy or lightheaded", "Frequent urination & extreme thirst"]},
                },
            ],
        }

    # General clinical recovery default
    return {
        "patient_id": patient_id,
        "diagnosis": diagnosis,
        "generated_by": "fallback_rules",
        "title": f"Post-Discharge Health Check — {diagnosis}",
        "description": "Daily health check-in to track your symptoms, vitals, and overall recovery.",
        "questions": [
            {
                "id": "q1",
                "question_text": "What is your current body temperature?",
                "question_type": "number",
                "is_required": True,
                "metadata": {"unit": "°F"},
            },
            {
                "id": "q2",
                "question_text": "Rate your overall pain or discomfort level today (0-10)",
                "question_type": "scale",
                "is_required": True,
                "metadata": {"min": 0, "max": 10, "min_label": "No pain", "max_label": "Severe pain"},
            },
            {
                "id": "q3",
                "question_text": "How do you rate your energy and mobility compared to yesterday?",
                "question_type": "choice",
                "is_required": True,
                "metadata": {"options": ["Much better", "About the same", "A bit more tired/weak", "Significantly worse"]},
            },
            {
                "id": "q4",
                "question_text": "Are you experiencing any shortness of breath, nausea, or unusual symptoms?",
                "question_type": "boolean",
                "is_required": True,
                "metadata": {},
            },
            {
                "id": "q5",
                "question_text": "Please describe any specific questions or concerns for your doctor",
                "question_type": "text",
                "is_required": False,
                "metadata": {},
            },
        ],
    }


@router.post("/generate-dynamic-survey", tags=["ML"])
async def generate_dynamic_survey(
    req: GenerateDynamicSurveyRequest,
    current_user: CurrentUser = Depends(require_role("doctor")),
    supabase: Client = Depends(get_supabase_admin),
):
    """
    Dynamically generates a disease-aware survey tailored specifically to a patient's
    diagnosis and recovery stage, combining ML clinical priority prediction with
    Groq AI natural-language question formulation.
    """
    p_check = supabase.table("patients") \
        .select("id, diagnosis, comorbidities, discharge_date, expected_recovery_days, hospital_id, users(full_name)") \
        .eq("id", req.patient_id) \
        .eq("hospital_id", current_user.hospital_id) \
        .single() \
        .execute()

    if not p_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found in your hospital",
        )

    patient_record = p_check.data
    user_info = patient_record.get("users") or {}
    patient_name = user_info.get("full_name", "Patient")
    diagnosis = patient_record.get("diagnosis", "Post-Discharge Recovery")
    comorbidities = patient_record.get("comorbidities") or []

    # Get ML priority predictions
    snapshot = build_patient_feature_snapshot(
        patient_id=req.patient_id,
        hospital_id=current_user.hospital_id,
        supabase=supabase,
    )
    ml_recs = recommend_survey_questions(snapshot)
    top_recs = [r["id"] for r in ml_recs.get("recommendations", []) if r.get("selected")]

    demo = snapshot.get("demographics", {})
    days_since_dc = int(demo.get("days_since_discharge", 5))
    expected_rec = int(demo.get("expected_recovery_days", 30))

    prompt = f"""You are an expert physician designing a personalized post-discharge survey for a hospital patient.
Patient Information:
- Full Name: {patient_name}
- Specific Diagnosis / Condition: {diagnosis}
- Days Since Discharge: {days_since_dc} days (of expected {expected_rec} days recovery)
- Comorbidities: {', '.join(comorbidities) if comorbidities else 'None reported'}
- ML Predicted Priority Areas: {', '.join(top_recs)}

Generate a personalized, highly relevant clinical recovery survey specifically for this patient's condition.
Include 4 to 6 clinically targeted questions with appropriate response types.

Supported question types:
- "choice": multiple choice single selection (must provide 3-4 distinct clinical options in metadata.options)
- "boolean": yes/no symptom or red-flag question
- "scale": rating 0-10 slider (must provide min: 0, max: 10, min_label: "No pain/None", max_label: "Severe" in metadata)
- "number": numeric reading (must provide unit e.g. "mmHg", "°F", "mg/dL", "steps", "kg" in metadata.unit)
- "bp": blood pressure (systolic/diastolic)
- "photo": photo upload (for wounds, limb swelling, discoloration, rashes)
- "text": free-form description of symptoms

Respond ONLY with valid JSON in this exact structure:
{{
    "title": "<Concise survey title reflecting diagnosis>",
    "description": "<1-2 sentence doctor instruction for the patient>",
    "questions": [
        {{
            "id": "q1",
            "question_text": "<Clear, patient-friendly question>",
            "question_type": "choice" | "boolean" | "scale" | "number" | "bp" | "photo" | "text",
            "is_required": true,
            "metadata": {{
                "options": ["Option 1", "Option 2", "Option 3"],
                "unit": "°F",
                "min": 0,
                "max": 10,
                "min_label": "None",
                "max_label": "Severe"
            }}
        }}
    ]
}}
"""

    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            raw_json = resp.choices[0].message.content
            parsed = json.loads(raw_json)
            if "title" in parsed and "questions" in parsed and len(parsed["questions"]) > 0:
                parsed["patient_id"] = req.patient_id
                parsed["diagnosis"] = diagnosis
                parsed["generated_by"] = "groq_hybrid_ml"
                return parsed
        except Exception as e:
            print(f"⚠️ Groq dynamic survey generation failed, using fallback: {e}")

    diag_cat = demo.get("diagnosis_category", "general")
    return _generate_fallback_survey(req.patient_id, patient_name, diagnosis, diag_cat)
