"""
Discharge+ — Train Anomaly Detector
Standalone training script for Isolation Forest on longitudinal vital trajectories.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.synthetic_generator import generate_synthetic_patients
from ml.training.train_all import train_anomaly_detector

if __name__ == "__main__":
    print("Generating synthetic cohort for anomaly detector training...")
    df = generate_synthetic_patients(n_samples=1500, seed=42)
    result = train_anomaly_detector(df)
    print("Done:", result)
