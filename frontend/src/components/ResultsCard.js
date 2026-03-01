import React, { useState } from 'react';

/**
 * ResultsCard Component
 * 
 * Displays the risk score, danger rank badge, triggered signals, 
 * and escalation probability with detailed rationale.
 */
function ResultsCard({ result, domain }) {
  const [showRationale, setShowRationale] = useState(false);

  if (!result) return null;

  // Color mapping for danger rank badges
  const getBadgeClass = (dangerRank) => {
    const rankMap = {
      Green: 'badge-green',
      Yellow: 'badge-yellow',
      Orange: 'badge-orange',
      Red: 'badge-red',
    };
    return rankMap[dangerRank] || 'badge-green';
  };

  const getDangerEmoji = (dangerRank) => {
    const emojiMap = {
      Green: '✅',
      Yellow: '⚠️',
      Orange: '🔴',
      Red: '🚨',
    };
    return emojiMap[dangerRank] || '❓';
  };

  return (
    <div className="card results-card">
      <h2>📊 Risk Analysis Results</h2>

      <div className="cri-score">{result.risk_score}</div>
      <p style={{ fontSize: '0.9rem', color: '#6b7280', marginTop: '-0.5rem' }}>
        Crisis Risk Index (CRI)
      </p>

      <div className={`danger-badge ${getBadgeClass(result.danger_rank)}`}>
        {getDangerEmoji(result.danger_rank)} {result.danger_tier}
      </div>

      <div className="metric-row">
        <div className="metric">
          <div className="metric-label">Danger Rank</div>
          <div className="metric-value">{result.danger_rank}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Escalation Prob.</div>
          <div className="metric-value">{result.escalation_probability}%</div>
        </div>
        <div className="metric">
          <div className="metric-label">Confidence</div>
          <div className="metric-value">{(result.confidence * 100).toFixed(0)}%</div>
        </div>
      </div>

      {result.triggered_signals && result.triggered_signals.length > 0 && (
        <div className="triggered-signals">
          <h4>🎯 Triggered Signals ({result.triggered_signals.length})</h4>
          <ul className="signal-list">
            {result.triggered_signals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Rationale Section */}
      {result.rationale && (
        <div className="rationale-section">
          <button
            className="rationale-toggle"
            onClick={() => setShowRationale(!showRationale)}
          >
            {showRationale ? '▼' : '▶'} Why this score? (Show rationale)
          </button>

          {showRationale && (
            <div className="rationale-content">
              <div className="rationale-summary">
                <strong>{result.rationale.summary}</strong>
              </div>

              {result.rationale.signal_breakdown &&
                Object.keys(result.rationale.signal_breakdown).length > 0 && (
                  <div className="signal-weights">
                    <h5>Signal Contributions:</h5>
                    <table className="weights-table">
                      <tbody>
                        {Object.entries(result.rationale.signal_breakdown).map(
                          ([signal, points]) => (
                            <tr key={signal}>
                              <td className="signal-name">{signal}</td>
                              <td className="signal-points">+{points} pts</td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                    <div className="total-weights">
                      <strong>Total: {result.rationale.weighted_sum} points</strong>
                    </div>
                  </div>
                )}

              <div className="calculation-steps">
                <h5>Calculation Breakdown:</h5>
                <div className="step">
                  <span className="step-label">Signals Triggered:</span>
                  <span className="step-value">{result.rationale.calculation.num_signals}</span>
                </div>
                <div className="step">
                  <span className="step-label">Confidence Factor:</span>
                  <span className="step-value">{result.rationale.calculation.confidence_factor}</span>
                </div>
                <div className="step formula">
                  <span className="step-label">Formula:</span>
                  <span className="step-value code">{result.rationale.calculation.formula}</span>
                </div>
                <div className="step">
                  <span className="step-label">Raw Score:</span>
                  <span className="step-value">{result.rationale.calculation.raw_score}</span>
                </div>
                <div className="step final">
                  <span className="step-label">Final Score (clamped 0-100):</span>
                  <span className="step-value">{result.rationale.calculation.clamped_score}</span>
                </div>
              </div>

              <div className="rationale-explanation">
                <p>{result.rationale.explanation}</p>
              </div>
            </div>
          )}
        </div>
      )}

      <p style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '1rem', textAlign: 'right' }}>
        Analyzed at {new Date(result.timestamp).toLocaleTimeString()}
      </p>
    </div>
  );
}

export default ResultsCard;
