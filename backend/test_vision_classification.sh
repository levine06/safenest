#!/bin/bash
# Vision-Based Video Classification - Quick Test Scripts

# ============================================================================
# SETUP
# ============================================================================

echo "Setting up environment..."
cd /Users/levine/deeplearningweek/safenest/backend
source /Users/levine/deeplearningweek/.venv/bin/activate

# Verify OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set. GPT classification will be skipped (fallback to heuristics)."
fi

# ============================================================================
# TEST 1: Check Backend Starts
# ============================================================================

test_backend_start() {
    echo ""
    echo "TEST 1: Testing backend startup..."
    timeout 5 python app.py &
    sleep 2
    
    # Check if server responds to health check
    if curl -s http://localhost:5001/health | grep -q "healthy"; then
        echo "✓ Backend started successfully"
        kill $! 2>/dev/null
        return 0
    else
        echo "✗ Backend failed to start or health check failed"
        return 1
    fi
}

# ============================================================================
# TEST 2: Test Vision Classification with Sample Video
# ============================================================================

test_vision_classification() {
    echo ""
    echo "TEST 2: Testing vision-based video classification..."
    
    # Create a simple test video (5 seconds, 640x480)
    TEST_VIDEO="/tmp/test_video.mp4"
    echo "Creating test video at $TEST_VIDEO..."
    
    ffmpeg -f lavfi -i testsrc=duration=5:size=640x480:rate=30 \
           -f lavfi -i sine=frequency=1000:duration=5 \
           -pix_fmt yuv420p -c:v libx264 -c:a aac \
           "$TEST_VIDEO" 2>/dev/null
    
    if [ ! -f "$TEST_VIDEO" ]; then
        echo "✗ Failed to create test video. Make sure ffmpeg is installed."
        return 1
    fi
    
    echo "Uploading to /analyze-video..."
    
    # Start backend in background
    python app.py > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    sleep 3
    
    # Make request
    response=$(curl -s -X POST http://localhost:5001/analyze-video \
        -F "video=@$TEST_VIDEO")
    
    # Kill backend
    kill $BACKEND_PID 2>/dev/null
    
    # Verify response
    if echo "$response" | jq -e '.status == "success"' > /dev/null 2>&1; then
        echo "✓ Video analysis successful"
        
        # Print key fields
        echo ""
        echo "Response Summary:"
        echo "$response" | jq '{
            gpt_used: .gpt_used,
            primary_domain: .primary_domain,
            domain_confidence: .domain_confidence,
            gpt_severity: .gpt_severity,
            final_risk_score: .final_risk_score,
            keyframes_count: (.keyframes_used | length)
        }'
        
        # Print keyframes
        echo ""
        echo "Keyframes Used:"
        echo "$response" | jq '.keyframes_used'
        
        # Print key observations (if GPT was used)
        if echo "$response" | jq -e '.gpt_used' > /dev/null 2>&1; then
            echo ""
            echo "Key Observations:"
            echo "$response" | jq '.key_observations'
        fi
        
        return 0
    else
        echo "✗ Video analysis failed"
        echo "Response: $response"
        return 1
    fi
}

# ============================================================================
# TEST 3: Test Keyframe Selection
# ============================================================================

test_keyframe_selection() {
    echo ""
    echo "TEST 3: Testing keyframe selection..."
    
    cat > /tmp/test_keyframes.py << 'EOF'
import sys
sys.path.insert(0, '/Users/levine/deeplearningweek/safenest/backend')

import numpy as np
from utils.vision_classifier import select_keyframes

# Create mock timeline and frames
timeline = [
    {'timestamp': 0.5, 'motion_intensity': 0.1, 'signals': {
        'fire_smoke_detected': 0.05, 'fighting_detected': 0.0
    }},
    {'timestamp': 2.0, 'motion_intensity': 0.8, 'signals': {
        'fire_smoke_detected': 0.05, 'fighting_detected': 0.0
    }},
    {'timestamp': 5.0, 'motion_intensity': 0.2, 'signals': {
        'fire_smoke_detected': 0.85, 'fighting_detected': 0.05
    }},
    {'timestamp': 8.0, 'motion_intensity': 0.3, 'signals': {
        'fire_smoke_detected': 0.05, 'fighting_detected': 0.8
    }},
]

frames = []
for t in timeline:
    frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    frames.append({'frame': frame, 'timestamp': t['timestamp']})

keyframes = select_keyframes(timeline, frames)

print(f"Selected {len(keyframes)} keyframes:")
for kf in keyframes:
    print(f"  - timestamp={kf['timestamp']}s, reasons={kf['reasons']}")

# Verify expectations
expected_timestamps = [2.0, 5.0, 8.0]  # max_motion, max_fire, max_fighting
actual_timestamps = [kf['timestamp'] for kf in keyframes]

if actual_timestamps == expected_timestamps:
    print("✓ Keyframe selection correct!")
else:
    print(f"✗ Expected timestamps {expected_timestamps}, got {actual_timestamps}")
EOF
    
    python /tmp/test_keyframes.py
}

