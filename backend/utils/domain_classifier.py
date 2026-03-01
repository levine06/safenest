"""
Domain Classifier Utility

Maps detected signals and features to safety domains and identifies which domain is affected.
"""

from utils.domain_config import get_domain_config


def classify_domain_from_signals(signal_features, motion_analysis, face_analysis):
    """
    Classify which domain is most likely affected based on detected signals and features.
    
    Args:
        signal_features (dict): Signal feature scores (0-1 for each signal)
        motion_analysis (dict): Motion and frame analysis data
        face_analysis (dict): Face and crowd detection data
    
    Returns:
        dict: {
            'primary_domain': str (domain_id),
            'domain_probabilities': {
                'child_safety': float,
                'elder_care': float,
                'environmental': float,
                'crime_prevention': float
            },
            'reasoning': str,
            'confidence': float (0-1)
        }
    """
    
    domain_scores = {
        'child_safety': 0.0,
        'elder_care': 0.0,
        'environmental': 0.0,
        'crime_prevention': 0.0,
    }
    
    # Child Safety indicators - lower thresholds
    if signal_features.get('rapid_motion_detected', 0) > 0.25:
        domain_scores['child_safety'] += 0.35
    if signal_features.get('distress_scream_detected', 0) > 0.2:
        domain_scores['child_safety'] += 0.65
    if signal_features.get('adult_loitering_detected', 0) > 0.25:
        domain_scores['child_safety'] += 0.45
    if motion_analysis.get('motion_areas', 0) > 0:
        domain_scores['child_safety'] += 0.25
    
    # Elder Care indicators - lower thresholds
    if signal_features.get('fall_detected', 0) > 0.5:
        domain_scores['elder_care'] += 0.9
    if motion_analysis.get('motion_detected', False) == False and face_analysis.get('faces_detected', 0) > 0:
        domain_scores['elder_care'] += 0.35  # Stillness indicator
    if motion_analysis.get('motion_intensity', 0) < 0.15 and face_analysis.get('faces_detected', 0) > 0:
        domain_scores['elder_care'] += 0.25
    
    # Environmental Hazards indicators - lower thresholds
    if signal_features.get('smoke_detected', 0) > 0.3:
        domain_scores['environmental'] += 0.8
    if signal_features.get('fire_smoke_detected', 0) > 0.25:  # Enhanced fire detection
        domain_scores['environmental'] += 0.85
    if signal_features.get('fire_glow_detected', 0) > 0.2:  # Fire glow
        domain_scores['environmental'] += 0.75
    if motion_analysis.get('is_dark', False):
        domain_scores['environmental'] += 0.3
    if motion_analysis.get('brightness', 1) < 0.25:
        domain_scores['environmental'] += 0.25
    
    # Crime Prevention indicators - lower thresholds
    if signal_features.get('weapon_detected', 0) > 0.3:
        domain_scores['crime_prevention'] += 0.85
    if signal_features.get('adult_loitering_detected', 0) > 0.3:
        domain_scores['crime_prevention'] += 0.5
    if motion_analysis.get('crowd_density', 0) > 0.2:
        domain_scores['crime_prevention'] += 0.35
    if motion_analysis.get('motion_intensity', 0) > 0.15:
        domain_scores['crime_prevention'] += 0.3
    
    # Normalize scores to 0-1
    total_score = sum(domain_scores.values())
    if total_score > 0:
        for domain in domain_scores:
            domain_scores[domain] = domain_scores[domain] / max(total_score, 1)
    else:
        # Default uniform distribution if no strong signals
        for domain in domain_scores:
            domain_scores[domain] = 0.25
    
    # Find primary domain
    primary_domain = max(domain_scores, key=domain_scores.get)
    primary_confidence = domain_scores[primary_domain]
    
    # Generate reasoning
    reasoning = generate_classification_reasoning(signal_features, primary_domain)
    
    return {
        'primary_domain': primary_domain,
        'domain_probabilities': domain_scores,
        'reasoning': reasoning,
        'confidence': primary_confidence
    }


def generate_classification_reasoning(signal_features, primary_domain):
    """
    Generate human-readable explanation for domain classification.
    
    Args:
        signal_features (dict): Detected signal features
        primary_domain (str): Primary domain class
    
    Returns:
        str: Reasoning explanation
    """
    reasons = []
    
    # Analyze which signals contributed most
    top_signals = []
    for signal, score in signal_features.items():
        # only consider numeric scores when reasoning
        if isinstance(score, (int, float)) and score > 0.3:
            top_signals.append((signal, score))
    
    top_signals.sort(key=lambda x: x[1], reverse=True)
    
    if primary_domain == 'child_safety':
        reasons.append("Child Safety domain detected based on:")
        if any('rapid_motion' in s[0] for s in top_signals):
            reasons.append("• Rapid motion detected (potential struggle/distress)")
        if any('adult_loitering' in s[0] for s in top_signals):
            reasons.append("• Adult proximity detected (potential concern)")
        if any('distress' in s[0] for s in top_signals):
            reasons.append("• Distress indicators present")
    
    elif primary_domain == 'elder_care':
        reasons.append("Elder Care domain detected based on:")
        if any('fall' in s[0] for s in top_signals):
            reasons.append("• Fall detected (potential injury risk)")
        if any('stillness' in s[0] for s in top_signals) or len(top_signals) < 2:
            reasons.append("• Reduced motion pattern (potential immobility)")
    
    elif primary_domain == 'environmental':
        reasons.append("Environmental Hazards domain detected based on:")
        if any('smoke' in s[0] for s in top_signals):
            reasons.append("• Smoke or fire indicators")
        if any('dark' in s[0] for s in top_signals):
            reasons.append("• Lighting anomalies detected")
    
    elif primary_domain == 'crime_prevention':
        reasons.append("Crime Prevention domain detected based on:")
        if any('loitering' in s[0] for s in top_signals):
            reasons.append("• Suspicious loitering pattern detected")
        if any('weapon' in s[0] for s in top_signals):
            reasons.append("• Potential threat indicators present")
        if any('motion' in s[0] for s in top_signals):
            reasons.append("• Unusual motion pattern detected")
    
    return " ".join(reasons) if reasons else f"Classified as {primary_domain}"


def signals_to_boolean_dict(signal_features, threshold=0.3):
    """
    Convert signal feature scores to boolean dictionary for risk scoring.
    
    Args:
        signal_features (dict): Signal scores (0-1)
        threshold (float): Confidence threshold for boolean conversion
    
    Returns:
        dict: Boolean signals for risk scoring
    """
    boolean_signals = {}
    for signal, score in signal_features.items():
        if isinstance(score, (int, float)):
            boolean_signals[signal] = score > threshold
        else:
            # Non-numeric values cannot trigger a signal
            boolean_signals[signal] = False
    return boolean_signals


def get_signal_confidence_scores(signal_features):
    """
    Get confidence scores for each signal as a normalized dict.
    
    Args:
        signal_features (dict): Raw signal scores
    
    Returns:
        dict: Normalized confidence for each signal (0-1)
    """
    normalized = {}
    for signal, score in signal_features.items():
        if isinstance(score, (int, float)):
            normalized[signal] = min(1.0, score)
        else:
            normalized[signal] = 0.0
    
    return normalized
