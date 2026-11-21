"""
Discharge+ — Continuous Learning & Scheduled Retraining
Evaluates whether new finalized survey responses in a hospital exceed
the retraining threshold, builds candidate datasets, and updates artifacts.
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dependencies import get_supabase_admin
from config import get_settings
from ml.training.train_all import main as retrain_all_models

settings = get_settings()
WATERMARK_FILE = Path(__file__).resolve().parent.parent / "models" / "retrain_watermark.json"


def check_and_trigger_retraining(min_new_responses: int = 50) -> dict:
    """
    Check if eligible new survey responses exceed threshold, and retrain if so.
    """
    print(f"[{datetime.now(timezone.utc).isoformat()}] Checking retraining triggers...")
    supabase = get_supabase_admin()

    last_count = 0
    if WATERMARK_FILE.exists():
        try:
            with open(WATERMARK_FILE, "r") as f:
                last_count = json.load(f).get("last_processed_count", 0)
        except Exception:
            pass

    # Query current count of finalized risk scores
    try:
        res = supabase.table("risk_scores").select("id", count="exact").execute()
        current_count = res.count or 0
    except Exception as e:
        print(f"⚠️ Could not query risk_scores count: {e}")
        current_count = 0

    new_responses = current_count - last_count
    print(f"Current risk scores: {current_count}, Last processed: {last_count}, New: {new_responses}")

    if new_responses >= min_new_responses:
        print(f"✓ New records ({new_responses}) >= threshold ({min_new_responses}). Triggering retraining...")
        retrain_all_models()
        with open(WATERMARK_FILE, "w") as f:
            json.dump({
                "last_processed_count": current_count,
                "retrained_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        return {
            "status": "retrained",
            "new_samples": new_responses,
            "total_samples": current_count,
        }
    else:
        print(f"ℹ️ New records ({new_responses}) below threshold ({min_new_responses}). Retraining skipped.")
        return {
            "status": "skipped",
            "new_samples": new_responses,
            "threshold": min_new_responses,
        }


if __name__ == "__main__":
    check_and_trigger_retraining(min_new_responses=10)
