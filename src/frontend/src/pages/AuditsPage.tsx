/**
 * Audits page - Claim card repository.
 *
 * Browse all visible claim cards with filtering and full detail modal.
 */

import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { ClaimCard, VerdictType } from '../types';
import './AuditsPage.css';

const CATEGORIES = ['Genesis', 'Canon', 'Doctrine', 'Ethics', 'Institutions'];
const VERDICTS: VerdictType[] = ['True', 'Misleading', 'False', 'Unfalsifiable', 'Depends on Definitions'];

// Verdict badge color mapping
const VERDICT_COLORS: Record<VerdictType, string> = {
  'True': 'verdict-true',
  'Misleading': 'verdict-misleading',
  'False': 'verdict-false',
  'Unfalsifiable': 'verdict-unfalsifiable',
  'Depends on Definitions': 'verdict-depends',
};

export function AuditsPage() {
  const [cards, setCards] = useState<ClaimCard[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<ClaimCard | null>(null);

  // Filters
  const [skip, setSkip] = useState(0);
  const [category, setCategory] = useState<string>('');
  const [verdict, setVerdict] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const [searchInput, setSearchInput] = useState<string>('');

  const limit = 50;

  // Load claim cards
  useEffect(() => {
    loadCards();
  }, [skip, category, verdict, search]);

  const loadCards = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getAuditCards({
        skip,
        limit,
        category: category || undefined,
        verdict: verdict || undefined,
        search: search || undefined,
      });
      setCards(response.claim_cards);
      setTotal(response.total);
      setHasMore(response.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load claim cards');
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = (card: ClaimCard) => {
    setSelectedCard(card);
  };

  const handleCloseModal = () => {
    setSelectedCard(null);
  };

  const handleCategoryChange = (newCategory: string) => {
    setCategory(newCategory);
    setSkip(0); // Reset pagination
  };

  const handleVerdictChange = (newVerdict: string) => {
    setVerdict(newVerdict);
    setSkip(0);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setSkip(0);
  };

  const handleClearFilters = () => {
    setCategory('');
    setVerdict('');
    setSearch('');
    setSearchInput('');
    setSkip(0);
  };

  const handleLoadMore = () => {
    setSkip(skip + limit);
  };

  const handleLoadPrevious = () => {
    setSkip(Math.max(0, skip - limit));
  };

  const activeFiltersCount = [category, verdict, search].filter(Boolean).length;

  return (
    <div className="audits-page">
      <div className="audits-container">
        {/* Page header */}
        <div className="page-header">
          <div>
            <h1>Audits</h1>
            <p className="subtitle">Browse all audited claim cards</p>
          </div>
          {total > 0 && (
            <div className="total-count">
              {total} claim card{total !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="filters-section">
          <form onSubmit={handleSearchSubmit} className="search-form">
            <input
              type="text"
              placeholder="Search claims..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="search-input"
            />
            <button type="submit" className="search-button">
              Search
            </button>
          </form>

          <div className="filter-row">
            <div className="filter-group">
              <label>Category:</label>
              <select
                value={category}
                onChange={(e) => handleCategoryChange(e.target.value)}
                className="filter-select"
              >
                <option value="">All Categories</option>
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label>Verdict:</label>
              <select
                value={verdict}
                onChange={(e) => handleVerdictChange(e.target.value)}
                className="filter-select"
              >
                <option value="">All Verdicts</option>
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>

            {activeFiltersCount > 0 && (
              <button onClick={handleClearFilters} className="clear-filters-button">
                Clear Filters ({activeFiltersCount})
              </button>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="error-message">
            <span className="error-icon">⚠</span>
            <span>{error}</span>
          </div>
        )}

        {/* Loading */}
        {loading && cards.length === 0 ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading claim cards...</p>
          </div>
        ) : cards.length === 0 ? (
          <div className="empty-state">
            <h2>No claim cards found</h2>
            <p>Try adjusting your filters.</p>
          </div>
        ) : (
          <>
            {/* Cards grid */}
            <div className="cards-grid">
              {cards.map((card) => (
                <div
                  key={card.id}
                  className="claim-card-summary"
                  onClick={() => handleCardClick(card)}
                >
                  <div className={`verdict-badge ${VERDICT_COLORS[card.verdict]}`}>
                    {card.verdict}
                  </div>
                  <h3>{card.claim_text}</h3>
                  <p className="short-answer">{card.short_answer}</p>
                  <div className="card-footer">
                    {card.category_tags.length > 0 && (
                      <div className="categories">
                        {card.category_tags.slice(0, 2).map((tag) => (
                          <span key={tag.id} className="category-tag">
                            {tag.category_name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {(skip > 0 || hasMore) && (
              <div className="pagination">
                <button
                  onClick={handleLoadPrevious}
                  disabled={skip === 0 || loading}
                  className="pagination-button"
                >
                  ← Previous
                </button>
                <span className="pagination-info">
                  Showing {skip + 1}-{skip + cards.length} of {total}
                </span>
                <button
                  onClick={handleLoadMore}
                  disabled={!hasMore || loading}
                  className="pagination-button"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}

        {/* Modal for full claim card */}
        {selectedCard && (
          <div className="modal-overlay" onClick={handleCloseModal}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button className="modal-close" onClick={handleCloseModal}>
                ✕
              </button>

              <div className="modal-header">
                <div className={`verdict-badge ${VERDICT_COLORS[selectedCard.verdict]}`}>
                  {selectedCard.verdict}
                </div>
                <h2>{selectedCard.claim_text}</h2>
                {selectedCard.claimant && (
                  <p className="claimant">Claimant: {selectedCard.claimant}</p>
                )}
              </div>

              <div className="modal-body">
                <section className="modal-section">
                  <h3>Short Answer</h3>
                  <p>{selectedCard.short_answer}</p>
                </section>

                <section className="modal-section">
                  <h3>Deep Answer</h3>
                  <p>{selectedCard.deep_answer}</p>
                </section>

                {selectedCard.why_persists && selectedCard.why_persists.length > 0 && (
                  <section className="modal-section">
                    <h3>Why This Claim Persists</h3>
                    <ul>
                      {selectedCard.why_persists.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {selectedCard.sources.length > 0 && (
                  <section className="modal-section">
                    <h3>Sources</h3>
                    <div className="sources-list">
                      {selectedCard.sources.map((source) => (
                        <div key={source.id} className="source-item">
                          <div className="source-type">{source.source_type.replace('_', ' ')}</div>
                          <div className="source-citation">{source.citation}</div>
                          {source.url && (
                            <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-url">
                              View source →
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <section className="modal-section">
                  <h3>Confidence Level</h3>
                  <p>
                    <strong>{selectedCard.confidence_level}</strong> - {selectedCard.confidence_explanation}
                  </p>
                </section>

                {selectedCard.category_tags.length > 0 && (
                  <section className="modal-section">
                    <h3>Categories</h3>
                    <div className="categories">
                      {selectedCard.category_tags.map((tag) => (
                        <span key={tag.id} className="category-tag">
                          {tag.category_name}
                        </span>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
