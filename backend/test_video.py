#!/usr/bin/env python3
"""
Test script to debug video processing and domain classification
"""
import sys
sys.path.insert(0, '/Users/levine/deeplearningweek/safenest/backend')

from utils.video_processor import extract_frames, detect_motion, detect_faces, detect_people_count, get_frame_brightness, detect_fire_smoke, detect_color_anomaly, detect_crowd_density_zones
from utils.signal_detector import detect_pose_and_hands, detect_fall, detect_rapid_motion_pose, detect_aggressive_stance, detect_contact_and_fighting, detect_crowd_panic, generate_signal_features
from utils.domain_classifier import classify_domain_from_signals, signals_to_boolean_dict
from utils.risk_scorer import analyze_risk
import json

video_path = '/Users/levine/deeplearningweek/safenest/videos/child_kidnapping.mov'

print(f"Testing video: {video_path}")
print("="*60)

try:
    print("\n1️⃣ Extracting frames...")
    frames_list = extract_frames(video_path, sample_interval=1, max_frames=5)
    print(f"✅ Extracted {len(frames_list)} frames")
    
    if not frames_list:
        print("❌ No frames extracted!")
        sys.exit(1)
    
    # Analyze first frame
    frame = frames_list[0]['frame']
    print("\n2️⃣ Analyzing first frame...")
    
    brightness = get_frame_brightness(frame)
    print(f"   Brightness: {brightness}")
    
    faces = detect_faces(frame)
    print(f"   Faces detected: {faces['faces_detected']}")
    
    people = detect_people_count(frame)
    print(f"   People estimated: {people['people_estimated']}")
    
    fire_smoke = detect_fire_smoke(frame)
    print(f"   Fire/smoke prob: {fire_smoke['fire_smoke_probability']:.2f}")
    
    print("\n3️⃣ Running pose/hand detection...")
    pose = detect_pose_and_hands(frame)
    print(f"   Pose landmarks: {'found' if pose['pose_landmarks'] else 'not found'}")
    
    print("\n4️⃣ Generating signal features...")
    frame_analysis = {
        **brightness,
        'motion_detected': False,
        'motion_intensity': 0,
        'motion_areas': 0,
        'faces_detected': faces['faces_detected'],
        'crowd_density': people['crowd_density'],
        'fall_detected': False,
        'rapid_motion_intensity': 0,
        'fire_smoke_probability': fire_smoke['fire_smoke_probability'],
        'has_orange_red': fire_smoke['has_orange_red'],
        'red_dominance': 0,
        'is_flashing': False,
        'aggressive_stance_probability': 0,
        'fighting_probability': 0,
        'contact_detected': False,
        'contact_impact_intensity': 0,
        'is_chaotic': False,
        'crowd_vulnerability': 0,
        'crowd_panic_probability': 0,
    }
    
    signal_features = generate_signal_features(frame_analysis)
    print(f"   Signals generated: {len(signal_features)} signals")
    for signal, score in signal_features.items():
        # only print numeric scores
        if isinstance(score, (int, float)) and score > 0.1:
            print(f"      - {signal}: {score:.2f}")
    
    print("\n5️⃣ Classifying domain...")
    domain_result = classify_domain_from_signals(signal_features, frame_analysis, faces)
    print(f"   Primary domain: {domain_result['primary_domain']}")
    print(f"   Confidence: {domain_result['confidence']:.2f}")
    print(f"   Domain probabilities:")
    for dom, prob in domain_result['domain_probabilities'].items():
        print(f"      - {dom}: {prob:.2f}")
    
    print("\n6️⃣ Computing risk score...")
    boolean_signals = signals_to_boolean_dict(signal_features, threshold=0.35)
    risk_result = analyze_risk(boolean_signals, domain=domain_result['primary_domain'])
    print(f"   Risk score: {risk_result['risk_score']:.2f}")
    print(f"   Danger rank: {risk_result['danger_rank']}")
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
