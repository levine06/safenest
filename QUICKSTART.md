# Quickstart — SafeNest (concise)

This quickstart gets the backend API and frontend dev server running locally.

Prereqs

- Python 3.8+ and virtualenv
- Node.js (v14+) and npm

1) Start backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The backend listens on http://localhost:5000 by default.

2) Start frontend (terminal 2)

```bash
cd frontend
npm install
npm start
```

The React dev server runs at http://localhost:3000 and will connect to the backend.

Quick API examples

Analyze signals (POST /analyze-risk). Include `domain` or omit to let the backend infer it:

```bash
curl -X POST http://localhost:5000/analyze-risk \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "crime",
    "signals": {
      "distress_audio_detected": true,
      "rapid_motion_detected": true,
      "stationary_person_detected": false,
      "loitering_detected": true,
      "multiple_reports": false,
      "smoke_or_fire_detected": false
    },
    "context": {"camera_id": "cam-123"}
  }'
```

Expected (example) response:

```json
{
  "domain": "crime",
  "risk_score": 75.5,
  "danger_rank": "Orange",
  "danger_tier": "High Risk",
  "triggered_signals": ["distress_audio_detected","rapid_motion_detected","loitering_detected"],
  "escalation_probability": 90,
  "confidence": 0.9,
  "timestamp": "2026-03-01T14:32:15.123456Z",
  "alert_id": 1
}
```

Get recent alerts (GET /alerts):

```bash
curl http://localhost:5000/alerts
```

Troubleshooting (common)

- If ports 3000 or 5000 are in use, stop the occupying process or change ports.
- If dependencies fail, re-run `pip install -r backend/requirements.txt` and `npm install`.

Further details and examples are in `backend/` and `frontend/` source files.

Enjoy exploring SafeNest! 🏠