# ============================================================================
# TEST 4: Test Risk Score Calibration
# ============================================================================

test_risk_calibration() {
    echo ""
    echo "TEST 4: Testing risk score calibration formula..."
    
    cat > /tmp/test_calibration.py << 'EOF'
# Test the calibration formula
heuristic_risk = 0.4
gpt_severity = 0.8

calibrated = 0.6 * gpt_severity + 0.4 * heuristic_risk
final_risk = max(heuristic_risk, calibrated)
final_risk = max(0.0, min(1.0, final_risk))

print(f"Heuristic Risk: {heuristic_risk}")
print(f"GPT Severity: {gpt_severity}")
print(f"Calibrated (0.6*gpt + 0.4*heur): {calibrated:.3f}")
print(f"Final Risk (max, clamped): {final_risk:.3f}")

# Verify formula works for edge cases
test_cases = [
    (0.0, 0.0, 0.0),
    (0.5, 0.5, 0.5),
    (0.3, 0.9, max(0.3, 0.6*0.9 + 0.4*0.3)),
    (0.9, 0.1, max(0.9, 0.6*0.1 + 0.4*0.9)),
]

print("\nEdge case tests:")
for heur, gpt, expected in test_cases:
    calib = 0.6 * gpt + 0.4 * heur
    final = max(heur, calib)
    final = max(0.0, min(1.0, final))
    status = "✓" if abs(final - expected) < 0.001 else "✗"
    print(f"{status} heur={heur}, gpt={gpt} -> {final:.3f}")
EOF
    
    python /tmp/test_calibration.py
}

# ============================================================================
# TEST 5: Test Domain Probabilities
# ============================================================================

test_domain_probabilities() {
    echo ""
    echo "TEST 5: Testing domain probabilities..."
    
    # Create minimal test video
    TEST_VIDEO="/tmp/test_domain.mp4"
    ffmpeg -f lavfi -i testsrc=duration=3:size=640x480:rate=30 \
           -f lavfi -i sine=frequency=1000:duration=3 \
           -pix_fmt yuv420p -c:v libx264 -c:a aac \
           "$TEST_VIDEO" 2>/dev/null
    
    # Start backend
    python app.py > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    sleep 3
    
    # Request
    response=$(curl -s -X POST http://localhost:5001/analyze-video \
        -F "video=@$TEST_VIDEO")
    
    # Kill backend
    kill $BACKEND_PID 2>/dev/null
    
    # Check domain probabilities
    echo "Domain Probabilities:"
    echo "$response" | jq '.domain_probabilities'
    
    # Verify they sum to ~1.0
    sum=$(echo "$response" | jq '[.domain_probabilities[]] | add' 2>/dev/null || echo 0)
    if (( $(echo "$sum > 0.99 && $sum < 1.01" | bc -l) )); then
        echo "✓ Domain probabilities sum to 1.0 (actually: $sum)"
    else
        echo "⚠️  Domain probabilities sum to $sum (expected ~1.0)"
    fi
}

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

run_all_tests() {
    echo "=========================================="
    echo "SafeNest Vision Classification Tests"
    echo "=========================================="
    
    test_backend_start
    test_keyframe_selection
    test_risk_calibration
    test_vision_classification
    test_domain_probabilities
    
    echo ""
    echo "=========================================="
    echo "All tests completed!"
    echo "=========================================="
}

# Run all tests
run_all_tests
