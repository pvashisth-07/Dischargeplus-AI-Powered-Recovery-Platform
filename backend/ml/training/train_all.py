"""
Discharge+ — Master ML Training Orchestrator
Trains all 5 scikit-learn / XGBoost models:
1. Survey Recommender (Multi-label XGBoost)
2. 30-Day Readmission Risk Predictor (Binary XGBoost + SHAP)
3. Vital Trajectory Anomaly Detector (Isolation Forest)
4. Survey Risk Classifier (3-Class XGBoost)
5. Medication Adherence Predictor (Logistic Regression)
Saves versioned artifacts to backend/ml/models/ and writes metadata.json.
"""

import os
import sys
import json
import hashlib
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    mean_absolute_error,
)
from sklearn.multioutput import MultiOutputClassifier
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.synthetic_generator import (
    generate_synthetic_patients,
    generate_synthetic_survey_responses,
)
from ml.feature_engineering import QUESTION_TYPES

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_file_hash(filepath: Path) -> str:
    """Calculate SHA256 checksum of an artifact."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:16]


def train_survey_recommender(df: pd.DataFrame) -> Dict[str, Any]:
    """Train multi-label classifier for the 8 survey question types."""
    print("Training Survey Recommender (MultiOutput XGBoost)...")
    label_cols = [f"label_{q}" for q in QUESTION_TYPES]

    feature_cols = [
        "age", "days_since_discharge", "expected_recovery_days", "is_male",
        "diag_diabetes", "diag_cardiac", "diag_post_surgical", "diag_respiratory", "diag_orthopedic", "diag_general",
        "comorb_hypertension", "comorb_diabetes", "comorb_copd", "comorb_coronary_artery_disease",
        "comorb_obesity", "comorb_chronic_kidney_disease",
        "fever_mean", "spo2_mean", "sugar_mean", "pain_mean", "systolic_bp_latest",
        "high_risk_count", "mean_risk_score",
    ]

    X = df[feature_cols]
    Y = df[label_cols]

    X_train, X_val, Y_train, Y_val = train_test_split(X, Y, test_size=0.2, random_state=42)

    base_xgb = XGBClassifier(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.08,
        eval_metric="logloss",
        random_state=42,
    )
    model = MultiOutputClassifier(base_xgb)
    model.fit(X_train, Y_train)

    # Evaluate
    Y_pred = model.predict(X_val)
    f1_micro = float(f1_score(Y_val, Y_pred, average="micro"))
    f1_macro = float(f1_score(Y_val, Y_pred, average="macro"))

    artifact_path = MODELS_DIR / "survey_recommender.joblib"
    bundle = {
        "model": model,
        "features": feature_cols,
        "labels": QUESTION_TYPES,
        "version": "xgb-multi-1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, artifact_path)
    print(f"✓ Saved survey_recommender.joblib (F1 micro: {f1_micro:.3f}, macro: {f1_macro:.3f})")

    return {
        "artifact": "survey_recommender.joblib",
        "version": "1.0.0",
        "algorithm": "MultiOutputClassifier(XGBoost)",
        "features": feature_cols,
        "metrics": {"f1_micro": round(f1_micro, 4), "f1_macro": round(f1_macro, 4)},
        "checksum": calculate_file_hash(artifact_path),
    }


def train_readmission_model(df: pd.DataFrame) -> Dict[str, Any]:
    """Train binary classifier for 30-day readmission risk."""
    print("Training 30-Day Readmission Risk Predictor (Binary XGBoost)...")
    feature_cols = [
        "age", "days_since_discharge", "expected_recovery_days", "is_male",
        "diag_diabetes", "diag_cardiac", "diag_post_surgical", "diag_respiratory", "diag_orthopedic", "diag_general",
        "comorb_hypertension", "comorb_diabetes", "comorb_copd", "comorb_coronary_artery_disease",
        "comorb_obesity", "comorb_chronic_kidney_disease",
        "fever_latest", "fever_mean", "fever_slope",
        "spo2_latest", "spo2_mean", "spo2_slope",
        "systolic_bp_latest", "diastolic_bp_latest",
        "sugar_latest", "sugar_mean",
        "pain_latest", "pain_mean",
        "spo2_declining_consecutive", "pain_spike",
        "high_risk_count", "last_risk_score", "mean_risk_score", "surveys_completed",
        "active_med_count", "adherence_rate", "recent_missed",
    ]

    X = df[feature_cols]
    y = df["target_readmitted"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = XGBClassifier(
        n_estimators=80,
        max_depth=4,
        learning_rate=0.06,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="auc",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val)[:, 1]

    auc = float(roc_auc_score(y_val, y_prob))
    acc = float(accuracy_score(y_val, y_pred))
    f1 = float(f1_score(y_val, y_pred, zero_division=0))

    artifact_path = MODELS_DIR / "readmission_model.joblib"
    bundle = {
        "model": model,
        "features": feature_cols,
        "version": "xgb-readmit-1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, artifact_path)
    print(f"✓ Saved readmission_model.joblib (ROC-AUC: {auc:.3f}, Acc: {acc:.3f}, F1: {f1:.3f})")

    return {
        "artifact": "readmission_model.joblib",
        "version": "1.0.0",
        "algorithm": "XGBClassifier",
        "features": feature_cols,
        "metrics": {"roc_auc": round(auc, 4), "accuracy": round(acc, 4), "f1": round(f1, 4)},
        "checksum": calculate_file_hash(artifact_path),
    }


def train_anomaly_detector(df: pd.DataFrame) -> Dict[str, Any]:
    """Train Isolation Forest on vital trajectory metrics."""
    print("Training Vital Trajectory Anomaly Detector (Isolation Forest)...")
    feature_cols = [
        "fever_latest", "fever_mean", "fever_slope",
        "spo2_latest", "spo2_mean", "spo2_slope",
        "systolic_bp_latest", "diastolic_bp_latest",
        "sugar_latest", "sugar_mean",
        "pain_latest", "pain_mean",
    ]

    X = df[feature_cols]

    model = IsolationForest(
        n_estimators=100,
        contamination=0.10,
        random_state=42,
    )
    model.fit(X)

    artifact_path = MODELS_DIR / "anomaly_detector.joblib"
    bundle = {
        "model": model,
        "features": feature_cols,
        "version": "iforest-1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, artifact_path)
    print("✓ Saved anomaly_detector.joblib (Isolation Forest, contamination=0.10)")

    return {
        "artifact": "anomaly_detector.joblib",
        "version": "1.0.0",
        "algorithm": "IsolationForest",
        "features": feature_cols,
        "metrics": {"contamination": 0.10, "n_estimators": 100},
        "checksum": calculate_file_hash(artifact_path),
    }


def train_risk_classifier() -> Dict[str, Any]:
    """Train 3-class XGBoost Survey Risk Classifier."""
    print("Training Hybrid Survey Risk Classifier (3-Class XGBoost)...")
    df_surveys = generate_synthetic_survey_responses(n_samples=2000, seed=42)

    feature_cols = [
        "fever", "fever_present",
        "spo2", "spo2_present",
        "systolic_bp", "diastolic_bp", "bp_present",
        "sugar", "sugar_present",
        "pain", "pain_present",
        "photo_present", "voice_present", "custom_text_present",
    ]

    X = df_surveys[feature_cols]
    y = df_surveys["target_risk_class"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = XGBClassifier(
        n_estimators=70,
        max_depth=3,
        learning_rate=0.08,
        objective="multi:softprob",
        num_class=3,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_val)
    acc = float(accuracy_score(y_val, y_pred))
    f1_macro = float(f1_score(y_val, y_pred, average="macro"))

    artifact_path = MODELS_DIR / "risk_classifier.joblib"
    bundle = {
        "model": model,
        "features": feature_cols,
        "classes": ["low", "medium", "high"],
        "version": "xgb-risk-3class-1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, artifact_path)
    print(f"✓ Saved risk_classifier.joblib (Accuracy: {acc:.3f}, F1 macro: {f1_macro:.3f})")

    return {
        "artifact": "risk_classifier.joblib",
        "version": "1.0.0",
        "algorithm": "XGBClassifier(3-class)",
        "features": feature_cols,
        "metrics": {"accuracy": round(acc, 4), "f1_macro": round(f1_macro, 4)},
        "checksum": calculate_file_hash(artifact_path),
    }


def train_adherence_predictor(df: pd.DataFrame) -> Dict[str, Any]:
    """Train Logistic Regression for medication non-adherence prediction."""
    print("Training Medication Adherence Predictor (Logistic Regression)...")
    feature_cols = [
        "age", "days_since_discharge",
        "active_med_count", "total_med_count",
        "adherence_rate", "recent_missed",
        "last_risk_score",
        "diag_diabetes", "diag_cardiac", "diag_post_surgical", "diag_respiratory", "diag_orthopedic", "diag_general",
    ]

    X = df[feature_cols]
    y = df["target_miss_dose"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_val)
    y_prob = model.predict_proba(X_val)[:, 1]

    auc = float(roc_auc_score(y_val, y_prob))
    acc = float(accuracy_score(y_val, y_pred))
    f1 = float(f1_score(y_val, y_pred, zero_division=0))

    artifact_path = MODELS_DIR / "adherence_model.joblib"
    bundle = {
        "model": model,
        "features": feature_cols,
        "version": "logreg-adherence-1.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, artifact_path)
    print(f"✓ Saved adherence_model.joblib (ROC-AUC: {auc:.3f}, Acc: {acc:.3f}, F1: {f1:.3f})")

    return {
        "artifact": "adherence_model.joblib",
        "version": "1.0.0",
        "algorithm": "LogisticRegression",
        "features": feature_cols,
        "metrics": {"roc_auc": round(auc, 4), "accuracy": round(acc, 4), "f1": round(f1, 4)},
        "checksum": calculate_file_hash(artifact_path),
    }


def main():
    print("==================================================")
    print("Discharge+ Machine Learning Model Training")
    print("==================================================")

    print("Generating synthetic clinical cohort (1500 patient profiles)...")
    df_cohort = generate_synthetic_patients(n_samples=1500, seed=42)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frameworks": {
            "scikit_learn": "1.9.1",
            "xgboost": "3.4.1",
            "pandas": "3.1.1",
            "numpy": "2.5.5",
        },
        "models": {},
    }

    meta["models"]["survey_recommender"] = train_survey_recommender(df_cohort)
    meta["models"]["readmission_model"] = train_readmission_model(df_cohort)
    meta["models"]["anomaly_detector"] = train_anomaly_detector(df_cohort)
    meta["models"]["risk_classifier"] = train_risk_classifier()
    meta["models"]["adherence_predictor"] = train_adherence_predictor(df_cohort)

    metadata_path = MODELS_DIR / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✓ All artifacts successfully generated in {MODELS_DIR}")
    print(f"✓ Saved model manifest: {metadata_path}")


if __name__ == "__main__":
    main()
