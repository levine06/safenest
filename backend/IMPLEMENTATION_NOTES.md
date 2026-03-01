# Vision-Based Video Classification Implementation

## Summary of Changes

### 1. New Module: `utils/vision_classifier.py`
Implements GPT-4o-mini Vision API integration for CCTV video analysis:
- **`select_keyframes(timeline_data, frame_list)`**: Selects up to 3 keyframes deterministically based on:
  - Frame with max motion_intensity
  - Frame with max fire/smoke probability
  - Frame with max fighting probability
  - Optional: First fall_detected frame (if present)
  - De-duplicates by timestamp, capped at 3 total

- **`frame_to_base64_jpeg(frame, quality=85)`**: Converts OpenCV BGR frames to base64 JPEG data URLs for API transmission

- **`classify_video_with_vision(keyframes, all_signal_features)`**: Main classification function that:
  - Builds domain definitions & prompt
  - Sends keyframes + signal summary to GPT-4o-mini
  - Returns domain classification with 4 domains:
    - `child_safety`
    - `elder_safety`
    - `environmental_hazard`
    - `crime`
  - Returns: severity (0-1), domain_probabilities, reasoning, key_observations
  - Graceful fallback if API fails (returns gpt_used=false)

### 2. Modified: `utils/signal_detector.py`
- **Removed**: Per-frame GPT-4o-mini calls (`classify_with_gpt4mini`, `format_frame_analysis_for_gpt`)
- **Kept**: All heuristic signal generation in `generate_signal_features()`
- **Result**: `generate_signal_features()` now returns clean heuristic signals only; no GPT processing at frame level

### 3. Modified: `app.py` - `/analyze-video` Endpoint
Enhanced endpoint now:

#### Flow:
1. Extract & analyze frames (existing heuristic pipeline)
2. Generate frame-level signals (heuristic only)
3. Select keyframes deterministically
4. Call GPT-4o-mini Vision with keyframes
5. Compute both heuristic and GPT-based risk scores
6. Calibrate final risk score using formula

#### Response JSON (NEW):
```json
{
  "status": "success",
  "primary_domain": "child_safety|elder_safety|environmental_hazard|crime",
  "domain_probabilities": {
    "child_safety": 0.0-1.0,
    "elder_safety": 0.0-1.0,
    "environmental_hazard": 0.0-1.0,
    "crime": 0.0-1.0
  },
  "domain_confidence": 0.0-1.0,
  "gpt_severity": 0.0-1.0,
  "heuristic_risk_score": 0.0-1.0,
  "final_risk_score": 0.0-1.0,
  "risk_score": 0.0-1.0,
  "keyframes_used": [
    {
      "timestamp": 2.5,
      "reasons": ["max_motion", "max_fighting"]
    },
    ...
  ],
  "gpt_used": true,
  "signals_detected": {...},
  "danger_rank": "...",
  "danger_tier": "...",
  "escalation_probability": 0.0-100.0,
  "triggered_signals": [...],
  "reasoning": "...",
  "key_observations": ["...", "...", "..."],
  "timeline": [...],
  "frames_analyzed": 20,
  "video_duration": 14.2
}
```

#### Risk Score Calibration:
```
heuristic_risk_score = analyze_risk(signals, domain) / 100.0  # Convert to 0-1
gpt_severity = severity from GPT response (0-1)
calibrated = 0.6 * gpt_severity + 0.4 * heuristic_risk
final_risk_score = clamp(max(heuristic_risk, calibrated), 0, 1)
```

#### Graceful Fallback:
If GPT fails (API error, JSON parse error, no keyframes):
- `gpt_used = false`
- Falls back to heuristic domain classifier
- `final_risk_score = heuristic_risk_score`
- Response includes error information

---

## Test Plan

### Unit Tests

