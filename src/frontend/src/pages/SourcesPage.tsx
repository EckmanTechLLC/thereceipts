/**
 * Sources page - All sources sorted by reference count.
 *
 * Displays all sources used across claim cards, sorted by most referenced first.
 */

import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { SourceWithCount } from '../types';
import './SourcesPage.css';

const SOURCE_TYPES = ['primary_historical', 'scholarly_peer_reviewed'];
const VERIFICATION_STATUSES = ['verified', 'partially_verified', 'unverified'];

export function SourcesPage() {
  const [sources, setSources] = useState<SourceWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [skip, setSkip] = useState(0);
  const [sourceType, setSourceType] = useState<string>('');
  const [verificationStatus, setVerificationStatus] = useState<string>('');

  const limit = 50;

  // Load sources
  useEffect(() => {
    loadSources();
  }, [skip, sourceType, verificationStatus]);

  const loadSources = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getSources({
        skip,
        limit,
        source_type: sourceType || undefined,
        verification_status: verificationStatus || undefined,
      });
      setSources(response.sources);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      setLoading(false);
    }
  };

  const handleSourceTypeChange = (newType: string) => {
    setSourceType(newType);
    setSkip(0);
  };

  const handleVerificationStatusChange = (newStatus: string) => {
    setVerificationStatus(newStatus);
    setSkip(0);
  };

  const handleClearFilters = () => {
    setSourceType('');
    setVerificationStatus('');
    setSkip(0);
  };

  const handleLoadMore = () => {
    setSkip(skip + limit);
  };

  const handleLoadPrevious = () => {
    setSkip(Math.max(0, skip - limit));
  };

  const formatSourceType = (type: string) => {
    return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  const getVerificationBadgeClass = (status: string | null) => {
    if (!status) return 'verification-badge unverified';
    return `verification-badge ${status}`;
  };

  return (
    <div className="sources-page">
      <div className="sources-header">
        <h1>Sources</h1>
        <p className="sources-subtitle">All sources used across claim cards, sorted by reference count</p>
      </div>

      {/* Filters */}
      <div className="sources-filters">
        <div className="filter-group">
          <label>Source Type:</label>
          <select value={sourceType} onChange={(e) => handleSourceTypeChange(e.target.value)}>
            <option value="">All Types</option>
            {SOURCE_TYPES.map(type => (
              <option key={type} value={type}>{formatSourceType(type)}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Verification Status:</label>
          <select value={verificationStatus} onChange={(e) => handleVerificationStatusChange(e.target.value)}>
            <option value="">All Statuses</option>
            {VERIFICATION_STATUSES.map(status => (
              <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>
            ))}
          </select>
        </div>

        {(sourceType || verificationStatus) && (
          <button onClick={handleClearFilters} className="clear-filters-btn">
            Clear Filters
          </button>
        )}
      </div>

      {/* Loading/Error states */}
      {loading && <div className="sources-loading">Loading sources...</div>}
      {error && <div className="sources-error">Error: {error}</div>}

      {/* Sources table */}
      {!loading && !error && sources.length === 0 && (
        <div className="sources-empty">No sources found</div>
      )}

      {!loading && !error && sources.length > 0 && (
        <>
          <div className="sources-table-container">
            <table className="sources-table">
              <thead>
                <tr>
                  <th>Citation</th>
                  <th>Type</th>
                  <th>Verification</th>
                  <th>References</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(source => (
                  <tr key={source.id}>
                    <td className="citation-cell">
                      <div className="citation-text">{source.citation}</div>
                    </td>
                    <td className="type-cell">{formatSourceType(source.source_type)}</td>
                    <td className="verification-cell">
                      <span className={getVerificationBadgeClass(source.verification_status)}>
                        {source.verification_status || 'unverified'}
                      </span>
                    </td>
                    <td className="count-cell">{source.usage_count}</td>
                    <td className="link-cell">
                      {source.url ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-link">
                          View
                        </a>
                      ) : (
                        <span className="no-link">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="sources-pagination">
            <button
              onClick={handleLoadPrevious}
              disabled={skip === 0}
              className="pagination-btn"
            >
              Previous
            </button>
            <span className="pagination-info">
              Showing {skip + 1}–{skip + sources.length}
            </span>
            <button
              onClick={handleLoadMore}
              disabled={sources.length < limit}
              className="pagination-btn"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
