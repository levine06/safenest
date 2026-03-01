"""
SafeNest Backend - Flask API

Privacy-Preserving Child Safety Risk Intelligence System

This backend provides REST API endpoints for:
  - Risk analysis (POST /analyze-risk)
  - Video analysis (POST /analyze-video)
  - Alert history retrieval (GET /alerts)
  
All data is anonymized and alerts are auto-purged after 15 minutes
to ensure privacy-by-design.
"""
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from utils.risk_scorer import analyze_risk, get_danger_rank
from utils.video_processor import extract_frames, detect_motion, detect_faces, detect_people_count, get_frame_brightness, detect_fire_smoke, detect_color_anomaly, detect_crowd_density_zones, cleanup_video
from utils.signal_detector import detect_pose_and_hands, detect_fall, detect_rapid_motion_pose, detect_aggressive_stance, detect_contact_and_fighting, detect_crowd_panic, generate_signal_features
from utils.domain_classifier import classify_domain_from_signals, signals_to_boolean_dict
from utils.vision_classifier import select_keyframes, classify_video_with_vision
import os
import tempfile
import cv2

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes (frontend communication)

# In-memory alert storage
alerts = []

# Configuration
ALERT_RETENTION_MINUTES = 15


def purge_old_alerts():
    """Remove alerts older than ALERT_RETENTION_MINUTES."""
    global alerts
    cutoff_time = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(minutes=ALERT_RETENTION_MINUTES)
    # Parse ISO timestamp and filter
    alerts = [
        alert
        for alert in alerts
        if datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00")) > cutoff_time
    ]


