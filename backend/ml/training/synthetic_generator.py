"""
Discharge+ — Synthetic Data Generator
Generates realistic clinical training cohorts covering:
- Diabetic, cardiac, post-surgical, respiratory, orthopedic, and general recovery profiles
- Longitudinal vitals, pain trajectories, and survey answers
- 30-day readmission outcomes and medication adherence logs
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from ml.feature_engineering import (
    DIAGNOSIS_CATEGORIES,
    COMMON_COMORBIDITIES,
    QUESTION_TYPES,
)


def generate_synthetic_patients(n_samples: int = 1200, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic patient cohort for ML training."""
    np.random.seed(seed)

    records = []
    diag_weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]

    for i in range(n_samples):
        diag = np.random.choice(DIAGNOSIS_CATEGORIES, p=diag_weights)
        age = int(np.random.normal(58, 14))
        age = max(18, min(92, age))
        gender = np.random.choice(["male", "female"], p=[0.52, 0.48])
        days_since_dc = int(np.random.exponential(8))
        days_since_dc = min(30, days_since_dc)
        expected_rec = int(np.random.choice([14, 21, 30, 45, 60], p=[0.2, 0.3, 0.3, 0.1, 0.1]))

        # Comorbidities based on primary diagnosis
        comorb_hypertension = int(np.random.rand() < (0.75 if diag == "cardiac" else 0.40))
        comorb_diabetes = int(np.random.rand() < (0.95 if diag == "diabetes" else 0.25))
        comorb_copd = int(np.random.rand() < (0.70 if diag == "respiratory" else 0.15))
        comorb_cad = int(np.random.rand() < (0.60 if diag == "cardiac" else 0.15))
        comorb_obesity = int(np.random.rand() < 0.30)
        comorb_ckd = int(np.random.rand() < 0.15)

        # Baseline vitals and trends
        fever_mean = np.random.normal(98.6, 0.6)
        spo2_mean = np.random.normal(97.5, 1.5)
        sys_bp_mean = np.random.normal(128, 14)
        dia_bp_mean = np.random.normal(82, 8)
        sugar_mean = np.random.normal(160 if diag == "diabetes" else 105, 30 if diag == "diabetes" else 15)
        pain_mean = np.random.normal(5.0 if diag in ["post_surgical", "orthopedic"] else 2.0, 1.8)

        # Trajectory signals
        fever_slope = np.random.normal(0.0, 0.2)
        spo2_slope = np.random.normal(-0.1 if diag == "respiratory" else 0.0, 0.3)
        spo2_dec_consec = int(np.random.choice([0, 1, 2, 3], p=[0.75, 0.15, 0.07, 0.03]))
        pain_spike = int(np.random.choice([0, 1], p=[0.85, 0.15]))

        # Past risk scores & adherence
        high_risk_count = int(np.random.poisson(0.4))
        mean_risk_score = min(100.0, max(10.0, np.random.normal(30 + high_risk_count * 18, 12)))
        last_risk_score = min(100.0, max(10.0, mean_risk_score + np.random.normal(0, 10)))

        med_count = int(np.random.choice([1, 2, 3, 4, 5, 6], p=[0.1, 0.2, 0.3, 0.2, 0.1, 0.1]))
        adherence_rate = min(1.0, max(0.2, np.random.beta(8, 2)))
        recent_missed = int(np.random.poisson(0.5))

        # 30-day readmission probability ground truth calculation
        readmit_logit = (
            -2.8
            + 0.02 * (age - 50)
            + 0.03 * (sys_bp_mean - 120)
            + (1.2 if spo2_dec_consec >= 3 else 0.0)
            + (0.8 if pain_spike else 0.0)
            + (0.02 * (mean_risk_score - 30))
            + (0.9 if high_risk_count >= 2 else 0.0)
            + (0.8 * (1.0 - adherence_rate))
            + (0.5 if comorb_hypertension and comorb_cad else 0.0)
        )
        readmit_prob = 1.0 / (1.0 + np.exp(-readmit_logit))
        is_readmitted = int(np.random.rand() < readmit_prob)

        # Medication non-adherence ground truth (miss dose in 48h)
        adhere_logit = (
            -1.8
            + 2.5 * (1.0 - adherence_rate)
            + 0.4 * recent_missed
            + 0.2 * med_count
            + 0.01 * (age - 50)
        )
        miss_prob = 1.0 / (1.0 + np.exp(-adhere_logit))
        will_miss_next_dose = int(np.random.rand() < miss_prob)

        # Question type ground truth (multi-label)
        q_sugar = int(diag == "diabetes" or comorb_diabetes or np.random.rand() < 0.15)
        q_bp = int(diag in ["cardiac", "diabetes"] or comorb_hypertension or np.random.rand() < 0.25)
        q_spo2 = int(diag in ["cardiac", "respiratory"] or comorb_copd or np.random.rand() < 0.20)
        q_pain = int(diag in ["post_surgical", "orthopedic"] or pain_spike or np.random.rand() < 0.30)
        q_photo = int(diag in ["post_surgical", "orthopedic"] or np.random.rand() < 0.12)
        q_fever = int(diag in ["post_surgical", "respiratory"] or high_risk_count > 0 or np.random.rand() < 0.35)
        q_voice = int(diag == "respiratory" or np.random.rand() < 0.10)
        q_text = int(diag == "general" or np.random.rand() < 0.40)

        rec = {
            "age": age,
            "days_since_discharge": days_since_dc,
            "expected_recovery_days": expected_rec,
            "is_male": 1.0 if gender == "male" else 0.0,
            "diagnosis_category": diag,
            "comorb_hypertension": float(comorb_hypertension),
            "comorb_diabetes": float(comorb_diabetes),
            "comorb_copd": float(comorb_copd),
            "comorb_coronary_artery_disease": float(comorb_cad),
            "comorb_obesity": float(comorb_obesity),
            "comorb_chronic_kidney_disease": float(comorb_ckd),
            "fever_latest": round(fever_mean + fever_slope, 1),
            "fever_mean": round(fever_mean, 1),
            "fever_std": round(np.random.uniform(0.1, 0.8), 2),
            "fever_slope": round(fever_slope, 2),
            "spo2_latest": round(spo2_mean + spo2_slope, 1),
            "spo2_mean": round(spo2_mean, 1),
            "spo2_std": round(np.random.uniform(0.5, 2.0), 2),
            "spo2_slope": round(spo2_slope, 2),
            "systolic_bp_latest": round(sys_bp_mean, 1),
            "diastolic_bp_latest": round(dia_bp_mean, 1),
            "sugar_latest": round(sugar_mean, 1),
            "sugar_mean": round(sugar_mean, 1),
            "sugar_std": round(np.random.uniform(5, 25), 1),
            "sugar_slope": round(np.random.normal(0, 2), 1),
            "pain_latest": round(pain_mean, 1),
            "pain_mean": round(pain_mean, 1),
            "pain_std": round(np.random.uniform(0.2, 1.5), 1),
            "pain_slope": round(np.random.normal(0, 0.4), 2),
            "spo2_declining_consecutive": float(spo2_dec_consec),
            "pain_spike": float(pain_spike),
            "high_risk_count": float(high_risk_count),
            "last_risk_score": round(last_risk_score, 1),
            "mean_risk_score": round(mean_risk_score, 1),
            "surveys_completed": float(np.random.randint(1, 15)),
            "active_med_count": float(med_count),
            "total_med_count": float(med_count + np.random.randint(0, 2)),
            "adherence_rate": round(adherence_rate, 3),
            "recent_missed": float(recent_missed),
            # Targets
            "target_readmitted": is_readmitted,
            "target_miss_dose": will_miss_next_dose,
            "label_fever": q_fever,
            "label_spo2": q_spo2,
            "label_bp": q_bp,
            "label_sugar": q_sugar,
            "label_pain": q_pain,
            "label_photo": q_photo,
            "label_voice": q_voice,
            "label_custom_text": q_text,
        }

        # Add one-hot diag columns
        for c in DIAGNOSIS_CATEGORIES:
            rec[f"diag_{c}"] = 1.0 if diag == c else 0.0

        records.append(rec)

    return pd.DataFrame(records)


