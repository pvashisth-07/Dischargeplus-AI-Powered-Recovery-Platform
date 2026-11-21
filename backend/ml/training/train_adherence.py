"""
Discharge+ — Train Medication Adherence Predictor
Standalone training script for Logistic Regression adherence prediction.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.synthetic_generator import generate_synthetic_patients
from ml.training.train_all import train_adherence_predictor

if __name__ == "__main__":
    print("Generating synthetic cohort for adherence predictor training...")
    df = generate_synthetic_patients(n_samples=1500, seed=42)
    result = train_adherence_predictor(df)
    print("Done:", result)
