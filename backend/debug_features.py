import sys
sys.path.insert(0,'/Users/levine/deeplearningweek/safenest/backend')
from utils.signal_detector import generate_signal_features

frame_analysis={
    'brightness': {'brightness': 0.5716, 'is_dark': False},
    'motion_detected': False,
    'motion_intensity': 0,
    'motion_areas': 0,
    'faces_detected': 0,
    'crowd_density': 0.0,
    'fall_detected': False,
    'rapid_motion_intensity': 0,
    'fire_smoke_probability': 0.0,
    'has_orange_red': False,
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

features = generate_signal_features(frame_analysis)
print('FEATURES', features)
for k,v in features.items():
    print(k, type(v), v)
