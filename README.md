# 🛡️ SafeNest  
### Privacy-Preserving Community Safety Risk Intelligence

SafeNest is a real-time public safety intelligence system that analyzes CCTV footage, extracts safety-relevant signals, classifies risk domains, and computes a Crisis Risk Index (CRI) to support early detection, situational awareness, and emergency response planning.

👉 **Quickstart Guide:** See [QUICKSTART.md](./QUICKSTART.md) to run locally.

---

## 🚨 Problem Context

Across many urban environments, CCTV infrastructure already exists — but most systems are passive. They record footage without actively interpreting risk in real time. As a result:

- Critical signals (e.g., child distress, elderly falls, fire outbreaks, violent motion) may go unnoticed.
- Monitoring often depends on human operators manually watching multiple feeds.
- Alerts are reactive rather than predictive.
- Geographic risk patterns are not aggregated for strategic planning.

Communities need a system that transforms raw surveillance footage into structured, actionable intelligence — without compromising privacy.

SafeNest addresses this gap by turning unstructured video into domain-specific risk assessments and geographic insights.

---

## 💡 Our Solution

SafeNest transforms CCTV footage into structured safety intelligence by:

1. Detecting safety-relevant signals
2. Classifying footage into safety domains:
   - 👶 Child Safety  
   - 👴 Elder Safety  
   - 🌋 Environmental Hazard  
   - 🚔 Crime  
3. Computing a **Crisis Risk Index (CRI)** score (0–100)
4. Estimating escalation probability
5. Logging alerts
6. Visualizing geographic risk using a Singapore heatmap

This enables faster decision-making and smarter emergency planning.

---

## 🔍 Key Features

- 🎥 Video-based safety signal extraction
- 🧠 AI-powered domain classification
- 📊 Crisis Risk Index (0–100)
- 📈 Escalation probability estimation
- 🗂 Alert history tracking
- 🗺 Singapore risk heatmap visualization
- 🔐 Privacy-preserving design (no facial recognition, no identity tracking)

---

## 🏗 System Architecture

### Frontend
- React-based dashboard
- Signal simulator
- Alert history panel
- Risk analysis display
- Geographic heatmap visualization

### Backend
- Flask API
- Video frame processing
- Signal feature generation
- OpenAI-powered classification
- Risk scoring engine
- In-memory alert storage

### AI Integration
- Uses OpenAI API for:
  - Signal interpretation
  - Domain classification
  - Risk assessment reasoning

---

## 📊 How Safety Signals Are Interpreted

From CCTV footage, SafeNest extracts contextual indicators such as:

- Distress behavior
- Loitering patterns
- Rapid motion anomalies
- Environmental hazards (e.g., fire/smoke)
- Suspicious movement patterns

These signals are structured into a standardized format and passed to the AI model for domain classification and severity estimation.

---

## 📈 Crisis Risk Index (CRI)

The CRI is a score between **0 and 100** representing overall threat level.

Conceptually, it considers:
- Severity of detected signals
- Number of compounding indicators
- Vulnerable population context
- Escalation likelihood

Risk levels:
- 🟢 0–30 → Safe  
- 🟡 31–60 → Watch  
- 🟠 61–80 → High Risk  
- 🔴 81–100 → Critical  

The CRI serves as a decision-support indicator — not a replacement for human judgment.

---

## 🗺 Heatmap Visualization

SafeNest maps alerts onto a Singapore island visualization to:

- Identify high-risk clusters
- Monitor geographic concentration of incidents
- Support emergency resource planning
- Improve long-term preventive deployment

Bubble size reflects alert concentration.

---

## 🔐 Privacy & Ethical Considerations

SafeNest is designed with privacy-first principles:

- ❌ No facial recognition
- ❌ No identity tracking
- ❌ No biometric storage
- ✅ Signal-based risk abstraction
- ✅ Short-lived alert storage
- ✅ Contextual analysis only

The system focuses on **situational intelligence**, not surveillance profiling.

---

## ⚙️ Tech Stack

- **Frontend:** React
- **Backend:** Flask (Python)
- **AI:** OpenAI API
- **Visualization:** Custom heatmap rendering
- **Styling:** CSS
- **Deployment:** Local development environment

---

## 🚀 Demo Flow

1. Select Safety Domain
2. Toggle relevant safety signals OR upload video
3. Click **Analyze Risk**
4. View:
   - CRI score
   - Escalation probability
   - Domain classification
   - Alert history update
   - Heatmap visualization

---

## ⚠️ Limitations

- Uses sampled frames, not full motion understanding
- In-memory alert storage (not persistent)
- Risk scoring is heuristic + AI-guided (not calibrated to real emergency datasets)
- Heatmap coordinates are simulated for demo purposes

---

## 🔮 Future Improvements

- Persistent database storage
- Real geographic coordinate integration
- Offline lightweight edge model
- Multi-camera correlation
- Real-time streaming ingestion
- Emergency service API integration
- Model fine-tuning for safety contexts

---

## 🏁 Conclusion

SafeNest demonstrates how AI-powered safety intelligence can:

- Enable earlier detection
- Improve situational awareness
- Support coordinated response
- Operate responsibly in diverse community environments

High-quality safety systems can be delivered effectively — and ethically.

---
