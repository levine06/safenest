"""
Vision-Based Video Classifier

Uses OpenAI GPT-4o-mini with vision capabilities to classify CCTV videos
into one of 4 domains and assess severity based on keyframes and numeric signals.
"""

import base64
import json
import os
import cv2
from io import BytesIO

# Lazy import of OpenAI to avoid initialization issues
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
_client = None

def get_openai_client():
    """Get OpenAI client, initializing on first call."""
    global _client
    if _client is None and OPENAI_API_KEY:
        try:
            from openai import OpenAI
            _client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client: {e}", flush=True)
    return _client

print("DEBUG vision_classifier OPENAI_API_KEY set?", bool(OPENAI_API_KEY), flush=True)


def select_keyframes(timeline_data, frame_list):
    """
    Select up to 3 keyframes deterministically based on frame analysis.
    
    Prioritizes (STEP 2):
    1. BEST CLARITY FRAME: Largest face area OR highest brightness + lowest motion blur
    2. PEAK EVENT FRAME: Max of motion/fire/fighting
    3. AFTERMATH FRAME: Frame after fall OR highest crowd_panic
    
    Args:
        timeline_data (list): List of frame dicts with signals, motion_intensity, brightness, face_area_estimate
        frame_list (list): List of frame dicts with 'frame' (np.ndarray) and 'timestamp'
    
    Returns:
        list: Selected keyframes as dicts {
            'frame': np.ndarray,
            'timestamp': float,
            'reasons': [str],
            'frame_index': int
        }
    """
    if not timeline_data or not frame_list:
        return []
    
    selected_indices = set()
    keyframes = []
    
    # Map to store best value and its index for each criterion (STEP 2)
    best_clarity = {'score': -1, 'index': -1}  # NEW: Largest face OR best brightness/motion
    peak_event = {'score': -1, 'index': -1}    # Max motion/fire/fighting
    aftermath = {'score': -1, 'index': -1}     # First frame after fall OR max panic
    first_fall_idx = -1
    
    # Scan timeline to find optimal frames (STEP 2)
    for i, frame_data in enumerate(timeline_data):
        signals = frame_data.get('signals', {})
        
        # ===== STEP 2: Best Clarity Score =====
        # Priority: largest face area → highest brightness with low blur
        face_area = frame_data.get('face_area_estimate', 0)
        brightness = frame_data.get('brightness', 0.5)
        motion_blur_est = frame_data.get('motion_intensity', 0)  # Higher = more blur
        
        # Clarity score: face area (weighted high) + (brightness - blur penalty)
        clarity_score = face_area * 1000 + (brightness * 100 - motion_blur_est * 50)
        
        if clarity_score > best_clarity['score']:
            best_clarity['score'] = clarity_score
            best_clarity['index'] = i
        
        # ===== STEP 2: Peak Event Score =====
        # Max of motion/fire/fighting (event magnitude)
        motion = frame_data.get('motion_intensity', 0)
        fire_prob = signals.get('fire_smoke_detected', 0)
        fighting_prob = signals.get('fighting_detected', 0)
        event_score = max(motion, fire_prob, fighting_prob)
        
        if event_score > peak_event['score']:
            peak_event['score'] = event_score
            peak_event['index'] = i
        
        # ===== STEP 2: Aftermath Score =====
        # Frame immediately after fall OR highest crowd_panic
        if first_fall_idx == -1 and signals.get('fall_detected', 0) > 0.5:
            first_fall_idx = i
        
        panic_prob = signals.get('crowd_panic_detected', 0)
        if panic_prob > aftermath['score']:
            aftermath['score'] = panic_prob
            aftermath['index'] = i
    
    # If fall detected, prefer frame immediately after
    if first_fall_idx >= 0 and first_fall_idx + 1 < len(timeline_data):
        aftermath['index'] = first_fall_idx + 1
    
    # Build priority list: clarity, peak event, aftermath (max 3)
    candidates = [
        (best_clarity['index'], 'best_clarity'),
        (peak_event['index'], 'peak_event'),
        (aftermath['index'], 'aftermath')
    ]
    
    # Select unique indices (max 3)
    for idx, reason in candidates:
        if len(selected_indices) >= 3:
            break
        if idx >= 0 and idx not in selected_indices:
            selected_indices.add(idx)
    
    # Sort by index to maintain temporal order
    sorted_indices = sorted(selected_indices)
    
    # Build keyframes with reasons
    for idx in sorted_indices:
        if 0 <= idx < len(frame_list):
            frame_obj = frame_list[idx]
            
            # Determine reasons for this frame
            reasons = []
            if idx == best_clarity['index'] and best_clarity['score'] > 0:
                reasons.append('best_clarity')
            if idx == peak_event['index'] and peak_event['score'] > 0:
                reasons.append('peak_event')
            if idx == aftermath['index'] and aftermath['score'] > 0:
                reasons.append('aftermath')
            
            keyframes.append({
                'frame': frame_obj['frame'],
                'timestamp': frame_obj['timestamp'],
                'reasons': reasons if reasons else ['selected'],
                'frame_index': idx
            })
    
    return keyframes


