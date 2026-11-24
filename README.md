# .Discharge+ 🏥

**B2B Multi-Tenant Hospital Post-Discharge Care Platform**

Discharge+ is a SaaS platform that helps hospitals monitor and manage patients after discharge, reducing readmission rates through AI-driven risk scoring, automated surveys, real-time communication, and intelligent report analysis.

---

## ✨ Features

### 👨‍💼 Admin Portal

- Hospital registration & onboarding
- Doctor/Patient CRUD with auto-generated credentials
- CSV bulk import for patients
- Doctor ↔ Patient assignment management
- Analytics dashboard (survey completion, risk distribution, doctor performance)

### 🩺 Doctor Portal

- Patient list with risk badges (High/Medium/Low) & real-time filters
- Detailed patient view with **4 trend charts** (Temperature, SpO2, BP, Blood Sugar) with normal ranges
- AI-driven survey builder (8 question types: vitals, pain slider, photo/voice uploads)
- Private doctor notes per patient
- Real-time chat & video calling (100ms.live)

### 🤒 Patient Portal

- Recovery progress ring (Day X of Y)
- Dynamic health surveys with AI feedback after submission
- **Report Analyzer** — upload medical reports → OCR → AI analysis with:
  - Color-coded parameters (normal/borderline/abnormal)
  - Plain-language summary (English/Hindi toggle)
  - Suggested doctor questions
- Medication tracker with streak system (🔥 day streak)
- Chat with assigned doctor & video call support

### 🤖 AI Engine (Groq)

- Risk scoring on survey responses (low/medium/high)
- Medical report analysis (parameter extraction, patient-friendly explanations)
- Multi-language support (English / Hindi)

---

## 🏗️ Architecture

```
Dischage+/
├── database/
│   └── schema.sql          # 18 tables, RLS policies, triggers
├── backend/
│   ├── main.py             # FastAPI app + CORS + routers
│   ├── config.py           # Pydantic settings
│   ├── dependencies.py     # JWT auth + Supabase client
│   ├── models/schemas.py   # Pydantic request/response models
│   ├── routers/
│   │   ├── auth.py         # Login, admin register
│   │   ├── admin.py        # CRUD, CSV import, assignments
│   │   ├── doctor.py       # Patient list, detail, notes
│   │   ├── patient.py      # Profile, medications
│   │   ├── survey.py       # Survey builder, responses
│   │   ├── ai.py           # Report analysis endpoints
│   │   └── chat.py         # Chat + 100ms video calls
│   ├── services/
│   │   ├── ai_service.py   # Groq integration
│   │   ├── risk_service.py # Risk scoring engine
│   │   └── email_service.py# SMTP + Jinja2 templates
│   ├── utils/helpers.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Router with role-based guards
│   │   ├── lib/            # supabase.js, api.js (Axios)
│   │   ├── store/          # Zustand global state
│   │   ├── hooks/          # useAuth, useChat, useRealtime
│   │   ├── components/     # Sidebar, StatCard, RiskBadge, Charts
│   │   └── pages/
│   │       ├── Auth/       # AdminLogin, Register, DoctorLogin, PatientLogin
│   │       ├── Admin/      # Dashboard, Doctors, Patients, Assignments, Analytics
│   │       ├── Doctor/     # Dashboard, PatientDetail, SendSurvey, Chat, CallRoom
│   │       └── Patient/    # Dashboard, Survey, ReportAnalyzer, Medications, Chat, CallRoom
│   ├── Dockerfile
│   └── vite.config.js
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ & **npm**
- **Python** 3.11+
- **Supabase** project (get one at [supabase.com](https://supabase.com))
- **Groq** API key (get one at [console.groq.com](https://console.groq.com))
- *(Optional)* **100ms.live** account for video calls

### 1. Database Setup

1. Go to your Supabase dashboard → **SQL Editor**
2. Paste and run `database/schema.sql`
3. This creates all 18 tables, RLS policies, indexes, and triggers

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt

# Copy and fill environment variables
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Edit `.env` with your credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
GROQ_API_KEY=gsk_your_key
SMTP_SERVER=smtp.gmail.com
SMTP_EMAIL=your@email.com
SMTP_PASSWORD=your-app-password
HMS_ACCESS_KEY=your-100ms-key       # Optional
HMS_SECRET=your-100ms-secret         # Optional
```

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Copy and fill environment variables
copy .env.example .env

# Edit .env
# VITE_SUPABASE_URL=https://your-project.supabase.co
# VITE_SUPABASE_ANON_KEY=your-anon-key
# VITE_API_URL=http://localhost:8000

npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### 4. Docker Deployment (Optional)

```bash
docker-compose up --build -d
```

