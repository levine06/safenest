# SafeNest

SafeNest is a small developer demo that analyzes anonymized safety signals from CCTV-style video and classifies footage into one or more safety domains (for example: `child_safety`, `elderly_safety`, `environmental_hazards`, `crime`). For each classified domain it computes a domain-specific Crisis Risk Index (CRI) — a transparent, rule-based risk score used to rank and triage incidents.

- a Flask backend (`backend/`) that exposes a JSON API for analysis and optional domain classification
- a React frontend (`frontend/`) for uploading videos and interacting with the demo

This repository is intended for local development and demonstration purposes only. See the quick start for rapid setup: [QUICKSTART.md](QUICKSTART.md)

Project layout (top-level)

```
safenest/
├─ backend/      # Flask API and Python utilities
├─ frontend/     # React app
├─ videos/       # sample/test videos
├─ QUICKSTART.md
└─ README.md
```

License / notes

- This is a prototype; do not use for real monitoring without appropriate safeguards.
- For detailed developer notes and examples, open `backend/` and `frontend/` folders.
- ✅ Risk classifications (danger tier)
- ✅ Timestamps
- ✅ Escalation probabilities

### Data Retention
- **Automatic Purge:** All alerts deleted after 15 minutes
- **No Archival:** No long-term storage or databases
- **Simulation Only:** No real CCTV, microphones, or biometric processing

This is a **simulation prototype**—in production, additional safeguards (encryption, audit logging, consent systems) would be required.

---

## 📡 API Endpoints

### `POST /analyze-risk`

Analyze safety signals, optionally include or request domain classification, and compute a domain-specific risk score.

**Request (minimal):**
```json
{
  "domain": "crime",                
  "signals": {
    "distress_audio_detected": true,
    "rapid_motion_detected": true,
    "stationary_person_detected": false,
    "loitering_detected": true,
    "multiple_reports": false,
    "smoke_or_fire_detected": false
  },
  "context": {
    "camera_id": "cam-123",
    "timestamp": "2026-03-01T14:32:00Z"
  }
}
```

The `domain` field may be provided by the client or omitted to let the backend infer one or more domains from the signals and context.

**Response:**
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

### `GET /alerts`

Retrieve recent alerts (auto-purged after 15 minutes).

**Response:**
```json
{
  "alerts": [
    {
      "alert_id": 3,
      "risk_score": 75.5,
      "danger_rank": "Orange",
      "danger_tier": "High Risk",
      "triggered_signals": ["distress_scream_detected", "rapid_motion_detected"],
      "escalation_probability": 90,
      "confidence": 0.9,
      "timestamp": "2026-03-01T14:32:15.123456Z"
    },
    ...
  ],
  "count": 5,
  "retention_minutes": 15,
  "timestamp": "2026-03-01T14:35:00.000000Z"
}
```

### `GET /health`

Health check endpoint.

---

## 🎮 Demo Mode

Click the **"🎲 Demo Mode"** button to randomize all signals at once. Perfect for judges to quickly see different risk scenarios!

---

## 📊 Risk Scoring Examples

### Example 1: All Clear
```
Signals: All OFF
Risk Score: 0
Danger Rank: Green (Safe)
Escalation: 20%
```

### Example 2: Mild Concern
```
Signals: after_school_hours=ON
Risk Score: 10 × 0.6 = 6
Danger Rank: Green (Safe)
Escalation: 30%
```

### Example 3: High Alert
```
Signals (example domain=crime):
  - distress_audio_detected=ON (+45)
  - rapid_motion_detected=ON (+35)
  - loitering_detected=ON (+30)
  - multiple_reports=ON (+20)

Weighted Sum: 45+35+30+20 = 130
Confidence: 0.9 (4 signals)
Risk Score: 130 × 0.9 = 117 → Clamped to 100
Danger Rank: Red (Critical)
Escalation: 20+25+20+15+10 = 90%
```

---

## 🛠️ Tech Stack

- **Frontend:** React 18, Axios, CSS Grid
- **Backend:** Flask, Python 3.7+
- **Storage:** In-memory array (alerts list)
- **Communication:** REST API with CORS

### Dependencies

**Backend (`requirements.txt`):**
- Flask 2.3.2
- flask-cors 4.0.0
- Werkzeug 2.3.6

**Frontend (`package.json`):**
- react 18.2.0
- react-dom 18.2.0
- axios 1.4.0
- react-scripts 5.0.1

---

## 🧪 Testing the System

### Manual Test Scenario

1. **Dashboard loads:** Both frontend and backend running
2. **All signals OFF:** Click "Analyze Risk" → Risk score ≈ 0, Green tier
3. **Toggle some signals:** Click "Analyze Risk" → Check risk score changes match weighted sum
4. **Demo Mode:** Click "🎲 Demo Mode" → Random signals → Instant analysis
5. **Alert History:** Verify alerts appear in the table, showing most recent first
6. **Privacy Banner:** Read Privacy & Anonymity explainer
7. **15-min retention:** Reload page → Old alerts should disappear (demo: instant with mock timestamps)

### Backend Testing (Python)

```bash
cd safenest/backend
python -c "from utils.risk_scorer import analyze_risk; result = analyze_risk({'distress_scream_detected': True, 'rapid_motion_detected': True, 'child_stopped_moving': False, 'adult_loitering_detected': True, 'multiple_reports': False, 'after_school_hours': True}); print(result)"
```

---

## 📝 Notes for Judges

- **Privacy-First:** This prototype emphasizes anonymity at every layer. No biometric data, faces, or IDs.
- **Explainability:** Risk scoring uses transparent, rule-based logic—not ML black boxes.
-- **Responsible Design:** Demonstrates how to build safety tools responsibly for public safety domains (children, elderly, environmental hazards, crime), and includes privacy-preserving defaults.
- **Extensibility:** The risk scoring engine can be enhanced with additional signals, weights, or smarter confidence factors.
- **Simulation Only:** This is a proof-of-concept. Real deployments would require legal review, consent frameworks, and audit logging.

---

## 🚀 Future Enhancements

- Add Chart.js for risk trend visualization over time
- Implement user authentication and role-based access
- Add configurable signal weights (admin panel)
- Integrate with real safety data APIs
- Add incident lifecycle management (open, in-progress, resolved)
- Deploy to cloud (AWS, Google Cloud, Azure)
- Add comprehensive audit logging
- Multi-language support

---

## 📄 License

This is a hackathon prototype. Use freely for educational and demonstration purposes.

---

## ❓ FAQ

**Q: Is this actually monitoring children?**  
A: No. This is a simulation prototype. No real audio, video, or biometric data is processed.

**Q: How is data deleted after 15 minutes?**  
A: Every `/alerts` request filters out alerts older than 15 minutes. No background jobs needed.

**Q: Can I customize signal weights?**  
A: Yes! Edit the `SIGNAL_WEIGHTS` dict in `backend/utils/risk_scorer.py`.

**Q: How do I deploy this to production?**  
A: Don't, without significant security/legal review. This is a prototype for educational purposes.

---

## 📞 Support

Questions? Check the code comments or review the risk scoring logic in `backend/utils/risk_scorer.py`.

---

**Built with ❤️ for public safety and privacy.**
