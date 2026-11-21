"""
Discharge+ — Train Hybrid Survey Risk Classifier
Standalone training script for 3-class XGBoost survey risk classifier.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.training.train_all import train_risk_classifier

if __name__ == "__main__":
    result = train_risk_classifier()
    print("Done:", result)