- Frontend (local): [http://localhost:3000](http://localhost:3000)
- Backend (local): [http://localhost:8000](http://localhost:8000)
- Frontend (deployed): [https://dischargeplusai-poweredrecoveryplat.vercel.app/](https://dischargeplusai-poweredrecoveryplat.vercel.app/)
- Backend (deployed): [https://dischargeplus-ai-powered-recovery.onrender.com/](https://dischargeplus-ai-powered-recovery.onrender.com/)

---

## 🧪 Demo Credentials

Use these accounts to explore the live platform. Pick any role below and sign in at the matching login page.


| Role    | Login URL                                                                              |
| ------- | -------------------------------------------------------------------------------------- |
| Admin   | [/login](https://dischargeplusai-poweredrecoveryplat.vercel.app/login)                 |
| Doctor  | [/doctor-login](https://dischargeplusai-poweredrecoveryplat.vercel.app/doctor-login)   |
| Patient | [/patient-login](https://dischargeplusai-poweredrecoveryplat.vercel.app/patient-login) |


### Admin


| Email                                     | Password             |
| ----------------------------------------- | -------------------- |
| [admin@aiims.com](mailto:admin@aiims.com) | `Hospital@aiims` |


### Doctors


| Name                 | Email                                                           | Password       |
| -------------------- | --------------------------------------------------------------- | -------------- |
| Dr. Pranav Vashisth  | [pranavvashisth03@gmail.com](mailto:pranavvashisth03@gmail.com) | `Ij4%V6brxob9` |
| Dr. Kavya Jethani    | [kavya09@gmail.com](mailto:kavya09@gmail.com)                   | `Pv1%dr#Sy6k7` |
| Dr. Somik Jain       | [somjain1212@gmail.com](mailto:somjain1212@gmail.com)           | `Lr7$XoNI2O#B` |
| Dr. Pranshu Bhansali | [pranshu22129@gmail.com](mailto:pranshu22129@gmail.com)         | `Zx3$T9XYR$we` |
| Dr. Hemang Jain      | [hemang_jain@gmail.com](mailto:hemang_jain@gmail.com)           | `Rb6$DUz5NGJA` |
| Dr. Rehan Khan       | [ryhorn124@gmai.com](mailto:ryhorn124@gmai.com)                 | `Jo9$ItQH8D@d` |


### Patients


| Email                                                       | Password       |
| ----------------------------------------------------------- | -------------- |
| [rajesh324@gmail.com](mailto:rajesh324@gmail.com)           | `Sv6!4xFql0ct` |
| [ritvik788@gmail.com](mailto:ritvik788@gmail.com)           | `Lz9#L#bKI3!n` |
| [bansalaayu8@gmail.com](mailto:bansalaayu8@gmail.com)       | `Hi2@CBfypi7B` |
| [himskhat@gmail.com](mailto:himskhat@gmail.com)             | `Od3$fqIFnYOD` |
| [sainigigi@gmail.com](mailto:sainigigi@gmail.com)           | `Dh8#XAhY#M!i` |
| [sainisomu@gmail.com](mailto:sainisomu@gmail.com)           | `Bn7!n34G10g7` |
| [varunvashishth@gmail.com](mailto:varunvashishth@gmail.com) | `Ks5@@Vnxs3mM` |
| [karun23@gmail.com](mailto:karun23@gmail.com)               | `Ab8$k4qErdFB` |


> **Note:** These are shared demo accounts for evaluation only. Do not use them for real patient data.

---

## 🔐 Multi-Tenant Security


| Layer        | Mechanism                                                         |
| ------------ | ----------------------------------------------------------------- |
| **Database** | Row Level Security (RLS) — every query is scoped to `hospital_id` |
| **Backend**  | JWT middleware validates tokens and injects `hospital_id`         |
| **Frontend** | Role-based `ProtectedRoute` (admin/doctor/patient)                |


---

## 📋 API Endpoints


| Method | Endpoint                      | Role    | Description        |
| ------ | ----------------------------- | ------- | ------------------ |
| POST   | `/auth/login`                 | Public  | Login              |
| POST   | `/auth/admin-register`        | Public  | Register hospital  |
| GET    | `/admin/stats`                | Admin   | Dashboard stats    |
| POST   | `/admin/doctors`              | Admin   | Create doctor      |
| POST   | `/admin/patients`             | Admin   | Create patient     |
| POST   | `/admin/patients/bulk-import` | Admin   | CSV import         |
| GET    | `/doctor/patients`            | Doctor  | Patient list       |
| POST   | `/surveys/create`             | Doctor  | Send survey        |
| POST   | `/surveys/{id}/respond`       | Patient | Submit response    |
| POST   | `/ai/analyze-report`          | Patient | AI report analysis |
| POST   | `/chat/{patient_id}/message`  | Any     | Send chat message  |
| POST   | `/chat/calls/create-room`     | Doctor  | Start video call   |


---

## 🎨 Design System

- **Primary**: Deep Navy `#0A1628`
- **Accent**: Teal `#00D4AA`
- **Glass Cards**: `backdrop-filter: blur(20px)` with subtle borders
- **Typography**: Inter font family
- **Animations**: Framer Motion page transitions & micro-interactions
- **Charts**: Recharts (Line, Bar, Pie, Area with normal-range bands)

---

