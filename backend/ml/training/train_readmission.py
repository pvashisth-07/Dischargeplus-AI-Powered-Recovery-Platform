"""
Discharge+ — Train Readmission Risk Model
Standalone training script for 30-day readmission prediction with XGBoost.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.synthetic_generator import generate_synthetic_patients
from ml.training.train_all import train_readmission_model

if __name__ == "__main__":
    print("Generating synthetic cohort for readmission model training...")
    df = generate_synthetic_patients(n_samples=1500, seed=42)
    result = train_readmission_model(df)
    print("Done:", result)
