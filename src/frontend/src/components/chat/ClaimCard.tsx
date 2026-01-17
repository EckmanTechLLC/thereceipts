/**
 * Claim card component with expandable sections.
 *
 * Renders a claim card within chat with collapsible content areas.
 */

import { useState } from 'react';
import type { ClaimCard as ClaimCardType } from '../../types';
import './ClaimCard.css';

interface ClaimCardProps {
  card: ClaimCardType;
}

export function ClaimCard({ card }: ClaimCardProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showAll, setShowAll] = useState(false);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const handleShowYourWork = () => {
    if (showAll) {
      // Hide all subsections and clear any expanded ones
      setExpandedSections(new Set());
      setShowAll(false);
    } else {
      // Show subsections (they appear collapsed)
      setShowAll(true);
    }
  };

  const isExpanded = (section: string) => expandedSections.has(section);

  // Helper to render verdict badge
  const renderVerdict = () => {
    if (!card.verdict) {
      return (
        <span className="verdict-badge verdict-unknown">
          Unknown
        </span>
      );
    }
    const verdictClass = card.verdict.toLowerCase().replace(/\s+/g, '-');
    return (
      <span className={`verdict-badge verdict-${verdictClass}`}>
        {card.verdict}
      </span>
    );
  };

  // Helper to render confidence badge
  const renderConfidence = () => {
    if (!card.confidence_level) {
      return (
        <span className="confidence-badge confidence-medium">
          Medium Confidence
        </span>
      );
    }
    const confidenceClass = card.confidence_level.toLowerCase();
    return (
      <span className={`confidence-badge confidence-${confidenceClass}`}>
        {card.confidence_level} Confidence
      </span>
    );
  };

  return (
    <div className="claim-card">
      {/* Header */}
      <div className="claim-card-header">
        <h3 className="claim-text">
          <span className="claim-label">Claim:</span> {card.claim_text}
        </h3>
        <div className="claim-meta">
          {renderVerdict()}
          {renderConfidence()}
        </div>
      </div>

      {/* Short answer (always visible) */}
      <div className="claim-section short-answer">
        <p>{card.short_answer}</p>
      </div>

      {/* Show Your Work button */}
      <div className="show-work-container">
        <button onClick={handleShowYourWork} className="show-work-button">
          {showAll ? 'Hide Details' : 'Show Your Work'}
        </button>
      </div>

      {/* Subsections (only visible after Show Your Work clicked) */}
      {showAll && (
        <>
          {/* Deep answer */}
          <div className="claim-section expandable">
        <button
          onClick={() => toggleSection('deep_answer')}
          className="section-toggle"
        >
          <span className={`toggle-icon ${isExpanded('deep_answer') ? 'expanded' : ''}`}>
            ▶
          </span>
          <span className="section-title">Deep Answer</span>
        </button>
        {isExpanded('deep_answer') && (
          <div className="section-content">
            <p>{card.deep_answer}</p>
          </div>
        )}
      </div>

      {/* Why this persists */}
      {card.why_persists && card.why_persists.length > 0 && (
        <div className="claim-section expandable">
          <button
            onClick={() => toggleSection('why_persists')}
            className="section-toggle"
          >
            <span className={`toggle-icon ${isExpanded('why_persists') ? 'expanded' : ''}`}>
              ▶
            </span>
            <span className="section-title">Why This Persists</span>
          </button>
          {isExpanded('why_persists') && (
            <div className="section-content">
              <ul>
                {card.why_persists.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Evidence review (confidence explanation) */}
      <div className="claim-section expandable">
        <button
          onClick={() => toggleSection('evidence')}
          className="section-toggle"
        >
          <span className={`toggle-icon ${isExpanded('evidence') ? 'expanded' : ''}`}>
            ▶
          </span>
          <span className="section-title">Evidence Review</span>
        </button>
        {isExpanded('evidence') && (
          <div className="section-content">
            <p>{card.confidence_explanation}</p>
          </div>
        )}
      </div>

      {/* Sources */}
      {card.sources && card.sources.length > 0 && (
        <div className="claim-section expandable">
          <button
            onClick={() => toggleSection('sources')}
            className="section-toggle"
          >
            <span className={`toggle-icon ${isExpanded('sources') ? 'expanded' : ''}`}>
              ▶
            </span>
            <span className="section-title">Sources ({card.sources.length})</span>
          </button>
          {isExpanded('sources') && (
            <div className="section-content">
              <ul className="sources-list">
                {card.sources.map(source => (
                  <li key={source.id} className="source-item">
                    <div className="source-citation">{source.citation}</div>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-link"
                      >
                        View Source →
                      </a>
                    )}
                    {source.usage_context && (
                      <div className="source-context">
                        <em>{source.usage_context}</em>
                      </div>
                    )}
                    {source.quote_text && (
                      <blockquote className="source-quote">
                        "{source.quote_text}"
                      </blockquote>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Apologetics techniques */}
      {card.apologetics_tags && card.apologetics_tags.length > 0 && (
        <div className="claim-section expandable">
          <button
            onClick={() => toggleSection('apologetics')}
            className="section-toggle"
          >
            <span className={`toggle-icon ${isExpanded('apologetics') ? 'expanded' : ''}`}>
              ▶
            </span>
            <span className="section-title">
              Apologetics Techniques ({card.apologetics_tags.length})
            </span>
          </button>
          {isExpanded('apologetics') && (
            <div className="section-content">
              <ul className="apologetics-list">
                {card.apologetics_tags.map(tag => (
                  <li key={tag.id} className="apologetics-item">
                    <strong>{tag.technique_name}</strong>
                    {tag.description && <p>{tag.description}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Agent audit trail */}
      <div className="claim-section expandable">
        <button
          onClick={() => toggleSection('audit')}
          className="section-toggle"
        >
          <span className={`toggle-icon ${isExpanded('audit') ? 'expanded' : ''}`}>
            ▶
          </span>
          <span className="section-title">Agent Audit Trail</span>
        </button>
        {isExpanded('audit') && (
          <div className="section-content">
            <pre className="audit-json">
              {JSON.stringify(card.agent_audit, null, 2)}
            </pre>
          </div>
        )}
      </div>
        </>
      )}
    </div>
  );
}
