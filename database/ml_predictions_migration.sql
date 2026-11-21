-- ============================================================
-- Discharge+ — ML Predictions Audit Table Migration (Phase 4B)
-- ============================================================

CREATE TABLE IF NOT EXISTS ml_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID REFERENCES hospitals(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    model_version TEXT,
    input_features JSONB,
    prediction JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for tenant and patient lookups
CREATE INDEX IF NOT EXISTS idx_ml_predictions_hospital ON ml_predictions(hospital_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_patient ON ml_predictions(patient_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_model ON ml_predictions(model_name);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_created ON ml_predictions(created_at);

-- RLS Policy: Only hospital staff can read predictions
ALTER TABLE ml_predictions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Hospital staff view their hospital's ML predictions"
    ON ml_predictions FOR SELECT
    USING (hospital_id = (SELECT hospital_id FROM users WHERE id = auth.uid()));