def frame_to_base64_jpeg(frame, quality=85):
    """
    Convert a numpy frame (BGR) to base64-encoded JPEG data URL.
    
    Args:
        frame (np.ndarray): OpenCV BGR frame
        quality (int): JPEG quality (0-100)
    
    Returns:
        str: data:image/jpeg;base64,<encoded_data>
    """
    # Encode frame as JPEG
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        raise ValueError("Failed to encode frame as JPEG")
    
    # Convert to base64
    b64_data = base64.b64encode(buffer).decode('utf-8')
    
    return f"data:image/jpeg;base64,{b64_data}"


def build_signal_summary(all_signal_features):
    """
    Build a concise JSON summary of numeric signal features for GPT context.
    
    Args:
        all_signal_features (dict): Signal feature scores (0-1)
    
    Returns:
        dict: Summary of key signals with their values
    """
    summary = {}
    
    # Select key signals for summary
    key_signal_names = [
        'rapid_motion_detected',
        'fall_detected',
        'aggressive_stance_detected',
        'fighting_detected',
        'fire_smoke_detected',
        'adult_loitering_detected',
        'crowd_panic_detected',
        'close_contact_detected',
    ]
    
    for signal_name in key_signal_names:
        value = all_signal_features.get(signal_name, 0)
        if value > 0:  # Only include non-zero signals for clarity
            summary[signal_name] = round(float(value), 2)
    
    return summary


def generate_sequence_summary(timeline_data, all_signal_features):
    """
    STEP 3: Generate a deterministic narrative summary from heuristics.
    
    This helps GPT focus on "WHO" rather than "WHAT" and reduces crime false positives.
    
    Args:
        timeline_data (list): Timeline of frame data
        all_signal_features (dict): Aggregated heuristic signals
    
    Returns:
        str: Brief narrative summary (1-2 sentences)
    """
    # Extract key heuristic signals
    fall_detected = all_signal_features.get('fall_detected', 0) > 0.5
    fighting_detected = all_signal_features.get('fighting_detected', 0) > 0.3
    fire_smoke = all_signal_features.get('fire_smoke_detected', 0) > 0.3
    weapon_detected = all_signal_features.get('weapon_detected', 0) > 0.3
    crowd_panic = all_signal_features.get('crowd_panic_detected', 0) > 0.3
    
    # Estimate people count from timeline
    people_count = max([t.get('signals', {}).get('adult_loitering_detected', 0) 
                       for t in timeline_data], default=0)
    people_count_level = 'many' if people_count > 0.6 else ('some' if people_count > 0.2 else 'few')
    
    # Build narrative
    parts = []
    
    if fall_detected:
        parts.append(f"Person falls. {people_count_level} people visible.")
    elif fighting_detected:
        parts.append(f"Physical contact/fighting detected. {people_count_level} people involved.")
    elif fire_smoke:
        parts.append(f"Fire/smoke detected. Environmental hazard present.")
    elif crowd_panic:
        parts.append(f"Chaotic crowd movement detected. {people_count_level} people present.")
    else:
        parts.append(f"Video shows activity. {people_count_level} people detected.")
    
    if weapon_detected:
        parts.append("Possible weapon visible.")
    
    if not fire_smoke and not weapon_detected and not fighting_detected:
        parts.append("No visible fire or weapon detected.")
    
    return " ".join(parts)