#### 1. Keyframe Selection
```python
# Test with timeline data
timeline = [
    {'timestamp': 0.5, 'motion_intensity': 0.1, 'signals': {
        'fire_smoke_detected': 0.1, 'fighting_detected': 0.0
    }},
    {'timestamp': 2.0, 'motion_intensity': 0.8, 'signals': {
        'fire_smoke_detected': 0.1, 'fighting_detected': 0.0
    }},
    {'timestamp': 5.0, 'motion_intensity': 0.2, 'signals': {
        'fire_smoke_detected': 0.9, 'fighting_detected': 0.0
    }},
    {'timestamp': 8.0, 'motion_intensity': 0.3, 'signals': {
        'fire_smoke_detected': 0.1, 'fighting_detected': 0.85
    }},
]
frames = [
    {'frame': frame_np_array, 'timestamp': 0.5},
    {'frame': frame_np_array, 'timestamp': 2.0},
    {'frame': frame_np_array, 'timestamp': 5.0},
    {'frame': frame_np_array, 'timestamp': 8.0},
]

keyframes = select_keyframes(timeline, frames)
# Expected: 3 keyframes at timestamps [2.0 (max_motion), 5.0 (max_fire), 8.0 (max_fighting)]
# Verify: all have correct reasons, no duplicates, ordered by timestamp
```

#### 2. Frame Encoding
```python
import cv2
import numpy as np

frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
data_url = frame_to_base64_jpeg(frame)

# Verify:
assert data_url.startswith('data:image/jpeg;base64,')
assert len(data_url) > 100
```

#### 3. GPT Classification Fallback
```python
# Test with no OpenAI key
os.environ.pop('OPENAI_API_KEY', None)

result = classify_video_with_vision([], {})
# Expected: gpt_used=false, error message, default domain=child_safety
assert result['gpt_used'] == False
assert result['primary_domain'] == 'child_safety'
```

### Integration Tests

#### 4. Full Video Analysis with GPT
```bash
# Start backend (with OPENAI_API_KEY set)
cd /Users/levine/deeplearningweek/safenest/backend
/Users/levine/deeplearningweek/.venv/bin/python app.py

# In another terminal, send test video
curl -X POST http://localhost:5001/analyze-video \
  -F "video=@test_video.mp4"

# Verify response JSON includes:
# - "gpt_used": true
# - "primary_domain": one of 4 domains
# - "domain_probabilities": sums to ~1.0
# - "gpt_severity": 0-1 float
# - "final_risk_score": 0-1 float
# - "keyframes_used": array with 1-3 items, each with timestamp & reasons
# - "key_observations": array of strings
```

#### 5. Risk Score Calibration Verification
```
# Inspect response JSON:
heuristic = response['heuristic_risk_score']
gpt_sev = response['gpt_severity']
final = response['final_risk_score']

# Verify formula:
expected_calibrated = 0.6 * gpt_sev + 0.4 * heuristic
expected_final = max(heuristic, expected_calibrated)
assert final == clamp(expected_final, 0, 1)
```

---

## Curl Examples

### Example 1: Analyze Video with GPT (Expected to work if OpenAI key is set)
```bash
curl -X POST http://localhost:5001/analyze-video \
  -F "video=@~/Videos/test_video.mp4" \
  2>&1 | jq '.' | head -100
```

Expected output excerpt:
```json
{
  "status": "success",
  "primary_domain": "crime",
  "domain_probabilities": {
    "child_safety": 0.1,
    "elder_safety": 0.05,
    "environmental_hazard": 0.15,
    "crime": 0.7
  },
  "domain_confidence": 0.7,
  "gpt_severity": 0.75,
  "heuristic_risk_score": 0.45,
  "final_risk_score": 0.61,
  "gpt_used": true,
  "keyframes_used": [
    {
      "timestamp": 2.5,
      "reasons": ["max_motion"]
    },
    {
      "timestamp": 4.2,
      "reasons": ["max_fighting"]
    }
  ],
  "key_observations": [
    "Two people in close proximity with rapid aggressive movements",
    "Signs of physical contact detected in frame",
    "Possible weapon-like object visible in high-motion region"
  ]
}
```

