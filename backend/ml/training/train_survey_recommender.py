"""
Discharge+ — Train Survey Recommender
Standalone training script for the Multi-label XGBoost Question Recommender.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.synthetic_generator import generate_synthetic_patients
from ml.training.train_all import train_survey_recommender

if __name__ == "__main__":
    print("Generating synthetic cohort for survey recommender training...")
    df = generate_synthetic_patients(n_samples=1500, seed=42)
    result = train_survey_recommender(df)
    print("Done:", result)
