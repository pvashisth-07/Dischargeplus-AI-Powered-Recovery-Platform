# Discharge+ machine learning implementation plan

**Inputs** · `ml_integration_plan.pdf`, pp. 1–8, and [Discharge+ repository at commit 2748b2d](https://github.com/pvashisth-07/Dischargeplus-AI-Powered-Recovery-Platform/tree/2748b2d528641c28e12a6677a1d83989ca6aea53). Paths are relative to the repository root. The schedule follows the PDF’s three implementation weeks and ongoing learning phase. Each subphase is a separate implementation task with its own merge gate.

## Target behavior

The current app builds surveys manually, shows raw vital charts and a survey risk badge in Patient Detail, and calls Groq to score every patient survey submission. Implement five scikit-learn/XGBoost capabilities, corresponding to roughly five of the estimated twenty intelligent product features in the original plan. The 25% figure is a scope estimate.

| Capability | Current behavior | Target behavior |
|---|---|---|
| Disease-aware survey recommendations | Doctor selects question types manually | Disease rules at cold start, then a multi-label model ranks the eight existing types. The doctor can edit every selection. |
| 30-day readmission risk | Patient Detail shows a survey risk badge | A separate XGBoost probability with the three strongest SHAP contributors when eligible. |
| Vital trajectory anomalies | Doctor interprets trend charts | Isolation Forest on patient-baseline trajectory features, with observable trend alerts and a cohort comparison when supported. |
| Survey submission risk | Groq determines risk level and score | XGBoost scores the survey. Groq explains the structured result and drafts patient feedback. |
| Medication adherence | Patient logs taken or missed doses | Logistic regression predicts likelihood of missing the next scheduled dose within 48 hours. The patient sees a reminder and the doctor sees an adherence badge or alert. |

Groq also writes short survey recommendation reasons and the doctor’s insight narrative. Report parameter extraction stays on the existing Groq route. A future NER model remains an option outside this delivery. The survey risk score, the 30-day readmission probability, and medication nonadherence probability are different outputs and should have distinct names in the API and UI.

## How to execute this plan

1. Give the coding agent one subphase at a time. Include the shared contracts below and the preceding subphase’s evidence. Keep each change reviewable and merge it behind its feature flag where applicable.
2. At the end of each subphase, record changed files, checks run, exercised fallbacks, benchmark results where relevant, and blockers. Fix regressions in the current subphase before starting dependent work. Continue independent work when a data or approval gate blocks a single feature.
3. Keep synthetic artifacts and seeded demo data in a separate demo profile or environment. Keep production predictions disabled until the corresponding data, performance, and clinical review gates pass. Use an authorized staging tenant and test accounts for integration runs.
4. Reuse the existing FastAPI auth dependencies, Axios client, React flows, and Supabase data. Avoid new infrastructure for the first release. Introduce a queue, shared cache, or database index only when a measured limit or durability requirement calls for it.

## Runtime, data, and API contracts

### Integration points

- `backend/main.py` mounts `backend/routers/ml.py` at `/ml`. Its endpoints authorize the caller and pass a bounded data snapshot into `backend/ml/feature_engineering.py`. Inference modules consume that snapshot and load versioned artifacts from `backend/ml/models/`.
- `frontend/src/pages/Doctor/SendSurvey.jsx` and `frontend/src/pages/Doctor/PatientDetail.jsx` call the doctor endpoints through `frontend/src/lib/api.js`. Their existing data, chart, and form requests remain usable while ML loads.
- `frontend/src/pages/Patient/Survey.jsx` submits to `POST /surveys/{survey_id}/respond` in `backend/routers/survey.py`. This calls `backend/services/risk_service.py`, which sends a feature vector to `backend/ml/risk_classifier.py` and a structured result to `backend/services/ai_service.py` for narrative text.
- `backend/ml/adherence_predictor.py` serves the patient dashboard and supplies a batched prediction summary to the doctor dashboard. Supabase reads and writes stay in the backend. Training scripts and external datasets stay outside the request path.

### API and authorization

| Endpoint | Caller and contract |
|---|---|
| `GET /ml/health` | Return lightweight ML readiness with per-module status and safe model versions. Exclude tenant, patient, artifact path, and internal error details. Existing app health remains independent of model readiness. |
| `GET /ml/survey-recommendations?patient_id=...` | Assigned doctor. Return eight known types in ranked order where supported, with per-type probability or null, selected flag, reason, mode (`model`, `rules`, `disabled`, or `unavailable`), and model or rules version. Unsupported or unobserved labels may have null probabilities. |
| `GET /ml/patient-insights/{patient_id}` | Assigned doctor. Return separate readmission, anomaly, and cohort sections with per-section status, as-of time and relevant version. Optional summary accompanies structured results. Missing probabilities and missing history are represented explicitly. |
| Proposed `GET /ml/adherence/me` | Patient self only. Resolve patient ID from the authenticated user. Return next-dose time when known, horizon, probability or null, nudge eligibility, status and version. Doctor list receives an optional summary through its existing response, populated in bulk. |
| Existing `POST /surveys/{survey_id}/respond` | Patient owner in the same hospital. Keep `response_id`, `risk_score`, `ai_feedback`, and `message` compatible. If the rollout needs a pending-risk state, update the frontend and all readers before shipping it. Keep sufficient feedback for existing clients. |

Use `require_role` and the resolved user’s `hospital_id`. A service-role Supabase client bypasses RLS, so validate doctor identity, active assignment, patient ownership where applicable, and hospital membership before inference, cached results, and audit writes. Apply tenant filters throughout each query and join. Derive tenant on the server and validate UUIDs. Use deliberate 401/403/404 behavior consistent with existing callers and avoid disclosing cross-tenant record existence. A disabled model or insufficient data produces a typed feature status. Reserve request errors for invalid input, denied access, or genuine service errors. Never turn missing data into low risk, zero probabilities, or fake model confidence.

### Feature definitions

Implement the same deterministic transforms for offline training and online inference. A snapshot takes `hospital_id`, `patient_id`, and an explicit UTC prediction cutoff. Document the artifact input order, types, units, categorical vocabulary, invalid ranges, missing-value flags, and schema version. Use only data available by the cutoff. Historical rows introduced or updated after the cutoff need versioned source data or should be omitted from training.

| Source | Features and handling |
|---|---|
| `patients` | Diagnosis category mapping for the first baseline, with TF-IDF as an evaluated option. Normalize comorbidities into multi-hot features. Use days since discharge and expected recovery days. Derive age from date of birth at the cutoff and evaluate available demographics for readmission. Exclude identifying data and outcome fields from feature vectors. |
| `survey_responses`, `response_answers`, `surveys` | Use `submitted_at` to anchor response order. Start with a configurable last 20 responses and evaluate a smaller rolling N within that bound. Compute vital mean, elapsed-time slope and unit-specific variance over valid observations, plus count, recency, and missingness. Keep one observation per vital per survey according to an explicit duplicate rule. |
| Answer encoding | Temperature in °F, SpO₂ in percent, glucose in mg/dL, pain on its existing numeric scale. BP systolic is `answer_numeric`, while the existing UI stores diastolic in `answer_value`. Accept historical nulls and malformed values as missing. Preserve valid zero values at serialization where the domain permits them, such as pain. Use presence flags for media or free text unless a reviewed structured observation is available. |
| `risk_scores` | Use historical finalized level, score, and trend where relevant. Exclude the current result from its own feature vector, trigger-created pending rows, and future information. Track label provenance for legacy Groq scores, reviewed rule labels, and later predictions. |
| `medications`, `medication_logs` | Use a bounded 14-day lookback for logged taken/missed pattern, adherence rate, medication count, and frequency complexity. Derive scheduled slots only from interpretable schedules, using explicit time zone and coverage rules. Window by dose/log timestamps and use schedule metadata known at the cutoff. |
| Readmission outcomes | The checked-in schema contains `patients.is_readmitted`, `admission_date`, and `discharge_date`, with no verified dated readmission label or follow-up coverage. Obtain an authorized outcome feed anchored to index discharge, including dated events and coverage, before real-tenant calibration or rollout. Treat incomplete follow-up and ambiguous discharge episodes explicitly. |

### Performance and failure budgets

The following are starting engineering budgets for staging. Record actual deployment hardware, data volume, and concurrency in Phase 0, then adjust numerical targets against measured baselines and record the reason. Run warm and cold tests separately. Suggested load samples are 1, 10 and 25 concurrent requests with representative history lengths and doctor-list sizes.

| Measure | Initial check |
|---|---|
| Warm local feature-vector transform plus inference | p95 ≤ 50 ms per patient for ordinary windows. Benchmark SHAP separately and bound its input size. |
| Doctor ML GETs, structured result | p95 ≤ 500 ms in staging, including auth and Supabase. Record the cold start and test model-unavailable mode. Validate that a slow narrative cannot hold the card beyond the structured response budget. |
| Hybrid survey submit | Compare end-to-end p50/p95 and error rate with the legacy route on the same cases, including DB write, alert, and feedback. Target p95 at or below the measured legacy baseline with Groq available. Verify timeouts and failure scenarios separately. |
| Doctor list and dashboards | Confirm roughly constant query count across page sizes and no per-patient network or Groq request. Compare p95 to baseline and investigate regressions over 10% under matched load. |
| Process resources | Record artifact size, cold load time, memory per worker, and concurrency headroom inside the deployment container before choosing worker count. |

Load verified joblib artifacts once per serving worker, cache bounded explainers where useful, warm only enabled versions, and cap numerical library threads to avoid CPU oversubscription. A missing, corrupt, or incompatible artifact yields a typed degraded state. Run synchronous Supabase, model, and Groq work in a bounded execution path so async routes can continue servicing other requests. Filter projected columns and limit lookbacks in the database. Batch related reads and answer inserts. Profile before adding composite indexes such as `(hospital_id, patient_id, submitted_at)`. Keep HTML/JS bundles free of training artifacts and ML libraries.

Narratives are optional enrichment. Batch all question reasons into at most one Groq call and use a short deadline, validated output, and deterministic reason text as fallback. Return structured predictions promptly and use cached or independently fetched enrichment where needed. Cache by tenant, entity, model version, source-data watermark, and locale after authorization. Bound cache size and invalidate on data change or promotion. On submit, aim for one bounded narrative call for reasoning and feedback combined. Emit aggregate timings for data fetch, feature build, inference, SHAP, narrative and persistence, along with fallback rates, request IDs and model versions. Use approved telemetry and avoid patient payloads in logs.

## Phase 0 · Baseline and release decisions

1. Confirm HEAD and compare the paths and field names above with the branch being implemented. Read `backend/main.py`, `dependencies.py`, relevant routers and schemas, `risk_service.py`, `ai_service.py`, and the five affected React screens. Review `database/schema.sql` and how migrations are applied in the target Supabase environment.
2. In an isolated staging database, seed two hospitals, two assigned doctors, an unassigned doctor, and patients with complete, sparse and missing histories. Capture successful and failure paths for survey creation, submission, feedback, the risk row and high-risk notification, charts/notes, medication logging, the doctor list, and report extraction. Keep sanitized fixtures and a baseline latency/query report. The repository uses a Python 3.11 backend Dockerfile and a Vite frontend. Run the backend entry point from `backend/` and run `npm ci && npm run build` from `frontend/`.
3. Confirm the policy for risk labels and alert thresholds with the clinical owner. Record the intended users, outcome definitions, minimum usable sample sizes and supported cohorts, handling of missing data, activation criteria, and approved Groq data fields. Agree on feature flags for recommendations, readmission, anomaly, hybrid risk and adherence with prospective live defaults off. Keep the demo profile explicit.
4. Check how existing survey completion and recurring behavior work before choosing an idempotency key. The current submit handler inserts the survey response, writes answers individually, updates completion, and calls risk synchronously. A DB trigger inserts a pending placeholder with level `low`. Capture tests for this exact flow before refactoring.

**Exit gate** · Baseline fixtures and measurements exist, the API paths and data gaps are recorded, and validation criteria are assigned to owners. Clinical data gaps can remain open for an isolated demo.

## Phase 1 · Foundation (week 1)

### 1A · Package, dependencies and feature flags

1. Create `backend/ml/` with `__init__.py`, `feature_engineering.py`, `training/` and `models/`. Add config through `backend/config.py` and the existing environment documentation. Provide a deterministic demo mode and separate module flags. Register the ML router and schema-validated stubs for health, recommendations and insights.
2. Add the PDF dependency minimums in `backend/requirements.txt`: `scikit-learn>=1.4.0`, `xgboost>=2.0.0`, `pandas>=2.2.0`, `numpy>=1.26.0`, `joblib>=1.3.0`, `shap>=0.45.0`. Lock a tested compatible resolution for training and serving, and record the Python/package versions in metadata. Rebuild the Python 3.11 slim image and test actual imports and XGBoost/SHAP inference on the target architecture. Add a native runtime dependency only if the image requires it. Install notebook tooling in the training environment.
3. Use a simple artifact loader for approved local artifacts. Check manifest, feature-schema compatibility and checksum before deserializing trusted joblib files. Ship the verified artifact through the backend build or release process. Keep patient data and source extracts out of Git and container layers.

**Exit gate** · App and Docker image start with flags off and artifacts absent. Existing routes work, authenticated stub requests return stable contracts, unauthorized or cross-tenant requests fail, and ML health reports missing artifacts without disabling the base app.

### 1B · Snapshot queries and feature parity

1. Use the doctor detail handler as a reference for patient, survey and risk history. It reads 20 recent response/risk rows and active medications. Read `medication_logs` directly for adherence features. Share data access at the query/service level where practical. Avoid calling the doctor HTTP route internally or copying its response’s names and contact data into ML.
2. Implement the feature table above as pure transforms over tenant-scoped snapshots. Fix feature column ordering and categorical preprocessing at fit time. Keep raw values and timestamps available internally for trend evidence, while keeping PII, media URLs, text notes and prompt data out of feature telemetry.
3. Test historical schemas and both BP fields, legitimate zero pain, null date/comorbidities, missing or duplicate observations, out-of-order timestamps, stale data, one-point windows, and post-cutoff events. Verify exact feature output parity for the same fixture through training and online code.

**Exit gate** · Shared fixture vectors match, including null and sparse cases. Verify bounded query counts and time filters with a two-hospital test fixture.

### 1C · Seed data, training entry points and manifests

1. Implement a seeded synthetic generator covering all eight question types, diagnosis cohorts, chronological vitals, risk tiers, a dated readmission outcome and follow-up window, and explicit adherence trajectories. Create separate threshold-rule labels for hybrid risk. Use synthetic data to test dataset builders, validation and inference wiring.
2. Add callable training entry points for survey recommendations and readmission, plus dedicated commands or subcommands for anomaly, hybrid risk, and adherence. Each accepts dataset location, seed, output directory and configuration. Each uses the shared feature transforms and saves a versioned artifact and manifest. Add artifact smoke tests in a fresh serving process.
3. Establish `backend/ml/models/metadata.json` for artifact names and versions, checksums, feature-schema versions, dependency versions, training date, data source and scope, sample counts, split definition, thresholds, metrics, and demo/live eligibility. Keep metrics per module and preserve prior manifests when promoting a release.

**Exit gate** · A clean environment can generate demo fixtures, fit smoke models, reload each artifact, and produce finite typed outputs without Supabase or Groq credentials. Tiny synthetic runs are evidence of wiring only.

## Phase 2 · Doctor-facing ML (week 2)

### 2A · Disease rules and the Send Survey panel

1. Add `backend/ml/survey_recommender.py` with a versioned rule baseline. Preserve the PDF examples as reviewable seeds: diabetes → sugar and BP, cardiac → BP and SpO₂, and post-surgical → pain, photo, and fever. Normalize diagnosis/categories and comorbidities. Define how overlapping rules combine and how an unknown diagnosis returns generic reviewed suggestions or preserves manual selection. Include days post-discharge, expected recovery, and prior survey history in the feature contract for the learned version.
2. Activate the recommendation endpoint in rules mode. Return allowlisted IDs `fever`, `spo2`, `bp`, `sugar`, `pain`, `photo`, `voice`, `custom_text`. Rule reasons may cite diagnosis categories and reviewed mappings. Rules use null model probabilities.
3. In `SendSurvey.jsx`, show **AI Suggested Questions** on selecting an eligible patient. Preselect suggestions in the existing `selectedTypes` form state and attach one concise reason per type. Route all toggles through that same state. Cancel or ignore stale fetches on patient switches and ensure delayed responses cannot overwrite edits the doctor already made. Give the doctor a way to reapply suggestions. Keep the existing preview, creation payload, scheduling and manual picker usable during error or loading.
4. Give `ai_service.py` a helper that writes per-type reasons in one bounded request from structured recommendation evidence. Keep reasons tied to the allowed question types and use deterministic wording on timeout or malformed output.

**Exit gate** · A selected demo diabetic patient gets sugar and BP even with Groq off. Tests cover profile swaps, unassigned doctors, unknown diagnosis, overlap, manual overrides, and normal survey creation.

### 2B · Train, compare and package the multi-label recommender

1. Add `backend/ml/training/train_survey_recommender.py`. Build eight independent binary tasks with one XGBoost model per eligible label, optionally wrapped with `MultiOutputClassifier`. Use RandomForest as an offline comparison if useful. Preserve label order and store per-type probabilities, ranks and selection thresholds in the contract. Handle labels with no usable positives or negatives through rules or explicit unavailable probabilities.
2. Create a dataset mapping for the [MIMIC-III demo subset](https://physionet.org/content/mimiciii-demo/1.4/) and the [UCI Diabetes 130-US Hospitals dataset](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008). For each dataset, map available diagnoses and measurements to the eight question types, declare proxies and missing labels, and record authorization, units and coverage. Public inpatient records lack the app’s doctor selections and survey responses. Treat proxy labels as training experiments or demo support, with photo, voice or custom text left unobserved wherever the data cannot support them.
3. For hospital training, join `surveys`, `response_answers`, and completed `risk_scores` by response, patient, and hospital. Measure which observed question types surfaced a concerning finding or were associated with high risk for similar patients. Use observed opportunity masks. An unasked type has an unknown outcome, and historical doctor selection or a Groq score can bias estimated usefulness. Separate clinician-reviewed labels and alert on shifts in coverage or class balance. Include recommendation overrides in evaluation where reliably captured. Keep any future outcomes out of ranking features at prediction time.
4. Compare learned ranking to the rules baseline on patient-disjoint held-out data. Publish support per label, precision/recall at the displayed cut, F1, ranking quality and coverage. Export `backend/ml/models/survey_recommender.joblib`. Enable the model mode in demo or staging first. Fall back to rules for unknown categories, unsupported labels, insufficient confidence, or artifact failure.

**Exit gate** · Artifact emits the same ordered schema as the rules endpoint. Low-support labels degrade cleanly. Enable learned ranking for a real tenant only after it improves the agreed baseline on relevant cases without eroding coverage of clinically important question types.

### 2C · Readmission risk and SHAP

1. Add `backend/ml/readmission_model.py` and `backend/ml/training/train_readmission.py`. Define outcome as a verified readmission within 30 days of an index discharge. Choose prediction cutoffs within the follow-up window and include only patients eligible and event-free at the cutoff. Use positives with a verified in-window event and negatives with verified coverage through day 30. Censor incomplete or ambiguous episodes. Document local readmission scope, planned readmission treatment, and outcome ascertainment with the clinical owner.
2. Fit and evaluate binary XGBoost on vital trajectory features plus available demographics, diagnosis, comorbidities, recovery window, prior finalized risk trends and medication adherence where supported. Compare to a simple baseline. Put any probability calibrator in the artifact bundle. Public data can exercise compatible pipelines. Evaluate the post-discharge feature set on representative post-discharge outcomes. The existing boolean is insufficient for a live model trained on this target.
3. Compute top three SHAP contributors by absolute contribution for eligible predictions. Return human-readable feature labels, direction and value/units where appropriate. Group one-hot columns when they represent the same underlying feature. Keep contributions in a declared model-output space and do not equate them with changes in calibrated probability or medical causes. Reuse one explainer per loaded model/version and allow the probability to render when explanation is unavailable.
4. Wire the readmission section of `GET /ml/patient-insights/{patient_id}`. Return a 0–100% UI display for a valid probability, with the prediction timestamp, horizon and status. In real tenant mode, show a clearly marked unavailable state when the outcome feed, evidence or history is insufficient.

**Exit gate** · Known fixture predictions and contributor order survive fresh-process load. Held-out metrics, calibration and sample support are documented. The synthetic prospective demo works. Real-tenant exposure stays gated until dated outcomes, independent testing, representative subgroup checks and clinical sign-off are in place.

### 2D · Patient-baseline anomalies, cohort comparison and Patient Detail

1. Add `backend/ml/anomaly_detector.py`. Train Isolation Forest offline on trajectory features expressed relative to earlier patient baselines. At serving time, compare the latest observation/window with earlier observations from that patient using the same transform. Exclude the latest observation from its own baseline. Define minimum valid points and span per vital, handling irregular cadence, stale history and sparse measurements. Keep fit and retraining out of request handlers.
2. Return a structured anomaly flag, evidence, point count and recency. Generate separately auditable trend statements from actual values, such as “SpO₂ declining 3 surveys in a row” after three strictly descending comparable observations, or “Pain score spike detected” when the reviewed change rule fires. Distinguish anomaly flags and trend rules in the result. Check these against normal, declining, spike, sparse and noisy series. Evaluate Isolation Forest with known injected anomalies and reviewed cases, including false-alert rates.
3. Define and version the diagnosis cohort, discharge window, severity statistic, reference period and minimum cohort sample size. Precompute tenant-scoped reference quantiles offline, excluding the target patient from benchmark construction for the evaluated case where feasible. Render comparisons only when supported, such as the PDF’s top 10% fever severity example for post-appendectomy patients. Keep prevalence or denominators visible where needed for interpretation. Avoid exposing small cohorts or mixing hospitals without explicit authorization.
4. Extend `GET /ml/patient-insights/{patient_id}` to return all three sections independently. Ask Groq for a short doctor-friendly **Clinical Insights** narrative from the structured facts only. Require it to preserve direction, uncertainty and observed evidence. Render deterministic text if Groq is slow or fails.
5. Add the **ML Insights** card above the charts in `PatientDetail.jsx` with readmission probability, three contributors when available, anomaly/trend evidence, cohort percentile, and summary. Fetch it independently of detail and notes. Preserve current notes, medication actions, charts, and the survey risk badge.

**Exit gate** · Each insight can degrade independently. The seeded declining SpO₂ fixture appears in the card. Verify Groq-off mode, low cohort support, unavailable readmission and missing vitals. Compare latency, query count, and render behavior to the baseline.

## Phase 3 · Hybrid survey risk, medication adherence and evaluation (week 3)

### 3A · Train and shadow the survey risk classifier

1. Add `backend/ml/risk_classifier.py` and its offline training entry point. Fit a three-class XGBoost classifier for `low`, `medium`, and `high` using normalized submitted answers, measurement presence, and reviewed structured factors. Include only prior history available at submission if testing shows it improves performance. Keep the model score on the existing 0–100 scale. Define and evaluate a deterministic mapping from class probabilities to a score within the existing bands (0–30, 31–70, 71–100) and a structured factors schema.
2. Use finalized legacy production `risk_scores` as weak labels and bootstrap with a deterministic implementation of the threshold rules already in `SURVEY_SCORING_PROMPT`. Review its fever, SpO₂, systolic and diastolic BP, glucose, pain, wound criteria, the any-concerning floor, and the critical or multiple-concerning escalation. Write edge-case fixtures for all comparisons, overlapping findings and missing measurements. Interpret wound criteria only with a reviewed structured signal. Carry label source and rule version per example. Keep reviewer-labeled holdout data separate and exclude trigger placeholders, failed default scores, and fresh model predictions as ground truth.
3. Compare classifier, threshold baseline, and legacy Groq scoring on the same frozen cases. Track high-risk recall, dangerous downgrades, class calibration and score-band consistency. Evaluate a reviewed deterministic escalation floor and missing-input behavior before activation. Shadow predictions with no patient feedback, risk updates, or notifications from the shadow model.

**Exit gate** · Shadow scores are reproducible and contract-valid. The reviewed high-risk recall and missed-escalation criteria pass on independent data. Publish comparison, label provenance, and feature/version metadata.

### 3B · Switch risk service behind a flag and harden writes

1. Refactor `backend/services/risk_service.py` so feature construction and XGBoost determine tier, score and factors. Start with a deterministic reasoning message. Persist the validated numeric and structured result independently of Groq. Then generate plain-language reasoning and patient feedback via `ai_service.generate_patient_feedback()` and a text-only helper or shared call that preserves existing callers. Ignore any model-generated score, tier, factors, or unsupported clinical assertions. Preserve the report extraction pathway.
2. On `POST /surveys/{survey_id}/respond`, validate question IDs, payload and ownership before writes, normalize valid zero values, and batch inserts. For the rollout, make response/answer/completion/core-risk persistence a retry-safe unit. If separate Supabase requests cannot meet the atomicity gate, use a small reviewed database transaction/RPC with scoped privileges. Reuse a stored response under a per-occurrence submission key and verify payload agreement on replay. Preserve recurring surveys and answer history.
3. Ensure every activated submission reaches a valid finalized score or an explicit pending/review state. Fix read paths that currently display the trigger placeholder as low. For missing artifacts or inference errors, use the approved deterministic classifier fallback or a visible review state. Keep the historical flag-off path available for operational rollback with approved handling of any legacy default-low fallback. Never silently downgrade known concerning data during failure.
4. Preserve in-app high-risk alerts to active assigned doctors. Scope the lookup by hospital and make notifications idempotent by response and recipient. If notification retry is needed outside the core transaction, make pending delivery durable and retryable with the same key. Groq failure must still return a stable feedback message and leave the score and alert correct. Fault-inject at each write boundary, including service restart between score and alert.
5. Update `Survey.jsx` only as needed for canonical numeric serialization, compatibility and any explicit pending display. Keep existing survey completion and feedback UX. Bound the narrative deadline and measure end-to-end time and Groq request/cost reduction against baseline.

**Exit gate** · Replaying or racing the same submission creates one response, one finalized risk record and one alert per recipient. Authorization, high-risk routing and partial failures pass with Groq off, an invalid ML artifact, and stale/legacy data. Staging meets the regression and latency budgets before any canary.

### 3C · Medication adherence and alerts

1. Add `backend/ml/adherence_predictor.py` and fit logistic regression first. Compare XGBoost only as an offline candidate if the baseline misses agreed quality targets. Use 14 days of logged patterns, recent misses, adherence rate, number of meds, frequency complexity, patient age and diagnosis. Predict `P(next scheduled dose is missed | the next dose is due within 48 hours)` at a fixed cutoff. Cases without an eligible known dose return unavailable or no upcoming dose.
2. Use existing `medications` and `medication_logs`, with no schema change for the initial predictor. Current logs have `taken_at` and an explicit status, with no dose slot identifier. Match logs to supported schedules and discard ambiguous matches, duplicates and incomplete future windows. Define whether silence is unknown using measured coverage and clinician review. Keep the historical schedule and timezone assumptions explicit. Return insufficient data when the schedule cannot be interpreted.
3. In `frontend/src/pages/Patient/Dashboard.jsx`, add the optional adherence summary, a streak when supported by observed coverage, and the contextual next-dose reminder. Use “You're at risk of missing tonight's dose” only when the actual local next dose is tonight and the threshold is met. Preserve dashboard rendering if the new endpoint fails. Avoid making dose or regimen changes from the prediction.
4. In `frontend/src/pages/Doctor/Dashboard.jsx`, add the low predicted adherence badge. Use a batched snapshot with scoped reads and vectorized inference for assigned patients. Surface important predictions through the existing doctor alerts UI under the reviewed threshold policy. Deduplicate persisted alerts by tenant, patient, dose window and recipient as applicable. Keep adherence alerts and survey risk badges separate.
5. Evaluate precision, recall, PR-AUC, calibration, false reminders per patient, and prediction coverage against simple history and prevalence baselines. Validate clock boundaries, changing prescriptions, historical logs, no log, no upcoming dose, and no schedule.

**Exit gate** · The test patient gets the expected nudge and the assigned doctor gets the expected badge/alert when eligible. Dosage logging still works. The doctor list avoids per-patient requests and passes the dashboard performance gate.

### 3D · Evaluation notebook, demo and rollout rehearsal

1. Create `backend/ml/training/evaluation.ipynb`. Run it top-to-bottom with versioned fixtures and reproducible seeds. Include dataset sources, license/access constraints, feature schema, missingness, label definitions and support, and exact train/validation/test methodology. Keep patients disjoint, honor temporal cutoffs, and use hospital holdouts where sample size permits. Fit encoders, imputers and thresholds on training/validation data and use the held-out set once for release comparisons.
2. Add a per-model metrics table with accuracy, precision, recall, F1, confusion matrix, ROC/PR AUC and MAE wherever appropriate. Use MAE for eligible numeric targets, such as risk scores with a defensible numeric reference. Report unavailable metrics with a reason for unlabeled anomalies, unsupported classes or purely ranked outputs. Include calibration and subgroup/tenant slices with sample support, relevant confidence intervals, SHAP global feature-importance plots and local contributor examples. Keep demo metrics clearly labeled and independent from real clinical evidence.
3. Compare LLM-only and hybrid risk on identical de-identified/synthetic sample cases. Present classification and latency results, disagreement review, Groq call count and cost. Use captured approved outputs or a bounded optional Groq run. Never manufacture missing baseline metrics.
4. Rehearse the required live demo in a controlled demo tenant: doctor selects a diabetic patient → ML suggests sugar and BP → doctor sends survey → patient submits → XGBoost scores the survey → doctor opens Patient Detail and sees the seeded trajectory anomaly. Seed enough earlier observations to support the anomaly and show mock readmission, cohort and adherence where useful. Keep a readiness checklist for model artifacts, credentials and flags. Rehearse with Groq unavailable so deterministic explanations still carry the demo.
5. Demonstrate feature-off, shadow, internal staging/canary and broader activation with the same frontend and API contracts. Gate each module independently on data validity, clinical workflow review, performance and fallbacks. Roll back by disabling its feature flag or atomically restoring the last compatible artifact manifest. Verify rollback on a staging deployment first. Preserve submitted responses and notifications during rollback.

**Exit gate** · Notebook runs from a clean training environment and saves reproducible outputs. All applicable package, API, auth, fallback, build and performance checks pass. The demo and rollback have been exercised. Review real-tenant gates before activation.

## Phase 4 · Continuous learning, monitoring and optional audit (ongoing)

### 4A · Schedule and promote tenant-aware retraining

1. Use an external cron or scheduled job to evaluate retraining monthly and after the number of new eligible finalized `risk_scores` in a hospital exceeds a configurable threshold. Persist the processed data/label watermark and record skipped runs. Check usable samples, label support, coverage and outcome maturation per model independently. A risk score threshold can trigger a candidate run, and each candidate must still satisfy its own label requirements.
2. Build candidate datasets with `hospital_id` isolation, joining authorized `surveys`, `risk_scores`, and `response_answers`, plus adherence logs and dated outcomes as appropriate. Support per-hospital artifacts where there is enough evidence. Allow a shared model only where the approved training scope permits and local validation passes. Otherwise use module-specific rules or unavailable states. Lock overlapping runs per model and tenant.
3. Reuse training scripts and notebook evaluation code with deterministic splits, candidate manifests and side-by-side baseline comparisons. Monitor model versions, input/label drift, per-tenant coverage, fallbacks, latency, subgroup behavior and reviewed alerts. Use fixed independent holdouts and human-reviewed outcomes to prevent self-reinforcing labels.
4. Register candidates outside the serving directory, verify checksum and schema, then promote using an atomic manifest/version switch after approval. A failed retrain leaves the active artifact available. Warm and validate the candidate in staging, canary if eligible, then keep the prior compatible version for rollback. Record who approved activation, artifact lineage and the outcome.

**Exit gate** · Run dry and real staging jobs for two hospitals, below/above threshold, overlapping runs, incompatible artifacts, failed metrics and successful rollback. Confirm no tenant’s artifacts or data appear in another tenant’s path.

### 4B · Optional inference audit migration

The PDF proposes a single `ml_predictions` table to store every inference for audit, explainability and retraining. This is an optional, separately reviewed migration. The core features and adherence predictor can ship without it.

```sql
CREATE TABLE ml_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID REFERENCES hospitals(id),
    patient_id UUID REFERENCES patients(id),
    model_name TEXT NOT NULL,
    model_version TEXT,
    input_features JSONB,
    prediction JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

1. Confirm data retention and access policy, then implement the migration through the project’s Supabase workflow. Enforce scoped access and hospital/patient consistency, with RLS and backend-only writes where applicable. Require tenant and patient IDs for patient predictions. Keep only approved feature snapshots or references and approved structured output. Exclude free text, names, raw medical reports, media URLs and Groq prompts. Add indexes only for actual lookup and retention queries.
2. Associate each computed inference with model version and source cutoff. Distinguish completed inferences from cache hits and failed attempts. Design a deduplication key and decide whether approved writes require durable queuing. Benchmark any write and test retries, cleanup, and audit unavailability. Keep observed outcomes in a separate verified source and use audit predictions as inputs to later analysis.
3. Test RLS, access through service routes, cross-tenant isolation, retention, rollback, and audit-off operation.

**Exit gate** · Approved audit storage and deletion policies work in staging. Existing endpoints, core scoring and rollback pass with audit enabled and disabled.

## Original plan coverage

| PDF requirement | Implementation location |
|---|---|
| Current gaps, five-module architecture, ~25% target, and Groq/ML responsibilities | Target behavior and runtime contracts. |
| Disease-aware inputs, eight recommendations, confidence and doctor reasons | Feature definitions and Phases 2A–2B. |
| Cold start A disease rules, B public datasets, C monthly tenant data | Phases 2A, 2B and 4A. |
| Recommender endpoint, Send Survey panel, training script and joblib artifact | API contracts and Phases 2A–2B. |
| Doctor history, rolling vitals, risk and adherence features | Phase 1B and feature definitions. |
| XGBoost readmission, top three SHAP contributors, Isolation Forest, trend and cohort alerts, Groq summary | Phases 2C–2D. |
| Patient Insights endpoint and ML card above charts | API contracts and Phase 2D. |
| Historical and threshold bootstrap labels, XGBoost survey risk, Groq reasoning and feedback | Phases 3A–3B. |
| 14-day adherence features, 48-hour prediction, dashboard streak/nudge and doctor badges or alerts using existing logs | Phase 3C. |
| Six dependencies, ML package/router, seeded training and health stubs | Phases 1A–1C. |
| Model metadata, metrics, notebook, SHAP plots, LLM comparison and diabetic patient demo | Phases 1C and 3D. |
| Threshold-triggered scheduled retraining, per-hospital models and the optional audit table | Phases 4A–4B. |
| Report parameter extraction stays on Groq, with NER as a possible future project | Target behavior and Phase 3B. |

## Reference material

- The attached `ml_integration_plan.pdf` is the source for feature scope, the original sequence, algorithms, examples and optional SQL.
- Repository baseline and integration points. [GitHub snapshot](https://github.com/pvashisth-07/Dischargeplus-AI-Powered-Recovery-Platform/tree/2748b2d528641c28e12a6677a1d83989ca6aea53)
- Dataset provenance and scope. [MIMIC-III Clinical Database Demo](https://physionet.org/content/mimiciii-demo/1.4/) · [UCI Diabetes 130-US Hospitals](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008)
- Independent testing, representative data, human oversight and monitoring. [FDA and IMDRF good machine learning practice principles](https://www.fda.gov/medical-devices/artificial-intelligence-enabled-medical-devices/good-machine-learning-practice-medical-device-development-guiding-principles)