### Example 2: Fallback to Heuristics (if GPT fails)
```bash
# Unset OpenAI key (forces fallback)
unset OPENAI_API_KEY

curl -X POST http://localhost:5001/analyze-video \
  -F "video=@~/Videos/test_video.mp4" \
  2>&1 | jq '.gpt_used, .primary_domain, .final_risk_score'
```

Expected output:
```json
false
"child_safety"
0.35
```

### Example 3: Extract and Pretty-Print Keyframes Info
```bash
curl -s -X POST http://localhost:5001/analyze-video \
  -F "video=@~/Videos/test_video.mp4" \
  | jq '{
      gpt_used,
      primary_domain,
      keyframes_used,
      key_observations,
      final_risk_score,
      gpt_severity
    }'
```

---

## Key Observations Format

GPT returns 2-3 key observations grounded in visual evidence, e.g.:
- "Visible flames and heavy smoke detected in lower-right portion of frame at 5s"
- "Multiple elderly individuals detected, one appears immobilized near equipment at 12s"
- "Rapid crowd movement with people falling in stampede pattern"

---

## Domain Definitions (Sent to GPT)

1. **child_safety**: Child endangerment, abuse, neglect, inappropriate adult behavior, distress, trauma
2. **elder_safety**: Falls, medical emergencies, neglect, vulnerability
3. **environmental_hazard**: Fire, smoke, structural hazards, flooding, chemical leaks, power outages
4. **crime**: Weapons, fighting, robbery, assault, theft, property damage, forced entry

---

## Debugging

### Check if OpenAI Client Initializes:
```bash
cd /Users/levine/deeplearningweek/safenest/backend
/Users/levine/deeplearningweek/.venv/bin/python -c "
from utils.vision_classifier import get_openai_client
client = get_openai_client()
print(f'Client initialized: {client is not None}')
"
```

### Check Flask App Loads:
```bash
cd /Users/levine/deeplearningweek/safenest/backend
/Users/levine/deeplearningweek/.venv/bin/python -c "import app; print('✓ app.py loads OK')"
```

### Monitor Keyframe Selection:
Add debug logs in `select_keyframes()`:
```python
print(f"DEBUG: Selected {len(selected_indices)} keyframes at indices: {sorted_indices}")
for kf in keyframes:
    print(f"  - timestamp={kf['timestamp']}, reasons={kf['reasons']}")
```

### Monitor GPT Calls:
Add debug logs in `classify_video_with_vision()`:
```python
print(f"DEBUG: Calling GPT-4o-mini with {len(keyframes)} keyframes")
print(f"DEBUG: Signal summary: {signal_summary_json}")
```

---

## Constraints & Assumptions

1. ✅ Backend only (no frontend changes)
2. ✅ Keeps existing endpoints (`/analyze-risk`, `/alerts`, `/health`)
3. ✅ Minimal, clean changes
4. ✅ Graceful fallback if GPT fails
5. ✅ Determines keyframes deterministically (not randomly)
6. ✅ Supports 4 domain classification exactly
7. ✅ Risk score calibration formula: `clamp(max(heuristic, 0.6*gpt_severity + 0.4*heuristic), 0, 1)`
8. ✅ Per-frame GPT removed; vision classification once per video

---

## Files Modified

- **Created**: `utils/vision_classifier.py` (248 lines)
- **Modified**: `utils/signal_detector.py` (removed ~100 lines of GPT code, kept ~550 lines heuristic)
- **Modified**: `app.py` (replaced `/analyze-video` endpoint, added imports)

---

## Next Steps (Optional)

1. **Async GPT Calls**: If latency becomes an issue, move GPT calls to a background task
2. **Keyframe Optimization**: Refine thresholds for motion/fire/fighting heuristics
3. **Domain Fine-tuning**: Adjust GPT prompts based on real-world test results
4. **Caching**: Cache signal analysis per video to avoid re-processing on retries
5. **Metrics**: Log domain accuracy vs. ground truth for model improvement