def apply_consistency_constraints(gpt_result, all_signal_features, timeline_data):
    """
    STEP 4: Apply post-processing constraints to improve classification accuracy.
    
    1. Validate probabilities sum to ~1
    2. Downgrade "crime" if fighting/weapon/contact signals weak
    3. Boost "elder_safety" if fall + elderly-appearing person
    4. Handle edge cases
    
    Args:
        gpt_result (dict): Initial GPT response with domain_probabilities
        all_signal_features (dict): Heuristic signals
        timeline_data (list): Frame timeline for additional context
    
    Returns:
        dict: Adjusted gpt_result with corrected probabilities
    """
    probs = gpt_result.get('domain_probabilities', {}).copy()
    
    # ===== CONSTRAINT 1: Validate and normalize =====
    total = sum(probs.values())
    if total > 0:
        for domain in probs:
            probs[domain] = probs[domain] / total
    else:
        # Fallback uniform
        probs = {d: 0.25 for d in ['child_safety', 'elder_safety', 'environmental_hazard', 'crime']}
    
    # ===== CONSTRAINT 2: Downgrade crime if weak signals =====
    crime_prob = probs.get('crime', 0)
    if crime_prob > 0.5:
        fighting = all_signal_features.get('fighting_detected', 0)
        weapon = all_signal_features.get('weapon_detected', 0)
        contact = all_signal_features.get('close_contact_detected', 0)
        
        # If crime is high but combat signals are weak, downgrade
        if fighting < 0.3 and weapon < 0.3 and contact < 0.3:
            crime_prob = max(0.0, crime_prob - 0.3)
            # Redistribute probability to environmental/elder if fall detected
            if all_signal_features.get('fall_detected', 0) > 0.5:
                probs['elder_safety'] = min(1.0, probs.get('elder_safety', 0.25) + 0.2)
    
    # ===== CONSTRAINT 3: Boost elder_safety if fall + elderly apparent =====
    if all_signal_features.get('fall_detected', 0) > 0.5:
        # Check timeline for multiple falls or slow movement (elderly indicators)
        fall_count = sum(1 for t in timeline_data 
                        if t.get('signals', {}).get('fall_detected', 0) > 0.5)
        
        if fall_count >= 1:  # Clear fall signal
            probs['elder_safety'] = min(1.0, probs.get('elder_safety', 0.25) + 0.2)
    
    # ===== Normalize final probabilities =====
    total = sum(probs.values())
    if total > 0:
        for domain in probs:
            probs[domain] = max(0.0, min(1.0, probs[domain] / total))
    
    # Update result with adjusted probabilities
    gpt_result['domain_probabilities'] = probs
    
    # Update primary domain based on adjusted probabilities
    if probs:
        gpt_result['primary_domain'] = max(probs, key=probs.get)
    
    return gpt_result


