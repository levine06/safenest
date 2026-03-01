"""
SafeNest Risk Scoring Engine

Implements risk index calculation with multiple safety signals,
confidence weighting, and danger tier classification.
Supports multiple domains (Child Safety, Elder Care, etc.)

Privacy-First Design: All scoring is based on anonymized signals only—
no personal data or identifiable information is used.
"""

from datetime import datetime
from typing import Dict, List, Tuple
from utils.domain_config import get_domain_config

# Danger tier thresholds and labels (domain-agnostic)
DANGER_TIERS = [
    (0, 25, "Green", "Safe"),
    (26, 50, "Yellow", "Watch"),
    (51, 75, "Orange", "High Risk"),
    (76, 100, "Red", "Critical"),
]


def calculate_confidence_factor(num_signals_triggered: int) -> float:
    """
    Calculate confidence factor based on number of triggered signals.
    
    - 1 signal → 0.6
    - 2 signals → 0.75
    - 3+ signals → 0.9 (max 1.0)
    
    Args:
        num_signals_triggered: Count of signals that are True
        
    Returns:
        Confidence factor between 0.5 and 1.0
    """
    if num_signals_triggered == 0:
        return 0.5  # Very low confidence if no signals
    elif num_signals_triggered == 1:
        return 0.6
    elif num_signals_triggered == 2:
        return 0.75
    else:  # 3+
        return 0.9


def get_danger_rank(risk_score: float) -> Tuple[str, str]:
    """
    Classify risk score into danger tier.
    
    Args:
        risk_score: Numeric risk score (0-100)
        
    Returns:
        Tuple of (color_code, tier_name) e.g., ("Green", "Safe")
    """
    for min_score, max_score, color, tier_name in DANGER_TIERS:
        if min_score <= risk_score <= max_score:
            return (color, tier_name)
    # Fallback (should not reach here if score is properly clamped)
    return ("Red", "Critical")


def calculate_escalation_probability(signals: Dict[str, bool], escalation_bonuses: Dict[str, int], base: int = 20) -> float:
    """
    Calculate escalation probability based on triggered signals.
    
    Starts at base percentage, adds bonuses for each triggered signal, capped at 100%.
    
    Args:
        signals: Dictionary of boolean signals
        escalation_bonuses: Dict mapping signal names to bonus percentages
        base: Base escalation probability percentage
        
    Returns:
        Escalation probability as percentage (0-100)
    """
    probability = base

    # Signals may be boolean or numeric (0..1). Treat numeric as proportional contribution.
    for signal_name, val in signals.items():
        if signal_name in escalation_bonuses:
            try:
                # numeric contribution
                contrib = float(val)
            except Exception:
                contrib = 1.0 if bool(val) else 0.0
            probability += escalation_bonuses[signal_name] * max(0.0, min(1.0, contrib))

    # Cap at 100%
    return min(probability, 100)


def build_rationale(
    signal_contributions: Dict[str, float],
    weighted_sum: float,
    num_signals: int,
    confidence_factor: float,
    raw_score: float,
    final_score: float,
) -> Dict:
    """
    Build a detailed rationale explaining the risk score calculation.
    
    Args:
        signal_contributions: Dict of signal -> points contributed
        weighted_sum: Total points from all signals
        num_signals: Number of signals triggered
        confidence_factor: Confidence multiplier
        raw_score: Score before clamping
        final_score: Final clamped score (0-100)
        
    Returns:
        Dictionary with step-by-step calculation breakdown
    """
    return {
        "summary": f"Risk score calculated from {num_signals} triggered signal(s)",
        "signal_breakdown": signal_contributions,
        "weighted_sum": weighted_sum,
        "calculation": {
            "num_signals": num_signals,
            "confidence_factor": confidence_factor,
            "formula": f"{weighted_sum} × {confidence_factor} = {raw_score:.2f}",
            "raw_score": round(raw_score, 2),
            "clamped_score": final_score,
        },
        "explanation": (
            f"Triggered {num_signals} signal(s) with total weight {weighted_sum} points. "
            f"Applied confidence factor {confidence_factor} (lower confidence with fewer signals). "
            f"Final calculation: {weighted_sum} × {confidence_factor} = {raw_score:.2f}, "
            f"clamped to [{0}, {100}] = {final_score}."
        ),
    }


def analyze_risk(signals: Dict[str, bool], domain: str = 'child_safety', context: Dict = None) -> Dict:
    """
    Main risk analysis function with multi-domain support.
    
    Computes risk score, danger rank, triggered signals,
    and escalation probability for the specified domain.
    
    Args:
        signals: Dictionary of safety signals (boolean)
        domain: Domain ID (e.g., 'child_safety', 'elder_care')
        context: Optional context dict (reserved for future use)
        
    Returns:
        Dictionary with risk_score, danger_rank, danger_tier, triggered_signals,
        escalation_probability, timestamp, confidence, and rationale
    """
    
    # Get domain-specific configuration
    domain_config = get_domain_config(domain)
    signal_weights = domain_config['signal_weights']
    
    # Determine escalation bonuses (simple formula: 50% of signal weight)
    escalation_bonuses = {k: int(v * 0.5) for k, v in signal_weights.items()}
    escalation_base = 20  # Start at 20%
    
    # Signals may be boolean or numeric (0..1). Convert to numeric values 0..1.
    signal_values = {}
    for s, v in signals.items():
        if isinstance(v, bool):
            signal_values[s] = 1.0 if v else 0.0
        else:
            try:
                signal_values[s] = max(0.0, min(1.0, float(v)))
            except Exception:
                signal_values[s] = 0.0

    # Calculate weighted contributions (weight * confidence) per signal
    signal_contributions = {
        s: signal_weights[s] * signal_values.get(s, 0.0)
        for s in signal_weights.keys()
        if signal_values.get(s, 0.0) > 0
    }
    weighted_sum = sum(signal_contributions.values())

    # Determine confidence factor based on number of sufficiently-strong signals
    num_signals = sum(1 for v in signal_values.values() if v > 0.1)
    confidence_factor = calculate_confidence_factor(num_signals)

    # Calculate final risk score (use weighted sum scaled by confidence)
    raw_score = weighted_sum * confidence_factor
    risk_score = min(max(raw_score, 0), 100)  # Clamp to [0, 100]
    
    # Determine danger rank
    danger_color, danger_tier = get_danger_rank(risk_score)
    
    # Calculate escalation probability (scale bonuses by numeric signal value when available)
    escalation_probability = calculate_escalation_probability(signal_values, escalation_bonuses, escalation_base)
    
    # Build detailed rationale
    rationale = build_rationale(
        signal_contributions,
        weighted_sum,
        num_signals,
        confidence_factor,
        raw_score,
        risk_score
    )
    # Determine list of triggered signals (by numeric threshold)
    triggered_signals = [s for s, v in signal_values.items() if v > 0.1 and s in signal_weights]

    return {
        "risk_score": round(risk_score, 2),
        "danger_rank": danger_color,
        "danger_tier": danger_tier,
        "triggered_signals": triggered_signals,
        "escalation_probability": escalation_probability,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "confidence": confidence_factor,
        "rationale": rationale,
    }


if __name__ == "__main__":
    # Example usage
    test_signals = {
        "distress_scream_detected": True,
        "rapid_motion_detected": True,
        "child_stopped_moving": False,
        "adult_loitering_detected": True,
        "multiple_reports": False,
        "after_school_hours": True,
    }
    
    result = analyze_risk(test_signals)
    print("Test Risk Analysis Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")