def generate_synthetic_survey_responses(n_samples: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic survey responses and labels for 3-class XGBoost risk classifier."""
    np.random.seed(seed)
    data = []

    for _ in range(n_samples):
        # Sample vitals
        is_high = np.random.rand() < 0.20
        is_medium = not is_high and (np.random.rand() < 0.35)

        if is_high:
            fever = np.random.choice([103.2, 102.5, 94.8, 101.5])
            spo2 = np.random.choice([88.0, 89.5, 91.0, 93.0])
            sys_bp = np.random.choice([185.0, 192.0, 78.0, 160.0])
            dia_bp = np.random.choice([115.0, 124.0, 48.0, 98.0])
            sugar = np.random.choice([320.0, 380.0, 45.0, 220.0])
            pain = np.random.choice([8.0, 9.0, 10.0, 6.0])
            risk_class = 2  # high
            score = int(np.random.uniform(72, 98))
        elif is_medium:
            fever = np.random.choice([100.8, 101.2, 98.6])
            spo2 = np.random.choice([93.0, 92.0, 95.0])
            sys_bp = np.random.choice([148.0, 155.0, 120.0])
            dia_bp = np.random.choice([94.0, 96.0, 80.0])
            sugar = np.random.choice([210.0, 240.0, 110.0])
            pain = np.random.choice([4.0, 5.0, 6.0, 2.0])
            risk_class = 1  # medium
            score = int(np.random.uniform(35, 68))
        else:
            fever = np.random.normal(98.6, 0.4)
            spo2 = np.random.normal(98.0, 0.8)
            sys_bp = np.random.normal(120.0, 8.0)
            dia_bp = np.random.normal(80.0, 5.0)
            sugar = np.random.normal(100.0, 12.0)
            pain = np.random.choice([0.0, 1.0, 2.0])
            risk_class = 0  # low
            score = int(np.random.uniform(5, 28))

        row = {
            "fever": round(fever, 1),
            "fever_present": 1.0,
            "spo2": round(spo2, 1),
            "spo2_present": 1.0,
            "systolic_bp": round(sys_bp, 1),
            "diastolic_bp": round(dia_bp, 1),
            "bp_present": 1.0,
            "sugar": round(sugar, 1),
            "sugar_present": 1.0,
            "pain": round(pain, 1),
            "pain_present": 1.0,
            "photo_present": float(np.random.rand() < 0.25),
            "voice_present": float(np.random.rand() < 0.15),
            "custom_text_present": float(np.random.rand() < 0.30),
            "target_risk_class": risk_class,
            "target_score": score,
        }
        data.append(row)

    return pd.DataFrame(data)
