/**
 * Safety Domain Configurations
 * 
 * Defines different safety monitoring domains with their
 * specific signals, weights, and descriptions.
 */

export const SAFETY_DOMAINS = {
  CHILD_SAFETY: {
    id: 'child_safety',
    label: 'Child Safety',
    emoji: '👧',
    description: 'Detect risks to children in public spaces',
    signals: [
      { key: 'distress_scream_detected', label: 'Distress Scream', weight: 45 },
      { key: 'rapid_motion_detected', label: 'Rapid Motion', weight: 35 },
      { key: 'child_stopped_moving', label: 'Child Stopped Moving', weight: 25 },
      { key: 'adult_loitering_detected', label: 'Adult Loitering', weight: 30 },
      { key: 'multiple_reports', label: 'Multiple Reports', weight: 20 },
      { key: 'after_school_hours', label: 'After School Hours', weight: 10 },
    ],
  },
  ELDER_SAFETY: {
    id: 'elder_safety',
    label: 'Elder Safety',
    emoji: '👴',
    description: 'Monitor elderly persons for health & safety risks',
    signals: [
      { key: 'fall_detected', label: 'Fall Detected', weight: 50 },
      { key: 'no_movement_extended', label: 'No Movement (30+ min)', weight: 40 },
      { key: 'caregiver_absent', label: 'Caregiver Absent', weight: 35 },
      { key: 'emergency_call_pressed', label: 'Emergency Call Button', weight: 45 },
      { key: 'abnormal_vitals', label: 'Abnormal Vitals', weight: 38 },
      { key: 'isolation_risk', label: 'High Isolation Risk', weight: 25 },
    ],
  },
  ENVIRONMENTAL_HAZARD: {
    id: 'environmental_hazard',
    label: 'Environmental Hazard',
    emoji: '🏠',
    description: 'Detect environmental risks (fire, flooding, hazmat)',
    signals: [
      { key: 'smoke_detected', label: 'Smoke Detected', weight: 55 },
      { key: 'heat_anomaly', label: 'Extreme Heat', weight: 45 },
      { key: 'water_flooding', label: 'Water Flooding', weight: 50 },
      { key: 'toxic_fumes', label: 'Toxic Fumes Detected', weight: 60 },
      { key: 'structural_damage', label: 'Structural Damage', weight: 40 },
      { key: 'power_outage', label: 'Power Outage', weight: 20 },
    ],
  },
  CRIME: {
    id: 'crime',
    label: 'Crime',
    emoji: '🚔',
    description: 'Detect suspicious activity & crime risk indicators',
    signals: [
      { key: 'loitering_pattern', label: 'Suspicious Loitering', weight: 35 },
      { key: 'forced_entry', label: 'Forced Entry Detected', weight: 55 },
      { key: 'multiple_people_gathered', label: 'Crowd Anomaly', weight: 30 },
      { key: 'weapon_detected', label: 'Weapon Detected', weight: 60 },
      { key: 'theft_in_progress', label: 'Theft Pattern', weight: 50 },
      { key: 'after_hours_access', label: 'After-Hours Access', weight: 25 },
    ],
  },
};

/**
 * Get domain configuration by ID
 */
export function getDomainById(domainId) {
  return Object.values(SAFETY_DOMAINS).find(d => d.id === domainId) || SAFETY_DOMAINS.CHILD_SAFETY;
}

/**
 * Get all domains as array
 */
export function getAllDomains() {
  return Object.values(SAFETY_DOMAINS);
}