@app.route("/analyze-risk", methods=["POST"])
def analyze_risk_endpoint():
    """
    POST /analyze-risk
    
    Analyze safety signals and compute risk score for specified domain.
    
    Request JSON:
    {
        "signals": { ...booleans... },
        "domain": "child_safety" (optional, defaults to child_safety),
        "context": {} (optional)
    }
    
    Response JSON includes domain field in addition to other fields.
    """
    try:
        data = request.get_json()
        
        if not data or "signals" not in data:
            return jsonify({"error": "Missing 'signals' in request"}), 400
        
        signals = data.get("signals", {})
        domain = data.get("domain", "child_safety")  # Default to child_safety
        context = data.get("context", {})
        
        # Analyze risk with domain-specific configuration
        result = analyze_risk(signals, domain=domain, context=context)
        
        # Add alert ID, domain, and store in memory
        alert_id = len(alerts) + 1
        result["alert_id"] = alert_id
        result["domain"] = domain
        alerts.append(result)
        
        # Purge old alerts before returning
        purge_old_alerts()
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/alerts", methods=["GET"])
def get_alerts():
    """
    GET /alerts
    
    Retrieve recent alerts (most recent first).
    Automatically purges alerts older than ALERT_RETENTION_MINUTES.
    
    Response JSON:
    {
        "alerts": [
            {
                "alert_id": int,
                "risk_score": float,
                "danger_rank": str,
                "danger_tier": str,
                "triggered_signals": [str],
                "escalation_probability": float,
                "timestamp": str,
                "confidence": float
            },
            ...
        ],
        "count": int,
        "retention_minutes": int
    }
    """
    try:
        # Purge old alerts first
        purge_old_alerts()
        
        # Sort by timestamp descending (most recent first)
        sorted_alerts = sorted(
            alerts,
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        return jsonify({
            "alerts": sorted_alerts,
            "count": len(sorted_alerts),
            "retention_minutes": ALERT_RETENTION_MINUTES,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/alerts", methods=["DELETE"])
def delete_alerts():
    """
    DELETE /alerts
    
    Clear all alerts from the alert history.
    
    Response JSON:
    {
        "status": "cleared",
        "alerts_cleared": int
    }
    """
    global alerts
    try:
        count = len(alerts)
        alerts = []
        
        return jsonify({
            "status": "cleared",
            "alerts_cleared": count,
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze-video", methods=["POST"])
def analyze_video_endpoint():
    """
    POST /analyze-video
    
    Analyze CCTV video to detect safety signals and classify domain using vision AI.
    Uses up to 3 keyframes analyzed by GPT-4o-mini for domain classification.
    
    Request: Multipart form-data with video file
    
    Response JSON:
    {
        "status": "success",
        "primary_domain": str,
        "domain_probabilities": {...},
        "domain_confidence": float,
        "gpt_severity": float,
        "heuristic_risk_score": float,
        "final_risk_score": float,
        "keyframes_used": [{timestamp, reasons: [str]}, ...],
        "gpt_used": bool,
        "signals_detected": {...},
        "timeline": [...],
        "frames_analyzed": int,
        "video_duration": float
    }
    """
    try:
        # Check if video file is in request
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # Save video to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            video_file.save(tmp.name)
            temp_video_path = tmp.name
        
        try:
            # Extract frames from video
            frames_list = extract_frames(temp_video_path, sample_interval=1, max_frames=20)
            
            if not frames_list:
                return jsonify({"error": "Could not extract frames from video"}), 400
            
            # Analyze frames
            timeline = []
            all_signal_features = {}
            prev_landmarks = None
            prev_frame = None
            
            for frame_data in frames_list:
                frame = frame_data['frame']
                timestamp = frame_data['timestamp']
                
                # ===== BASIC FRAME ANALYSIS =====
                frame_brightness = get_frame_brightness(frame)
                face_analysis = detect_faces(frame)
                people_analysis = detect_people_count(frame)
                
                # Motion analysis
                motion_analysis = {'motion_detected': False, 'motion_intensity': 0, 'motion_areas': 0}
                if prev_frame is not None:
                    motion_analysis = detect_motion(prev_frame, frame)
                
                # ===== NEW CCTV-SPECIFIC ANALYSIS =====
                
                # Fire/smoke detection
                fire_smoke_analysis = detect_fire_smoke(frame)
                
                # Color anomaly (red dominance, flashing)
                color_analysis = detect_color_anomaly(frame)
                
                # Crowd density zones (for panic detection)
                crowd_zones = detect_crowd_density_zones(frame, face_analysis['face_positions'])
                
                # ===== POSE & ACTIVITY ANALYSIS =====
                
                # Pose and hand detection
                pose_hand_analysis = detect_pose_and_hands(frame)
                
                # Fall detection
                fall_analysis = detect_fall(pose_hand_analysis['pose_landmarks'])
                
                # Aggressive stance detection
                aggressive_analysis = detect_aggressive_stance(pose_hand_analysis['pose_landmarks'])
                
                # Rapid motion detection
                rapid_motion = {'rapid_motion_detected': False, 'motion_intensity': 0}
                if prev_landmarks is not None:
                    rapid_motion = detect_rapid_motion_pose(prev_landmarks, pose_hand_analysis['pose_landmarks'])
                
                # Fighting/contact detection
                fighting_analysis = detect_contact_and_fighting(
                    prev_landmarks,
                    pose_hand_analysis['pose_landmarks'],
                    face_analysis['faces_detected']
                )
                
                # Crowd panic detection
                panic_analysis = detect_crowd_panic(
                    motion_analysis.get('motion_intensity', 0),
                    face_analysis['faces_detected'],
                    people_analysis['crowd_density']
                )
                
                # ===== AGGREGATE FRAME ANALYSIS =====
                frame_analysis = {
                    # Brightness
                    **frame_brightness,
                    # Motion
                    **motion_analysis,
                    # People detection
                    'faces_detected': face_analysis['faces_detected'],
                    'crowd_density': people_analysis['crowd_density'],
                    # Fall
                    'fall_detected': fall_analysis['fall_detected'],
                    # Rapid motion (pose)
                    'rapid_motion_intensity': rapid_motion['motion_intensity'],
                    # Fire/smoke
                    'fire_smoke_probability': fire_smoke_analysis['fire_smoke_probability'],
                    'has_orange_red': fire_smoke_analysis['has_orange_red'],
                    # Color anomalies
                    'red_dominance': color_analysis['red_dominance'],
                    'is_flashing': color_analysis['is_flashing'],
                    # Aggressive behavior
                    'aggressive_stance_probability': aggressive_analysis['aggressive_stance_probability'],
                    # Fighting
                    'fighting_probability': fighting_analysis['fighting_probability'],
                    'contact_detected': fighting_analysis['contact_detected'],
                    'contact_impact_intensity': fighting_analysis['contact_impact_intensity'],
                    # Crowd issues
                    'crowd_panic_probability': panic_analysis['crowd_panic_probability'],
                    'is_chaotic': panic_analysis['is_chaotic'],
                    'crowd_vulnerability': panic_analysis['crowd_vulnerability'],
                }
                
                # Generate signal features for this frame (heuristic only now)
                signal_features = generate_signal_features(frame_analysis)

                # Aggregate all signals (keep max confidence score per signal)
                for signal, score in signal_features.items():
                    if isinstance(score, (int, float)):
                        all_signal_features[signal] = max(all_signal_features.get(signal, 0), score)
                
                # Domain classification for this frame
                frame_domain = classify_domain_from_signals(
                    signal_features, 
                    frame_analysis,
                    {'faces_detected': face_analysis['faces_detected']}
                )
                
                # STEP 2: Estimate face area for keyframe selection clarity metric
                # Face area based on number and confidence of detected faces
                face_area_estimate = min(1.0, face_analysis['faces_detected'] * 0.3) if face_analysis['faces_detected'] > 0 else 0
                
                timeline.append({
                    'timestamp': timestamp,
                    'domain': frame_domain['primary_domain'],
                    'domain_confidence': float(frame_domain['confidence']),
                    'signals': signal_features,
                    'motion_intensity': motion_analysis['motion_intensity'],
                    'brightness': frame_analysis.get('brightness', 0.5),
                    'face_area_estimate': face_area_estimate
                })
                
                prev_frame = frame
                prev_landmarks = pose_hand_analysis['pose_landmarks']
            
            # ===== HEURISTIC DOMAIN CLASSIFICATION =====
            
            max_motion = max([t['motion_intensity'] for t in timeline], default=0)
            heuristic_domain = classify_domain_from_signals(
                all_signal_features,
                {
                    'motion_intensity': max_motion,
                    'is_dark': any(t['motion_intensity'] < 0.1 for t in timeline),
                    'crowd_density': max([all_signal_features.get('adult_loitering_detected', 0)], default=0),
                    'fire_smoke_probability': all_signal_features.get('fire_smoke_detected', 0),
                    'has_orange_red': any('fire_glow' in s for s in all_signal_features)
                },
                {'faces_detected': max([t.get('signal', {}).get('adult_loitering_detected', 0) for t in timeline], default=0)}
            )
            
            # ===== HEURISTIC RISK SCORE =====
            heuristic_risk_result = analyze_risk(all_signal_features, domain=heuristic_domain['primary_domain'])
            heuristic_risk_score = heuristic_risk_result['risk_score'] / 100.0  # Convert to 0-1 scale
            
            # ===== VISION-BASED CLASSIFICATION WITH GPT-4O-MINI =====
            
            keyframes_data = select_keyframes(timeline, frames_list)
            gpt_result = classify_video_with_vision(keyframes_data, all_signal_features, timeline_data=timeline)
            
            # Extract results with graceful fallback
            gpt_used = gpt_result.get('gpt_used', False)
            primary_domain = gpt_result.get('primary_domain', heuristic_domain['primary_domain'])
            domain_probabilities = gpt_result.get('domain_probabilities', {
                'child_safety': 0.25,
                'elder_safety': 0.25,
                'environmental_hazard': 0.25,
                'crime': 0.25
            })
            gpt_severity = gpt_result.get('severity', 0.0)
            
            # If GPT failed, fall back to heuristic domain
            if not gpt_used:
                primary_domain = heuristic_domain['primary_domain']
                domain_probabilities = {
                    'child_safety': 0.0,
                    'elder_safety': 0.0,
                    'environmental_hazard': 0.0,
                    'crime': 0.0
                }
                domain_probabilities[primary_domain] = 1.0
                gpt_severity = heuristic_risk_score
            
            # ===== RISK SCORE CALIBRATION =====
            # Internal scale: 0-1
            # final_risk_score = clamp(max(heuristic_risk, 0.6*gpt_severity + 0.4*heuristic_risk), 0, 1)
            calibrated_risk = 0.6 * gpt_severity + 0.4 * heuristic_risk_score
            final_risk_score = max(heuristic_risk_score, calibrated_risk)
            final_risk_score = max(0.0, min(1.0, final_risk_score))  # Clamp to [0, 1]
            
            # ===== BUILD RESPONSE =====
            
            # Prepare keyframes_used data for response
            keyframes_used = []
            for kf in keyframes_data:
                keyframes_used.append({
                    'timestamp': float(kf['timestamp']),
                    'reasons': kf['reasons']
                })
            
            # Convert final_risk_score from 0-1 to 0-100 scale for API response
            final_risk_score_100 = final_risk_score * 100.0
            danger_rank, danger_tier = get_danger_rank(final_risk_score_100)
            
            response = {
                'status': 'success',
                'primary_domain': primary_domain,
                'domain_probabilities': domain_probabilities,
                'domain_confidence': float(max(domain_probabilities.values())) if domain_probabilities else 0.25,
                'gpt_severity': float(gpt_severity),  # Internal 0-1 scale
                'heuristic_risk_score': float(heuristic_risk_score),  # Internal 0-1 scale
                'final_risk_score': final_risk_score_100,  # UI scale 0-100
                'risk_score': final_risk_score_100,  # UI scale 0-100 (Crisis Risk Index)
                'keyframes_used': keyframes_used,
                'gpt_used': gpt_used,
                'signals_detected': {k: float(v) for k, v in all_signal_features.items() if isinstance(v, (int, float))},
                'danger_rank': danger_rank,
                'danger_tier': danger_tier,
                'escalation_probability': heuristic_risk_result['escalation_probability'],
                'triggered_signals': heuristic_risk_result['triggered_signals'],
                'reasoning': gpt_result.get('reasoning', heuristic_domain['reasoning']),
                'key_observations': gpt_result.get('key_observations', []),
                'timeline': timeline,
                'frames_analyzed': len(frames_list),
                'video_duration': frames_list[-1]['timestamp'] if frames_list else 0
            }
            
            return jsonify(response), 200
        
        finally:
            # Clean up temp video file
            cleanup_video(temp_video_path)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "SafeNest Backend",
        "alerts_in_memory": len(alerts)
    }), 200


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with API documentation."""
    return jsonify({
        "service": "SafeNest - Privacy-Preserving Child Safety Risk Intelligence",
        "version": "2.0.0",
        "endpoints": {
            "POST /analyze-risk": "Analyze safety signals and compute risk score",
            "POST /analyze-video": "Analyze CCTV video and detect domain/signals",
            "GET /alerts": "Retrieve recent alerts (with auto-purge)",
            "DELETE /alerts": "Clear all alerts",
            "GET /health": "Health check",
            "GET /": "This message"
        },
        "retention_minutes": ALERT_RETENTION_MINUTES,
        "note": "All data is anonymized. Alerts auto-purge after 15 minutes.",
    }), 200


if __name__ == "__main__":
    # Run Flask development server
    print("🚀 SafeNest Backend starting on http://localhost:5001")
    print(f"⏱️  Alert retention: {ALERT_RETENTION_MINUTES} minutes")
    print("✅ CORS enabled for frontend on http://localhost:3000")
    app.run(debug=True, host="0.0.0.0", port=5001)
