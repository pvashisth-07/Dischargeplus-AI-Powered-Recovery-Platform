"""
Discharge+ — Risk Service
Hybrid risk scoring:
1. Calculates risk tier, numeric score, and structured factors using ML (XGBoost + Clinical safety floor)
2. Persists validated structured risk score to database
3. Calls Groq AI strictly for empathetic patient feedback and natural language reasoning
4. Sends real-time notifications to assigned doctors if risk is high
"""

from dependencies import get_supabase_admin
from ml.risk_classifier import classify_survey_risk
from services.ai_service import generate_patient_feedback


def calculate_and_store_risk(
    survey_response_id: str,
    patient_id: str,
    hospital_id: str,
    answers: list,
) -> dict:
    """
    Calculate risk score for a survey response:
    1. Score answers via XGBoost hybrid risk classifier with clinical safety floor
    2. Update the risk_scores record
    3. Generate patient feedback via Groq
    4. Send notification if high risk
    Returns the risk result dict.
    """
    supabase = get_supabase_admin()

    # 1. Score via ML Hybrid Classifier (XGBoost + Clinical safety floor)
    risk_result = classify_survey_risk(answers)

    # 2. Update the risk score record created by the DB trigger
    try:
        supabase.table("risk_scores").update({
            "risk_level": risk_result.get("risk_level", "low"),
            "score": risk_result.get("score", 0),
            "reasoning": risk_result.get("reasoning", ""),
            "factors": risk_result.get("factors", {}),
        }).eq("survey_response_id", survey_response_id).execute()
    except Exception as e:
        print(f"⚠️ Failed to update risk_scores: {e}")

    # 3. Generate empathetic patient feedback via Groq (LLM only for natural language)
    feedback = "Thank you for completing your health check-in! Your responses have been recorded and shared with your doctor."
    try:
        feedback = generate_patient_feedback(answers, risk_result)
    except Exception as e:
        print(f"⚠️ Feedback generation failed, using fallback: {e}")

    # 4. Update survey response with feedback
    try:
        supabase.table("survey_responses").update({
            "ai_feedback": feedback,
        }).eq("id", survey_response_id).execute()
    except Exception as e:
        print(f"⚠️ Failed to update survey_response feedback: {e}")

    # 5. If high risk, create notification for assigned doctors
    if risk_result.get("risk_level") == "high":
        try:
            _notify_high_risk(patient_id, hospital_id, risk_result)
        except Exception as e:
            print(f"⚠️ High-risk notification failed: {e}")

    return {
        "risk_level": risk_result.get("risk_level"),
        "score": risk_result.get("score"),
        "reasoning": risk_result.get("reasoning"),
        "factors": risk_result.get("factors"),
        "feedback": feedback,
    }


def _notify_high_risk(patient_id: str, hospital_id: str, risk_result: dict):
    """Send notifications to assigned doctors when a patient is high risk."""
    supabase = get_supabase_admin()

    # Get patient name
    patient = supabase.table("patients").select("user_id, users(full_name)").eq("id", patient_id).single().execute()
    patient_name = "Unknown Patient"
    if patient.data and patient.data.get("users"):
        patient_name = patient.data["users"].get("full_name", patient_name)

    # Get assigned doctor user_ids
    assignments = supabase.table("assignments") \
        .select("doctors(user_id)") \
        .eq("patient_id", patient_id) \
        .eq("is_active", True) \
        .execute()

    doctor_user_ids = []
    for a in assignments.data or []:
        if a.get("doctors") and a["doctors"].get("user_id"):
            doctor_user_ids.append(a["doctors"]["user_id"])

    # Create notification for each assigned doctor
    for doc_uid in doctor_user_ids:
        supabase.table("notifications").insert({
            "hospital_id": hospital_id,
            "user_id": doc_uid,
            "title": f"⚠️ High Risk Alert: {patient_name}",
            "message": risk_result.get("reasoning", "Patient scored high risk on latest survey."),
            "type": "alert",
            "metadata": {
                "patient_id": patient_id,
                "risk_level": "high",
                "score": risk_result.get("score"),
            },
        }).execute()
