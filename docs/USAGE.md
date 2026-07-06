# HealthSteward Usage Guide

Quick reference for running and using HealthSteward.

---

## Starting the Application

### 1. Backend (API Server)

```bash
cd /Users/menon/workspace/HealthSteward
python -m uvicorn src.main:app --reload --port 8000
```

The API will be available at http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2. Frontend (React UI)

```bash
cd /Users/menon/workspace/HealthSteward/frontend
pnpm dev
```

The UI will be available at http://localhost:3000

---

## First-Time Setup

### Install Dependencies

**Backend:**
```bash
cd /Users/menon/workspace/HealthSteward
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
pnpm install
```

### Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Initialize Database

The database is created automatically on first run. To reset:
```bash
rm data/healthsteward.db
alembic upgrade head
```

---

## Using the Application

### Step 1: Create a Health Profile

1. Open http://localhost:3000
2. Click **"+ New Profile"**
3. Enter:
   - Name (required)
   - Date of birth
   - Blood type
   - Allergies
   - Emergency contact info
4. Click **"Create Profile"**

### Step 2: Add Health Data

Click on a profile to open it, then use the tabs:

**Conditions Tab:**
- Click **"+ Add Condition"**
- Enter condition name (e.g., "Type 2 Diabetes")
- Set severity (mild/moderate/severe)
- Set status (active/managed/resolved)
- Add notes

**Medications Tab:**
- Click **"+ Add Medication"**
- Enter medication name (e.g., "Metformin")
- Add dosage (e.g., "500mg")
- Add frequency (e.g., "twice daily")
- Note purpose and side effects

**Doctors Tab:**
- Click **"+ Add Doctor"**
- Enter doctor name
- Add specialty (e.g., "Endocrinology")
- Add clinic, phone, email

### Step 3: Schedule an Appointment

1. Go to **Appointments** tab
2. Click **"+ Schedule Appointment"**
3. Select a doctor (must add doctors first)
4. Pick date and time
5. Enter purpose (e.g., "Quarterly diabetes checkup")

### Step 4: Generate Visit Preparation

1. On any appointment, click **"Prepare Visit"**
2. Optionally add additional concerns
3. Click **"Generate Questions with AI"**
4. Review the AI-generated questions organized by category
5. Use **"Regenerate"** if you want different questions

### Step 5: Upload an After-Visit Summary (AVS)

1. Drop your PDF into the `data/avs/` folder in the project directory
2. Go to the **Documents** tab on your profile page
3. Click **"Scan for new files"** — the PDF appears as a new file (auto-refreshes every 30 s)
4. Click **"Parse"** to extract data using the local Ollama model
5. Review the parsed results (vitals, diagnoses, medications, lab orders, referrals, follow-ups)
6. Check items you want to apply and click **"Apply to Profile"**
7. Immediately after applying, a panel shows extracted follow-ups, lab orders, and referrals

### Step 6: Review Proactive Action Items

After applying an AVS or just browsing your profile:

1. Go to the **Overview** tab
2. The **Action Items** section surfaces things needing attention:
   - Upcoming appointments without visit prep
   - Past appointments to close out
   - Completed visits missing an AVS document
   - Vitals trends (weight, BMI, blood pressure, heart rate) across visits
   - Pending follow-up appointments with aging indicators (overdue / approaching)
   - Lab orders with staleness warnings and appointment-proximity alerts
   - Outstanding referrals
3. Each nudge has a **"Snooze 1w"** button — hides it for 7 days, then it re-surfaces automatically
4. Action nudges (follow-ups, lab orders, referrals, past-due appointments) have a one-click button to mark the item complete or navigate to it
5. Click **"Prepare"** on an upcoming-appointment nudge to go directly to visit prep

---

## API Usage (curl examples)

### Create a Profile
```bash
curl -X POST http://localhost:8000/api/profiles/ \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "blood_type": "O+", "allergies": "Penicillin"}'
```

### Add a Condition
```bash
curl -X POST http://localhost:8000/api/profiles/{profile_id}/conditions/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Hypertension", "severity": "moderate", "status": "managed"}'
```

### Add a Doctor
```bash
curl -X POST http://localhost:8000/api/profiles/{profile_id}/doctors/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Dr. Smith", "specialty": "Cardiology", "phone": "555-1234"}'
```

### Schedule an Appointment
```bash
curl -X POST http://localhost:8000/api/profiles/{profile_id}/appointments/ \
  -H "Content-Type: application/json" \
  -d '{"doctor_id": "{doctor_id}", "scheduled_date": "2025-03-15T10:00:00", "purpose": "Annual checkup"}'
```

### Generate Visit Prep
```bash
curl -X POST http://localhost:8000/api/visits/{appointment_id}/prepare \
  -H "Content-Type: application/json" \
  -d '{"additional_concerns": "Feeling tired lately"}'
```

### Get Visit Prep
```bash
curl http://localhost:8000/api/visits/{appointment_id}/prep
```

---

## Running Tests

```bash
cd /Users/menon/workspace/HealthSteward
pytest tests/ -v
```

---

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### Frontend won't start
```bash
cd frontend
pnpm install
```

### Database errors
```bash
rm data/healthsteward.db
alembic upgrade head
```

### AI features not working
- Check that `ANTHROPIC_API_KEY` is set in `.env`
- Verify key is valid at https://console.anthropic.com

### CORS errors
- Make sure backend is running on port 8000
- Make sure frontend is running on port 3000
- The Vite proxy handles API requests automatically

---

## File Locations

| What | Where |
|------|-------|
| Backend code | `src/` |
| Frontend code | `frontend/src/` |
| Database | `data/healthsteward.db` |
| Logs | `logs/healthsteward.log` |
| Environment config | `.env` |
| API docs | http://localhost:8000/docs |

---

*Last updated: 2026-07-05*
