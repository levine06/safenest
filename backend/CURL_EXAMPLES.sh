#!/bin/bash
# SafeNest Vision-Based Video Classification - Curl Examples

# ============================================================================
# SETUP
# ============================================================================
# Make sure backend is running:
#   cd /Users/levine/deeplearningweek/safenest/backend
#   /Users/levine/deeplearningweek/.venv/bin/python app.py

BACKEND_URL="http://localhost:5001"

# ============================================================================
# EXAMPLE 1: Simple Video Upload (with pretty output)
# ============================================================================
echo "=== Example 1: Analyze Video ==="
echo "Command:"
echo "curl -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@/path/to/video.mp4\" | jq '.'"
echo ""
echo "Running..."
echo ""

# Replace with actual video path
curl -s -X POST "$BACKEND_URL/analyze-video" \
  -F "video=@/Users/levine/Videos/sample.mp4" \
  2>/dev/null | jq '.' 2>/dev/null || echo "Note: No video available. Provide actual video file."

# ============================================================================
# EXAMPLE 2: Extract Key Fields Only
# ============================================================================
echo ""
echo "=== Example 2: View Key Results ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '{'"
echo "    gpt_used,"
echo "    primary_domain,"
echo "    domain_confidence,"
echo "    final_risk_score,"
echo "    keyframes_used,"
echo "    key_observations"
echo "  }'"
echo ""

# ============================================================================
# EXAMPLE 3: Check GPT Classification
# ============================================================================
echo "=== Example 3: View GPT Classification ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '{'"
echo "    gpt_used,"
echo "    primary_domain,"
echo "    severity: .gpt_severity,"
echo "    probabilities: .domain_probabilities,"
echo "    observations: .key_observations"
echo "  }'"
echo ""

# ============================================================================
# EXAMPLE 4: View Risk Score Breakdown
# ============================================================================
echo "=== Example 4: View Risk Score Breakdown ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '{'"
echo "    heuristic_risk_score,"
echo "    gpt_severity,"
echo "    final_risk_score,"
echo "    danger_tier,"
echo "    escalation_probability"
echo "  }'"
echo ""
echo "Expected: final_risk_score >= max(heuristic_risk_score, calibrated)"
echo ""

# ============================================================================
# EXAMPLE 5: View Keyframes Used
# ============================================================================
echo "=== Example 5: View Selected Keyframes ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '{'"
echo "    keyframes_used,"
echo "    total_keyframes: (.keyframes_used | length),"
echo "    frames_analyzed"
echo "  }'"
echo ""
echo "Expected:"
echo "  - keyframes_used: 1-3 items"
echo "  - Each has timestamp and reasons (max_motion, max_fire_smoke, max_fighting, fall_detected)"
echo ""

# ============================================================================
# EXAMPLE 6: Save Full Response to File
# ============================================================================
echo "=== Example 6: Save Response to JSON File ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" > response.json"
echo ""
echo "View with:"
echo "  cat response.json | jq '.'"
echo "  # or for specific field:"
echo "  jq '.primary_domain' response.json"
echo ""

# ============================================================================
# EXAMPLE 7: Extract Observations
# ============================================================================
echo "=== Example 7: View AI Observations ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '.key_observations[]'"
echo ""
echo "Expected output (if gpt_used=true):"
echo "  \"Visible flames and heavy smoke in frame 5\"..."
echo "  \"Multiple people detected in chaotic movement\"..."
echo "  \"Signs of physical contact and aggression\"..."
echo ""

# ============================================================================
# EXAMPLE 8: Check Domain Probabilities Sum to 1.0
# ============================================================================
echo "=== Example 8: Validate Domain Probabilities ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "  -F \"video=@video.mp4\" | jq '"
echo "    .domain_probabilities | values | add"
echo "  '"
echo ""
echo "Expected: 1.0 (or very close, e.g., 0.99-1.01)"
echo ""

# ============================================================================
# EXAMPLE 9: Test Fallback Mode (without API key)
# ============================================================================
echo "=== Example 9: Test Heuristic Fallback ==="
echo "Command (to test fallback, unset API key first):"
echo "  unset OPENAI_API_KEY"
echo "  curl -s -X POST $BACKEND_URL/analyze-video \\"
echo "    -F \"video=@video.mp4\" | jq '.gpt_used'"
echo ""
echo "Expected when API key not set:"
echo "  false (gpt_used=false)"
echo "  Domain classification from heuristics only"
echo "  final_risk_score = heuristic_risk_score"
echo ""

# ============================================================================
# EXAMPLE 10: One-Liner with Full Response Analysis
# ============================================================================
echo "=== Example 10: Complete Analysis One-Liner ==="
echo "Command:"
echo "curl -s -X POST $BACKEND_URL/analyze-video -F \"video=@video.mp4\" | \\"
echo "  jq '{'"
echo "    status: .status,"
echo "    gpt_used: .gpt_used,"
echo "    domain: .primary_domain,"
echo "    confidence: .domain_confidence,"
echo "    risk: .final_risk_score,"
echo "    keyframes: (.keyframes_used | map({ts: .timestamp, reasons}))"
echo "    observations: (.key_observations | length) > 0 | \"Yes\" // \"No\""
echo "  }'"
echo ""

# ============================================================================
# HELPFUL SCRIPTS
# ============================================================================
echo "=== Helpful Shell Functions ==="
echo ""
echo "Add to ~/.zshrc or ~/.bashrc:"
echo ""
cat << 'EOF'
# Analyze CCTV video with SafeNest
safenest_analyze() {
    local video_file="${1:?Usage: safenest_analyze <video_file>}"
    curl -s -X POST http://localhost:5001/analyze-video \
        -F "video=@$video_file" | jq '.'
}

# Quick summary
safenest_summary() {
    local video_file="${1:?Usage: safenest_summary <video_file>}"
    curl -s -X POST http://localhost:5001/analyze-video \
        -F "video=@$video_file" | jq '{
            gpt_used,
            primary_domain,
            final_risk_score,
            keyframes: (.keyframes_used | length),
            observations: .key_observations
        }'
}

# Check risk score breakdown
safenest_risk() {
    local video_file="${1:?Usage: safenest_risk <video_file>}"
    curl -s -X POST http://localhost:5001/analyze-video \
        -F "video=@$video_file" | jq '{
            heuristic: .heuristic_risk_score,
            gpt_severity: .gpt_severity,
            final: .final_risk_score,
            tier: .danger_tier
        }'
}

EOF

echo ""
echo "=== Testing Script ==="
echo ""
echo "#!/bin/bash"
echo "# test_video_analysis.sh"
echo ""
echo "TEST_VIDEO=\${1:-test_video.mp4}"
echo ""
echo "echo \"Analyzing \$TEST_VIDEO...\""
echo "curl -s -X POST http://localhost:5001/analyze-video \\"
echo "  -F \"video=@\$TEST_VIDEO\" | jq '{'"
echo "    status: .status,"
echo "    gpt_active: .gpt_used,"
echo "    threat_domain: .primary_domain,"
echo "    threat_level: .final_risk_score,"
echo "    certainty: .domain_confidence,"
echo "    key_evidence: .key_observations"
echo "  }'"
echo ""
