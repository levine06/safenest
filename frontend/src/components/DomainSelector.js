import React from 'react';
import { getAllDomains } from '../config/domains';

/**
 * DomainSelector Component
 * 
 * Allows users to switch between different safety monitoring domains
 * (Child Safety, Elder Safety, Environmental Hazard, Crime)
 */
function DomainSelector({ selectedDomain, onDomainChange, currentDomainInfo }) {
  const domains = getAllDomains();

  return (
    <div className="domain-selector">
      <h3>🎯 Select Safety Domain:</h3>
      <div className="domain-buttons">
        {domains.map((domain) => (
          <button
            key={domain.id}
            className={`domain-btn ${selectedDomain === domain.id ? 'active' : ''}`}
            onClick={() => onDomainChange(domain.id)}
            title={domain.description}
          >
            {domain.emoji} {domain.label}
          </button>
        ))}
      </div>
      <p className="domain-description">
        <strong>{currentDomainInfo.label}:</strong> {currentDomainInfo.description}
      </p>
    </div>
  );
}

export default DomainSelector;