def classify_video_with_vision(keyframes, all_signal_features, timeline_data=None, max_retries=2):
    """
    Classify video using OpenAI GPT-4o-mini with vision input on keyframes.
    
    Implements STEP 1, 3, and 4 improvements:
    - STEP 1: WHO-focused domain definitions with tie-breaker rules
    - STEP 3: Sequence summary narrative to reduce crime false positives
    - STEP 4: Post-processing consistency constraints
    
    Args:
        keyframes (list): List of keyframe dicts with 'frame', 'timestamp', 'reasons'
        all_signal_features (dict): Aggregated signal features from all frames
        timeline_data (list): Frame timeline for consistency constraints (optional)
        max_retries (int): Number of retries on JSON parse failure
    
    Returns:
        dict: {
            'gpt_used': bool,
            'primary_domain': str,
            'domain_probabilities': dict,
            'severity': float (0-1),
            'reasoning': str,
            'key_observations': [str],
            'error': str (optional)
        }
    """
    client = get_openai_client()
    
    if not client:
        return {
            'gpt_used': False,
            'error': 'OpenAI API key not configured',
            'primary_domain': 'child_safety',
            'domain_probabilities': {
                'child_safety': 0.25,
                'elder_safety': 0.25,
                'environmental_hazard': 0.25,
                'crime': 0.25
            },
            'severity': 0.0,
            'reasoning': 'API key not configured'
        }
    
    if not keyframes:
        return {
            'gpt_used': False,
            'error': 'No keyframes provided',
            'primary_domain': 'child_safety',
            'domain_probabilities': {
                'child_safety': 0.25,
                'elder_safety': 0.25,
                'environmental_hazard': 0.25,
                'crime': 0.25
            },
            'severity': 0.0,
            'reasoning': 'No keyframes provided'
        }
    
    # Build signal summary
    signal_summary = build_signal_summary(all_signal_features)
    signal_summary_json = json.dumps(signal_summary, indent=2)
    
    # STEP 3: Generate sequence summary narrative
    sequence_summary = ""
    if timeline_data:
        sequence_summary = generate_sequence_summary(timeline_data, all_signal_features)
    
    # ===== STEP 1: WHO-FOCUSED DOMAIN DEFINITIONS =====
    domain_definitions = """
DOMAIN DEFINITIONS (CLASSIFY BY "WHO IS AT RISK", NOT JUST "WHAT HAPPENED"):

1. child_safety:
   A CHILD (approx under 18) appears at risk or involved in a hazardous/unsafe situation.
   Examples: unattended child, aggressive adult near child, child distress, child injury.
   
2. elder_safety:
   An ELDERLY PERSON (approx 60+) appears at risk, especially falls, frailty, slow gait, mobility aids.
   Examples: elder on ground, elderly person falling, medical emergency in elderly, immobilization.
   
3. environmental_hazard:
   Fire, smoke, flooding, hazardous objects, unsafe infrastructure, or environmental threats.
   Tie-breaker: If a person falls but no environmental cause visible, and no elderly/child apparent → classify as environmental_hazard only if fall is clearly from hazard.
   Do NOT classify accidental falls as environmental_hazard unless caused by visible hazard.
   
4. crime:
   Clear MALICIOUS or INTENTIONAL WRONGDOING visible: assault, weapon use, theft, forced entry, stalking.
   Tie-breaker: Do NOT classify accidents or accidental falls as crime.
   Require visible malicious intent: weapon handling, aggressive assault, clear theft, forced entry.

TIE-BREAKER RULES (if multiple signals present):
- If a fall is detected:
  → If person appears elderly → elder_safety
  → If person appears a child → child_safety
  → Otherwise → only crime if clear malicious intent visible
- If fire/smoke visible → environmental_hazard (regardless of other signals)
- Only classify as crime if clear visible aggressive intent or weapon use
"""
    
    prompt = f"""{domain_definitions}

TASK: Classify this CCTV video into ONE of the 4 domains based on VISUAL EVIDENCE of WHO is at risk.

SEQUENCE SUMMARY (from heuristic analysis):
{sequence_summary if sequence_summary else "Video shows activity."}

NUMERIC SIGNAL SUMMARY FROM VIDEO ANALYSIS:
{signal_summary_json}

INSTRUCTIONS:
- Analyze VISUAL content in keyframes to identify WHO appears at risk
- Use numeric signals to corroborate classification
- Apply tie-breaker rules if multiple signals present
- Classify into exactly ONE primary domain
- Provide confidence scores for all 4 domains (must sum to 1.0)
- Assess overall severity (0=safe, 1=critical emergency)
- Provide 1-2 sentences of reasoning grounded in WHO is visible and their status
- List 2-3 KEY OBSERVATIONS about the people and situation

RESPOND WITH VALID JSON ONLY (no markdown, no explanation):
{{
  "primary_domain": "<one of: child_safety, elder_safety, environmental_hazard, crime>",
  "domain_probabilities": {{
    "child_safety": <0-1>,
    "elder_safety": <0-1>,
    "environmental_hazard": <0-1>,
    "crime": <0-1>
  }},
  "severity": <0-1>,
  "reasoning": "<1-2 sentences explaining WHO is at risk and why>",
  "key_observations": ["<observation1>", "<observation2>", "<observation3>"]
}}
"""
    
    # Build message with images
    content = [
        {
            "type": "text",
            "text": prompt
        }
    ]
    
    # Add keyframes as images
    for keyframe in keyframes:
        try:
            data_url = frame_to_base64_jpeg(keyframe['frame'], quality=85)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            })
        except Exception as e:
            print(f"Warning: Failed to encode keyframe at {keyframe['timestamp']}s: {e}", flush=True)
            continue
    
    if len(content) == 1:  # Only text, no images
        return {
            'gpt_used': False,
            'error': 'No keyframes could be encoded',
            'primary_domain': 'child_safety',
            'domain_probabilities': {
                'child_safety': 0.25,
                'elder_safety': 0.25,
                'environmental_hazard': 0.25,
                'crime': 0.25
            },
            'severity': 0.0,
            'reasoning': 'Failed to encode keyframes'
        }
    
    # Call GPT-4o-mini with vision (OpenAI API)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        # Extract response text (OpenAI format)
        response_text = response.choices[0].message.content
        
        # Parse JSON with retries
        result = None
        for attempt in range(max_retries):
            try:
                result = json.loads(response_text)
                break
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    print(f"Warning: JSON parse failed on attempt {attempt + 1}, retrying...", flush=True)
                else:
                    print(f"Error: Failed to parse GPT response as JSON: {e}", flush=True)
                    print(f"Response text: {response_text}", flush=True)
                    # STEP 4: Fallback to heuristic if JSON parse fails
                    return {
                        'gpt_used': False,
                        'error': f'JSON parse failed: {str(e)}',
                        'primary_domain': 'child_safety',
                        'domain_probabilities': {
                            'child_safety': 0.25,
                            'elder_safety': 0.25,
                            'environmental_hazard': 0.25,
                            'crime': 0.25
                        },
                        'severity': 0.0,
                        'reasoning': 'Fallback to heuristics due to parse failure'
                    }
        
        # Validate result schema
        if not result or 'primary_domain' not in result or 'domain_probabilities' not in result:
            raise ValueError("Missing required fields in GPT response")
        
        # STEP 4: Apply consistency constraints
        if timeline_data:
            result = apply_consistency_constraints(result, all_signal_features, timeline_data)
        else:
            # Normalize probabilities if no timeline data
            probs = result.get('domain_probabilities', {})
            total = sum(probs.values())
            if total > 0:
                for domain in probs:
                    probs[domain] = probs[domain] / total
        
        return {
            'gpt_used': True,
            'primary_domain': str(result.get('primary_domain', 'child_safety')),
            'domain_probabilities': {
                'child_safety': float(result.get('domain_probabilities', {}).get('child_safety', 0.25)),
                'elder_safety': float(result.get('domain_probabilities', {}).get('elder_safety', 0.25)),
                'environmental_hazard': float(result.get('domain_probabilities', {}).get('environmental_hazard', 0.25)),
                'crime': float(result.get('domain_probabilities', {}).get('crime', 0.25))
            },
            'severity': float(result.get('severity', 0.5)),
            'reasoning': str(result.get('reasoning', 'Video analyzed')),
            'key_observations': list(result.get('key_observations', []))
        }
    
    except Exception as e:
        print(f"Error calling OpenAI GPT-4o-mini Vision: {repr(e)}", flush=True)
        # STEP 4: Fallback to heuristic
        return {
            'gpt_used': False,
            'error': str(e),
            'primary_domain': 'child_safety',
            'domain_probabilities': {
                'child_safety': 0.25,
                'elder_safety': 0.25,
                'environmental_hazard': 0.25,
                'crime': 0.25
            },
            'severity': 0.0,
            'reasoning': f'API error: {str(e)}'
        }
