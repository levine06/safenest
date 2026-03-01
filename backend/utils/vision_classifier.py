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
    
    Prioritizes:
    1. Frame with max motion_intensity
    2. Frame with max fire_smoke_probability
    3. Frame with max fighting_probability
    Optional: Include first fall_detected frame if present, but cap at 3 total
    
    Args:
        timeline_data (list): List of frame dicts with signals and motion_intensity
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
    
    # Map to store max value and its index for each criterion
    max_motion = {'value': -1, 'index': -1}
    max_fire = {'value': -1, 'index': -1}
    max_fighting = {'value': -1, 'index': -1}
    first_fall = {'index': -1}
    
    # Scan timeline to find max values
    for i, frame_data in enumerate(timeline_data):
        signals = frame_data.get('signals', {})
        
        # Motion intensity
        motion = frame_data.get('motion_intensity', 0)
        if motion > max_motion['value']:
            max_motion['value'] = motion
            max_motion['index'] = i
        
        # Fire/smoke
        fire_prob = signals.get('fire_smoke_detected', 0)
        if fire_prob > max_fire['value']:
            max_fire['value'] = fire_prob
            max_fire['index'] = i
        
        # Fighting
        fighting_prob = signals.get('fighting_detected', 0)
        if fighting_prob > max_fighting['value']:
            max_fighting['value'] = fighting_prob
            max_fighting['index'] = i
        
        # First fall
        if first_fall['index'] == -1 and signals.get('fall_detected', 0) > 0.5:
            first_fall['index'] = i
    
    # Build priority list: motion, fire, fighting, fall (max 3)
    candidates = [
        (max_motion['index'], 'max_motion'),
        (max_fire['index'], 'max_fire'),
        (max_fighting['index'], 'max_fighting'),
        (first_fall['index'], 'fall_detected')
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
            if idx == max_motion['index'] and max_motion['value'] > 0:
                reasons.append('max_motion')
            if idx == max_fire['index'] and max_fire['value'] > 0:
                reasons.append('max_fire_smoke')
            if idx == max_fighting['index'] and max_fighting['value'] > 0:
                reasons.append('max_fighting')
            if idx == first_fall['index'] and first_fall['index'] >= 0:
                reasons.append('fall_detected')
            
            keyframes.append({
                'frame': frame_obj['frame'],
                'timestamp': frame_obj['timestamp'],
                'reasons': reasons,
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


def classify_video_with_vision(keyframes, all_signal_features, max_retries=2):
    """
    Classify video using OpenAI GPT-4o-mini with vision input on keyframes.
    
    Args:
        keyframes (list): List of keyframe dicts with 'frame', 'timestamp', 'reasons'
        all_signal_features (dict): Aggregated signal features from all frames
        max_retries (int): Number of retries on JSON parse failure
    
    Returns:
        dict: {
            'gpt_used': bool,
            'primary_domain': str ('child_safety'|'elder_safety'|'environmental_hazard'|'crime'),
            'domain_probabilities': {'child_safety': float, 'elder_safety': float, ...},
            'severity': float (0-1),
            'reasoning': str,
            'key_observations': [str],
            'error': str (optional, if failed)
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
    
    # Build the prompt
    domain_definitions = """
DOMAIN DEFINITIONS:
1. child_safety: Indicators of child endangerment, abuse, neglect, inappropriate adult behavior, or child vulnerability (e.g., unattended children, aggressive adults near children, distress, trauma).
2. elder_safety: Indicators of elderly person endangerment, falls, medical emergencies, neglect, or vulnerability (e.g., elder on ground, slow movement, unresponsive, signs of medical distress).
3. environmental_hazard: Indicators of physical environmental threats (e.g., fire, smoke, structural hazards, flooding, chemical leaks, power outages, extreme weather, blocked exits).
4. crime: Indicators of criminal activity or violent crime risk (e.g., weapon presence, fighting, robbery, assault, theft, property damage, forced entry, weapons handling).
"""
    
    prompt = f"""{domain_definitions}

TASK: Classify this CCTV video into ONE of the 4 domains above based on visual evidence in the keyframes and the numeric signal data provided.

NUMERIC SIGNAL SUMMARY FROM VIDEO ANALYSIS:
{signal_summary_json}

INSTRUCTIONS:
- Analyze the VISUAL content in the keyframes provided.
- Use the numeric signals as corroborating evidence.
- Classify into exactly ONE primary domain.
- Provide probability scores for all 4 domains (must sum to ~1.0).
- Assess overall severity (0=safe, 1=critical emergency).
- Provide 1-2 sentences of reasoning grounded in VISIBLE CUES.
- List 2-3 KEY OBSERVATIONS from the frames.

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
  "reasoning": "<1-2 sentences with visible cues>",
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
    
    # Call GPT-4o-mini with vision
    try:
        response = client.messages.create(
            model="gpt-4o-mini",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        
        # Extract response text
        response_text = response.content[0].text
        
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
                    raise
        
        # Validate result schema
        if not result or 'primary_domain' not in result or 'domain_probabilities' not in result:
            raise ValueError("Missing required fields in GPT response")
        
        # Normalize domain probabilities to sum to 1.0
        probs = result.get('domain_probabilities', {})
        total = sum(probs.values())
        if total > 0:
            for domain in probs:
                probs[domain] = probs[domain] / total
        
        return {
            'gpt_used': True,
            'primary_domain': str(result.get('primary_domain', 'child_safety')),
            'domain_probabilities': {
                'child_safety': float(probs.get('child_safety', 0.25)),
                'elder_safety': float(probs.get('elder_safety', 0.25)),
                'environmental_hazard': float(probs.get('environmental_hazard', 0.25)),
                'crime': float(probs.get('crime', 0.25))
            },
            'severity': float(result.get('severity', 0.5)),
            'reasoning': str(result.get('reasoning', 'Video analyzed')),
            'key_observations': list(result.get('key_observations', []))
        }
    
    except Exception as e:
        print(f"Error calling OpenAI GPT-4o-mini Vision: {repr(e)}", flush=True)
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
