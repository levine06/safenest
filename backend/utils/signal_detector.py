"""
Signal Detector Utility

Uses lightweight computer vision to detect safety signals from video frames.
"""

import numpy as np
import cv2
import os
import json
from openai import OpenAI

try:
    import mediapipe as mp
    MP_AVAILABLE = True
    mp_holistic = mp.solutions.holistic
except (ImportError, AttributeError):
    MP_AVAILABLE = False
    mp_holistic = None

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def detect_pose_and_hands(frame):
    """
    Detect body pose, hands, and face landmarks.
    Falls back to simpler detection if MediaPipe unavailable.
    
    Args:
        frame (np.ndarray): Video frame
    
    Returns:
        dict: {
            'pose_landmarks': list or None,
            'hand_landmarks': dict {left: list, right: list},
            'face_landmarks': list or None,
            'detection_confidence': float
        }
    """
    if MP_AVAILABLE and mp_holistic:
        try:
            with mp_holistic.Holistic(
                static_image_mode=False,
                model_complexity=0,  # Lightweight
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as holistic:
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = holistic.process(frame_rgb)
                
                return {
                    'pose_landmarks': results.pose_landmarks,
                    'hand_landmarks': {
                        'left': results.left_hand_landmarks,
                        'right': results.right_hand_landmarks
                    },
                    'face_landmarks': results.face_landmarks,
                    'detection_confidence': 0.7
                }
        except Exception as e:
            print(f"Warning: MediaPipe detection failed: {e}")
    
    # Fallback: return empty detections
    return {
        'pose_landmarks': None,
        'hand_landmarks': {'left': None, 'right': None},
        'face_landmarks': None,
        'detection_confidence': 0.0
    }


def detect_fall(pose_landmarks):
    """
    Detect if person has fallen based on pose.
    
    Heuristics:
    - Hip below knee level = falling/fallen
    - Person on ground (very low pose)
    
    Args:
        pose_landmarks: MediaPipe pose landmarks
    
    Returns:
        dict: {
            'fall_detected': bool,
            'fall_confidence': float (0-1)
        }
    """
    if pose_landmarks is None:
        return {'fall_detected': False, 'fall_confidence': 0}
    
    landmarks = pose_landmarks.landmark
    
    # Get key joint positions (in relative coordinates 0-1)
    hip_y = landmarks[23].y if len(landmarks) > 23 else 1
    knee_y = landmarks[26].y if len(landmarks) > 26 else 1
    ankle_y = landmarks[28].y if len(landmarks) > 28 else 1
    
    # If hip is significantly below knee, likely fallen
    if hip_y > knee_y + 0.15:
        return {'fall_detected': True, 'fall_confidence': 0.85}
    
    # If all joints very low (y > 0.8), person on ground
    if hip_y > 0.7 and knee_y > 0.7 and ankle_y > 0.7:
        return {'fall_detected': True, 'fall_confidence': 0.7}
    
    return {'fall_detected': False, 'fall_confidence': 0}


def detect_rapid_motion_pose(prev_landmarks, curr_landmarks):
    """
    Detect rapid motion by comparing pose landmarks between frames.
    
    Args:
        prev_landmarks: Previous frame pose landmarks
        curr_landmarks: Current frame pose landmarks
    
    Returns:
        dict: {
            'rapid_motion_detected': bool,
            'motion_intensity': float (0-1)
        }
    """
    if prev_landmarks is None or curr_landmarks is None:
        return {'rapid_motion_detected': False, 'motion_intensity': 0}
    
    prev_pts = prev_landmarks.landmark
    curr_pts = curr_landmarks.landmark
    
    # Calculate average displacement of key joints
    displacements = []
    for i in [11, 12, 23, 24]:  # Shoulders and hips
        if i < len(prev_pts) and i < len(curr_pts):
            dx = (curr_pts[i].x - prev_pts[i].x) ** 2
            dy = (curr_pts[i].y - prev_pts[i].y) ** 2
            displacement = (dx + dy) ** 0.5
            displacements.append(displacement)
    
    if displacements:
        avg_displacement = np.mean(displacements)
        # Normalize (0.1 = significant motion)
        motion_intensity = min(1.0, avg_displacement * 10)
        rapid_motion = motion_intensity > 0.3
        
        return {
            'rapid_motion_detected': rapid_motion,
            'motion_intensity': motion_intensity
        }
    
    return {'rapid_motion_detected': False, 'motion_intensity': 0}


def detect_hand_activity(hand_landmarks_dict):
    """
    Detect hand activity (open hands, gestures).
    
    Args:
        hand_landmarks_dict: Dict with 'left' and 'right' hand landmarks
    
    Returns:
        dict: {
            'hand_activity_detected': bool,
            'left_hand_open': bool,
            'right_hand_open': bool,
            'gesture_confidence': float
        }
    """
    left_hand = hand_landmarks_dict.get('left')
    right_hand = hand_landmarks_dict.get('right')
    
    left_open = check_hand_open(left_hand)
    right_open = check_hand_open(right_hand)
    
    return {
        'hand_activity_detected': left_open or right_open,
        'left_hand_open': left_open,
        'right_hand_open': right_open,
        'gesture_confidence': 0.6
    }


def check_hand_open(hand_landmarks):
    """
    Check if hand is open (spread fingers).
    
    Args:
        hand_landmarks: MediaPipe hand landmarks
    
    Returns:
        bool: True if hand appears open
    """
    if hand_landmarks is None:
        return False
    
    landmarks = hand_landmarks.landmark
    
    # Calculate distances between finger tips and palm center
    if len(landmarks) >= 21:
        palm_x = np.mean([lm.x for lm in landmarks[:9]])
        palm_y = np.mean([lm.y for lm in landmarks[:9]])
        
        # Finger tips: 4, 8, 12, 16, 20
        finger_tips = [4, 8, 12, 16, 20]
        distances = []
        for tip in finger_tips:
            dist = ((landmarks[tip].x - palm_x) ** 2 + (landmarks[tip].y - palm_y) ** 2) ** 0.5
            distances.append(dist)
        
        avg_distance = np.mean(distances)
        return avg_distance > 0.1  # Open if fingers spread far from palm
    
    return False


def detect_person_proximity(face_landmarks_list):
    """
    Detect if multiple people are very close (proximity detection).
    
    Args:
        face_landmarks_list: List of detected faces
    
    Returns:
        dict: {
            'people_count': int,
            'close_proximity': bool,
            'proximity_score': float (0-1)
        }
    """
    if not face_landmarks_list or len(face_landmarks_list) == 0:
        return {'people_count': 0, 'close_proximity': False, 'proximity_score': 0}
    
    people_count = len(face_landmarks_list)
    
    # If multiple people detected in close frame area, consider close proximity
    close_proximity = people_count >= 2
    proximity_score = min(1.0, (people_count - 1) / 3.0) if people_count > 1 else 0
    
    return {
        'people_count': people_count,
        'close_proximity': close_proximity,
        'proximity_score': proximity_score
    }


def detect_aggressive_stance(pose_landmarks):
    """
    Detect aggressive body posture indicators.
    
    Aggressive stances:
    - Arms raised/extended
    - Bent posture (tension)
    - Shoulder elevation
    - Forward lean
    
    Args:
        pose_landmarks: MediaPipe pose landmarks
    
    Returns:
        dict: {
            'aggressive_stance_probability': float (0-1),
            'arms_raised': bool,
            'forward_lean': bool
        }
    """
    if pose_landmarks is None:
        return {
            'aggressive_stance_probability': 0.0,
            'arms_raised': False,
            'forward_lean': False
        }
    
    landmarks = pose_landmarks.landmark
    
    try:
        # Key points: 11, 12 shoulders, 13, 14 elbows, 15, 16 wrists
        # 23, 24 hips, 25, 26 knees
        
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_elbow = landmarks[13]
        right_elbow = landmarks[14]
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        hip = landmarks[23]
        
        # Arms raised: wrists above shoulders
        arms_raised = (left_wrist.y < left_shoulder.y - 0.1) or \
                      (right_wrist.y < right_shoulder.y - 0.1)
        
        # Forward lean: shoulders forward of hips
        forward_lean = (left_shoulder.x < hip.x - 0.15) or \
                       (right_shoulder.x > hip.x + 0.15)
        
        # Arm extension: elbows far from shoulders
        left_arm_dist = ((left_elbow.x - left_shoulder.x) ** 2 + 
                        (left_elbow.y - left_shoulder.y) ** 2) ** 0.5
        right_arm_dist = ((right_elbow.x - right_shoulder.x) ** 2 + 
                         (right_elbow.y - right_shoulder.y) ** 2) ** 0.5
        
        high_arm_extension = (left_arm_dist > 0.12) or (right_arm_dist > 0.12)
        
        # Calculate overall aggression score
        aggression_score = (
            (0.4 if arms_raised else 0) +
            (0.3 if forward_lean else 0) +
            (0.3 if high_arm_extension else 0)
        )
        
        return {
            'aggressive_stance_probability': aggression_score,
            'arms_raised': arms_raised,
            'forward_lean': forward_lean
        }
    except:
        return {
            'aggressive_stance_probability': 0.0,
            'arms_raised': False,
            'forward_lean': False
        }


def detect_contact_and_fighting(prev_landmarks, curr_landmarks, people_count):
    """
    Detect close contact and potential fighting indicators.
    
    Fighting signals:
    - Multiple people in close proximity
    - Rapid reciprocal motion (both moving fast)
    - Stance changes
    - Arm contact area
    
    Args:
        prev_landmarks: Previous frame pose
        curr_landmarks: Current frame pose
        people_count (int): Number of detected people
    
    Returns:
        dict: {
            'contact_detected': bool,
            'fighting_probability': float (0-1),
            'contact_impact_intensity': float (0-1)
        }
    """
    contact_detected = people_count >= 2
    
    # Estimate motion intensity change
    motion_change = 0.0
    if prev_landmarks and curr_landmarks:
        prev_pts = prev_landmarks.landmark
        curr_pts = curr_landmarks.landmark
        
        try:
            # Upper body (arms, shoulders, head)
            upper_body = [5, 6, 11, 12, 13, 14, 15, 16]  # Shoulders, elbows, wrists
            displacements = []
            
            for i in upper_body:
                if i < len(prev_pts) and i < len(curr_pts):
                    dx = (curr_pts[i].x - prev_pts[i].x) ** 2
                    dy = (curr_pts[i].y - prev_pts[i].y) ** 2
                    displacement = (dx + dy) ** 0.5
                    displacements.append(displacement)
            
            if displacements:
                motion_change = min(1.0, np.mean(displacements) * 15)
        except:
            pass
    
    # Fighting probability: multiple people + high motion intensity + contact
    fighting_prob = 0.0
    if contact_detected:
        fighting_prob = min(1.0, 0.3 + motion_change * 0.7)
    
    return {
        'contact_detected': contact_detected,
        'fighting_probability': fighting_prob,
        'contact_impact_intensity': motion_change
    }


def detect_crowd_panic(motion_intensity, faces_detected, crowd_density):
    """
    Detect signs of crowd panic or disorder.
    
    Panic indicators:
    - Many people present + erratic motion
    - Rapid density changes
    - Chaotic movement patterns
    
    Args:
        motion_intensity (float): Overall frame motion 0-1
        faces_detected (int): Number of people detected
        crowd_density (float): Crowd density 0-1
    
    Returns:
        dict: {
            'crowd_panic_probability': float (0-1),
            'is_chaotic': bool,
            'crowd_vulnerability': float (0-1)
        }
    """
    panic_prob = 0.0
    is_chaotic = False
    vulnerability = 0.0
    
    # Chaotic: Many people + high motion
    if faces_detected >= 3:
        if motion_intensity > 0.4:
            is_chaotic = True
            panic_prob = min(1.0, motion_intensity * 0.6)
            vulnerability = min(1.0, crowd_density * 1.5)
    
    # Extreme density can indicate crushing risk
    if crowd_density > 0.6:
        vulnerability = min(1.0, crowd_density * 1.2)
        panic_prob = min(1.0, panic_prob + 0.3)
    
    return {
        'crowd_panic_probability': panic_prob,
        'is_chaotic': is_chaotic,
        'crowd_vulnerability': vulnerability
    }


def classify_with_gpt4mini(frame_analysis, frame_context=""):
    """
    Use OpenAI GPT-4 Mini to classify video frames for crisis detection.
    
    Args:
        frame_analysis (dict): Frame analysis metrics
        frame_context (str): Optional description of what's happening in the frame
    
    Returns:
        dict: {
            'crisis_risk_index': float (0-1),
            'hazard_type': str,
            'confidence': float (0-1),
            'reasoning': str
        }
    """
    if not client:
        return {
            'crisis_risk_index': 0.0,
            'hazard_type': 'unknown',
            'confidence': 0.0,
            'reasoning': 'OpenAI API key not configured'
        }
    
    # Build detailed prompt with frame analysis
    prompt = f"""Analyze this video frame for safety threats and crises. Return a JSON response.

FRAME ANALYSIS DATA:
{format_frame_analysis_for_gpt(frame_analysis)}

CONTEXT: {frame_context if frame_context else 'General surveillance footage'}

Classify the threat level and provide:
1. crisis_risk_index: 0-1 (0=safe, 1=critical emergency)
2. hazard_type: Primary threat category (violence, fire, medical_emergency, crowd_panic, robbery, accident, none, etc.)
3. confidence: 0-1 confidence in your assessment
4. reasoning: Brief explanation

Return ONLY valid JSON, no markdown."""

    try:
        response = client.messages.create(
            model="gpt-4-mini",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        response_text = response.content[0].text
        
        # Parse JSON response
        result = json.loads(response_text)
        
        return {
            'crisis_risk_index': float(result.get('crisis_risk_index', 0.0)),
            'hazard_type': str(result.get('hazard_type', 'unknown')),
            'confidence': float(result.get('confidence', 0.0)),
            'reasoning': str(result.get('reasoning', ''))
        }
    
    except Exception as e:
        print(f"Error calling GPT-4 Mini: {e}")
        return {
            'crisis_risk_index': 0.0,
            'hazard_type': 'classification_error',
            'confidence': 0.0,
            'reasoning': f'API error: {str(e)}'
        }


def format_frame_analysis_for_gpt(frame_analysis):
    """Format frame analysis metrics as readable text for GPT-4 Mini."""
    return f"""- Motion Intensity: {frame_analysis.get('rapid_motion_intensity', 0):.2f}
- Fall Detected: {frame_analysis.get('fall_detected', False)}
- Aggressive Stance: {frame_analysis.get('aggressive_stance_probability', 0):.2f}
- Fighting Probability: {frame_analysis.get('fighting_probability', 0):.2f}
- People Count: {frame_analysis.get('people_count', 0)}
- Crowd Density: {frame_analysis.get('crowd_density', 0):.2f}
- Crowd Panic: {frame_analysis.get('crowd_panic_probability', 0):.2f}
- Fire/Smoke: {frame_analysis.get('fire_smoke_probability', 0):.2f}
- Brightness: {frame_analysis.get('brightness', 1.0):.2f}
- Motion Areas: {frame_analysis.get('motion_areas', 0)}
"""


def generate_signal_features(frame_analysis, frame_context=""):
    """
    Convert frame analysis metrics to signal feature dictionary.
    NOW INCLUDES GPT-4 MINI CLASSIFICATION.
    
    Args:
        frame_analysis (dict): Frame analysis with pose, motion, etc.
        frame_context (str): Optional video context for GPT-4 Mini
    
    Returns:
        dict: Signal feature scores (0-1 for each signal type) + crisis risk assessment
    """
    features = {
        # Original signals
        'distress_scream_detected': 0.0,
        'rapid_motion_detected': 0.0,
        'adult_loitering_detected': 0.0,
        'fall_detected': 0.0,
        'weapon_detected': 0.0,
        'smoke_detected': 0.0,
        # NEW CCTV signals
        'fighting_detected': 0.0,
        'aggressive_stance_detected': 0.0,
        'close_contact_detected': 0.0,
        'erratic_motion_detected': 0.0,
        'fire_smoke_detected': 0.0,
        'crowd_panic_detected': 0.0,
        'people_falling_detected': 0.0,
        'fire_glow_detected': 0.0,
        # NEW: GPT-4 Mini Classification
        'crisis_risk_index': 0.0,
        'gpt_hazard_type': 'none',
        'gpt_confidence': 0.0,
    }
    
    # ===== ORIGINAL SIGNALS =====
    
    # Rapid motion signal - more sensitive
    motion_intensity = frame_analysis.get('rapid_motion_intensity', 0)
    if motion_intensity > 0.15:
        features['rapid_motion_detected'] = min(1.0, motion_intensity * 2.0)
    
    # Fall detection signal - high confidence
    if frame_analysis.get('fall_detected', False):
        features['fall_detected'] = 0.95
    
    # Crowd density can indicate loitering
    crowd_density = frame_analysis.get('crowd_density', 0)
    if crowd_density > 0.1:
        features['adult_loitering_detected'] = min(1.0, crowd_density * 2.0)
    
    # Motion areas indicate activity
    motion_areas = frame_analysis.get('motion_areas', 0)
    if motion_areas > 1:
        features['rapid_motion_detected'] = min(1.0, features['rapid_motion_detected'] + 0.3)
    
    # Motion intensity from frame
    motion_detected = frame_analysis.get('motion_detected', False)
    if motion_detected:
        motion_int = frame_analysis.get('motion_intensity', 0)
        if motion_int > 0.05:
            features['rapid_motion_detected'] = min(1.0, max(features['rapid_motion_detected'], motion_int * 1.8))
    
    # Dark conditions can be suspicious
    if frame_analysis.get('is_dark', False):
        features['weapon_detected'] = 0.35
    
    brightness = frame_analysis.get('brightness', 1.0)
    if brightness < 0.3:
        features['weapon_detected'] = min(1.0, features['weapon_detected'] + 0.35)
    
    # ===== NEW CCTV SIGNALS =====
    
    # Fire/Smoke detection from color analysis
    fire_smoke_prob = frame_analysis.get('fire_smoke_probability', 0)
    if fire_smoke_prob > 0.1:
        features['fire_smoke_detected'] = min(1.0, fire_smoke_prob * 1.5)
    
    # Fire glow (orange/red dominance + brightness)
    red_dominance = frame_analysis.get('red_dominance', 0)
    if red_dominance > 0.2:
        features['fire_glow_detected'] = min(1.0, red_dominance * 1.2)
    
    # Aggressive stance detection
    aggressive_prob = frame_analysis.get('aggressive_stance_probability', 0)
    if aggressive_prob > 0.2:
        features['aggressive_stance_detected'] = min(1.0, aggressive_prob * 1.5)
    
    # Fighting/Contact detection
    fighting_prob = frame_analysis.get('fighting_probability', 0)
    if fighting_prob > 0.15:
        features['fighting_detected'] = min(1.0, fighting_prob * 1.8)
    
    contact_impact = frame_analysis.get('contact_impact_intensity', 0)
    if contact_impact > 0.2:
        features['fighting_detected'] = min(1.0, features['fighting_detected'] + contact_impact * 0.5)
    
    # Close contact indicator
    if frame_analysis.get('contact_detected', False) or frame_analysis.get('close_proximity', False):
        features['close_contact_detected'] = 0.4 + min(0.6, motion_intensity * 0.5)
    
    # Erratic motion (chaotic crowd movement)
    crowd_panic_prob = frame_analysis.get('crowd_panic_probability', 0)
    if crowd_panic_prob > 0.15:
        features['erratic_motion_detected'] = min(1.0, crowd_panic_prob * 1.5)
    
    # Crowd panic / vulnerability
    if frame_analysis.get('is_chaotic', False):
        features['crowd_panic_detected'] = min(1.0, crowd_panic_prob + 0.2)
    
    # People falling in crowd context
    if frame_analysis.get('fall_detected', False) and crowd_density > 0.3:
        features['people_falling_detected'] = 0.85
    
    # ===== GPT-4 MINI CLASSIFICATION =====
    gpt_classification = classify_with_gpt4mini(frame_analysis, frame_context)
    
    # Start with GPT index
    base_index = gpt_classification['crisis_risk_index']
    features['gpt_hazard_type'] = gpt_classification['hazard_type']
    features['gpt_confidence'] = gpt_classification['confidence']

    # Heuristic adjustments to boost and vary the index
    heuristic_index = 0.0
    # increase sensitivity: lower thresholds, bigger boosts
    if features['rapid_motion_detected'] > 0.3:
        heuristic_index = max(heuristic_index, 0.4)
    if features['fall_detected'] > 0.4:
        heuristic_index = max(heuristic_index, 0.5)
    if features['fire_smoke_detected'] > 0.3 or features['fire_glow_detected'] > 0.3:
        heuristic_index = max(heuristic_index, 0.7)
    if features['fighting_detected'] > 0.2 or features['aggressive_stance_detected'] > 0.2:
        heuristic_index = max(heuristic_index, 0.6)
    if features['crowd_panic_detected'] > 0.2:
        heuristic_index = max(heuristic_index, 0.6)
    # additional boost when multiple high signals present
    high_signals = sum(
        1 for s in ['rapid_motion_detected','fall_detected','fire_smoke_detected','fighting_detected','crowd_panic_detected']
        if features.get(s,0) > 0.5
    )
    if high_signals >= 2:
        heuristic_index = min(1.0, heuristic_index + 0.2)

    # combine indexes with stronger weight and random jitter
    combined = base_index * 1.5 + heuristic_index * 0.7
    jitter = np.random.uniform(-0.1, 0.1)
    final_index = min(max(combined + jitter, 0.0), 1.0)

    features['crisis_risk_index'] = final_index
    
    return features
