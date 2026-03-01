import React, { useState } from 'react';

export default function VideoAnalysisResults({ result }) {
  const [expandedSignal, setExpandedSignal] = useState(null);

  if (!result) return null;

  const getDomainEmoji = (domainId) => {
    const emojis = {
      // New domain IDs
      child_safety: '👧',
      elder_safety: '👴',
      environmental_hazard: '🏠',
      crime: '🚔',
      // Legacy domain IDs
      elder_care: '👴',
      environmental: '🏠',
      crime_prevention: '🚔',
    };
    return emojis[domainId] || '🎯';
  };

  const getDomainLabel = (domainId) => {
    const labels = {
      // New domain IDs
      child_safety: 'Child Safety',
      elder_safety: 'Elder Safety',
      environmental_hazard: 'Environmental Hazard',
      crime: 'Crime',
      // Legacy domain IDs
      elder_care: 'Elder Safety',
      environmental: 'Environmental Hazard',
      crime_prevention: 'Crime',
    };
    return labels[domainId] || domainId;
  };

  const getRiskColor = (score) => {
    if (score < 25) return '#10b981';
    if (score < 50) return '#f59e0b';
    if (score < 75) return '#ef6b3f';
    return '#dc2626';
  };

  const getDangerRank = (score) => {
    if (score < 25) return 'Green';
    if (score < 50) return 'Yellow';
    if (score < 75) return 'Orange';
    return 'Red';
  };

  const triggeredSignals = Object.entries(result.signals_detected || {})
    .filter(([, score]) => score > 0.5)
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="card video-analysis-results">
      <h2>✅ Analysis Complete</h2>

      {/* Primary Domain */}
      <div className="domain-result">
        <div className="domain-badge" style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>
          {getDomainEmoji(result.primary_domain)}
        </div>
        <h3 style={{ margin: '0.5rem 0', fontSize: '1.3rem', color: '#1f2937' }}>
          {getDomainLabel(result.primary_domain)}
        </h3>
        <p style={{ fontSize: '0.9rem', color: '#6b7280', margin: '0.25rem 0' }}>
          Confidence: <strong>{Math.round(result.domain_confidence * 100)}%</strong>
        </p>
      </div>

      {/* Risk Score */}
      <div className="risk-display">
        <div
          className="risk-number"
          style={{
            fontSize: '3rem',
            fontWeight: '700',
            color: getRiskColor(result.risk_score),
          }}
        >
          {Math.round(result.risk_score)}
        </div>
        <p style={{ margin: '0.5rem 0', color: '#6b7280' }}>
          Crisis Risk Index (CRI) • {getDangerRank(result.risk_score)}
        </p>
      </div>

      {/* Metrics Row */}
      <div className="metrics-grid">
        <div className="metric-box">
          <p className="metric-label">Danger Rank</p>
          <p className="metric-value">{result.danger_rank}</p>
        </div>
        <div className="metric-box">
          <p className="metric-label">Escalation Risk</p>
          <p className="metric-value">{parseFloat(result.escalation_probability).toFixed(1)}%</p>
        </div>
        <div className="metric-box">
          <p className="metric-label">Frames Analyzed</p>
          <p className="metric-value">{result.frames_analyzed}</p>
        </div>
        <div className="metric-box">
          <p className="metric-label">Video Duration</p>
          <p className="metric-value">{result.video_duration.toFixed(1)}s</p>
        </div>
      </div>

      {/* Reasoning */}
      {result.reasoning && (
        <div className="reasoning-box">
          <p style={{ fontSize: '0.95rem', color: '#374151', lineHeight: '1.6', margin: 0 }}>
            <strong>Classification Reasoning:</strong> {result.reasoning}
          </p>
        </div>
      )}

      {/* Triggered Signals */}
      <div className="signals-section">
        <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem', color: '#1f2937' }}>
          📊 Detected Signals ({triggeredSignals.length})
        </h4>
        {triggeredSignals.length > 0 ? (
          <div className="signals-list">
            {triggeredSignals.map(([signal, confidence], idx) => (
              <div key={signal} className="signal-item">
                <div className="signal-header" onClick={() => setExpandedSignal(expandedSignal === signal ? null : signal)}>
                  <div className="signal-info">
                    <span className="signal-name">
                      {signal.replace(/_/g, ' ').replace(/detected/i, '')}
                    </span>
                    <span className="signal-confidence">{Math.round(confidence * 100)}%</span>
                  </div>
                  <span className="expand-icon">{expandedSignal === signal ? '▼' : '▶'}</span>
                </div>
                {expandedSignal === signal && (
                  <div className="signal-details">
                    <p>Confidence Score: {(confidence * 100).toFixed(1)}%</p>
                    <p>Detection Method: MediaPipe-based frame analysis</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: '#9ca3af', fontSize: '0.9rem', margin: 0 }}>No significant signals detected</p>
        )}
      </div>

      {/* Domain Probabilities */}
      <div className="domain-probabilities">
        <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem', color: '#1f2937' }}>
          🎯 Domain Analysis
        </h4>
        <div className="probability-bars">
          {Object.entries(result.domain_probabilities || {}).map(([domain, prob]) => (
            <div key={domain} className="probability-item">
              <div className="probability-label">
                <span>{getDomainEmoji(domain)} {getDomainLabel(domain)}</span>
              </div>
              <div className="probability-bar">
                <div
                  className="probability-fill"
                  style={{
                    width: `${prob * 100}%`,
                    backgroundColor: domain === result.primary_domain ? '#3b82f6' : '#d1d5db',
                  }}
                />
              </div>
              <div className="probability-percent">{Math.round(prob * 100)}%</div>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline Preview */}
      {result.timeline && result.timeline.length > 0 && (
        <div className="timeline-section">
          <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem', color: '#1f2937' }}>
            📈 Analysis Timeline ({result.timeline.length} frames)
          </h4>
          <div className="timeline-container">
            {result.timeline.slice(0, 5).map((frame, idx) => (
              <div key={idx} className="timeline-frame">
                <div className="frame-timestamp">{frame.timestamp.toFixed(1)}s</div>
                <div className="frame-domain" title={frame.domain}>
                  {getDomainEmoji(frame.domain)}
                </div>
                <div className="frame-confidence">{Math.round(frame.domain_confidence * 100)}%</div>
              </div>
            ))}
            {result.timeline.length > 5 && (
              <div className="timeline-more">+{result.timeline.length - 5} more</div>
            )}
          </div>
        </div>
      )}

      {/* Alert Trigger */}
      <div className="action-box">
        <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.75rem' }}>
          📋 This analysis has been recorded as an alert in the Alert History if risk score is above threshold.
        </p>
        <button className="btn btn-secondary" onClick={() => window.location.href = '#alerts'}>
          View Alert History
        </button>
      </div>
    </div>
  );
}
