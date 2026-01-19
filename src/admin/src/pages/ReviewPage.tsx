/**
 * Review Interface page.
 *
 * Admin interface for reviewing blog posts before publication.
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import type { PendingReview } from '../types';
import './ReviewPage.css';

export function ReviewPage() {
  const [reviews, setReviews] = useState<PendingReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedReview, setExpandedReview] = useState<string | null>(null);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  // Action modal state
  const [actionType, setActionType] = useState<'approve' | 'reject' | 'revision' | null>(null);
  const [selectedReview, setSelectedReview] = useState<PendingReview | null>(null);
  const [reviewerName, setReviewerName] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [revisionScope, setRevisionScope] = useState<'decomposer' | 'claim_pipeline' | 'composer'>('composer');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadReviews();
  }, []);

  const loadReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getPendingReviews({ limit: 50 });
      setReviews(response.reviews);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load reviews';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const toggleReviewExpand = (reviewId: string) => {
    setExpandedReview(expandedReview === reviewId ? null : reviewId);
  };

  const toggleCardExpand = (cardId: string) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(cardId)) {
      newExpanded.delete(cardId);
    } else {
      newExpanded.add(cardId);
    }
    setExpandedCards(newExpanded);
  };

  const openActionModal = (type: 'approve' | 'reject' | 'revision', review: PendingReview) => {
    setActionType(type);
    setSelectedReview(review);
    setReviewerName('');
    setReviewNotes('');
    setRevisionScope('composer');
  };

  const closeActionModal = () => {
    setActionType(null);
    setSelectedReview(null);
    setReviewerName('');
    setReviewNotes('');
  };

  const handleApprove = async () => {
    if (!selectedReview || !reviewerName.trim()) {
      alert('Reviewer name is required');
      return;
    }

    try {
      setIsSubmitting(true);
      await api.approveBlogPost(selectedReview.topic.id, {
        reviewed_by: reviewerName.trim(),
        review_notes: reviewNotes.trim() || undefined,
      });
      closeActionModal();
      loadReviews();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to approve blog post';
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!selectedReview || !reviewerName.trim() || !reviewNotes.trim()) {
      alert('Reviewer name and feedback are required');
      return;
    }

    try {
      setIsSubmitting(true);
      await api.rejectBlogPost(selectedReview.topic.id, {
        reviewed_by: reviewerName.trim(),
        admin_feedback: reviewNotes.trim(),
      });
      closeActionModal();
      loadReviews();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reject blog post';
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevision = async () => {
    if (!selectedReview || !reviewerName.trim() || !reviewNotes.trim()) {
      alert('Reviewer name and revision feedback are required');
      return;
    }

    try {
      setIsSubmitting(true);
      await api.requestRevision(selectedReview.topic.id, {
        reviewed_by: reviewerName.trim(),
        admin_feedback: reviewNotes.trim(),
        revision_scope: revisionScope,
      });
      closeActionModal();
      loadReviews();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to request revision';
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getVerdictBadgeClass = (verdict: string): string => {
    const map: Record<string, string> = {
      'True': 'verdict-true',
      'False': 'verdict-false',
      'Misleading': 'verdict-misleading',
      'Unfalsifiable': 'verdict-unfalsifiable',
      'Depends on Definitions': 'verdict-depends-on-definitions',
    };
    return map[verdict] || 'verdict-unfalsifiable';
  };

  return (
    <div className="review-page">
      <div className="page-header">
        <h1>Review Queue</h1>
        <button onClick={loadReviews} className="btn-secondary">Refresh</button>
      </div>

      {loading && <div className="loading">Loading reviews...</div>}
      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && reviews.length === 0 && (
        <div className="empty-state">No reviews pending</div>
      )}

      {!loading && !error && reviews.length > 0 && (
        <div className="review-list">
          {reviews.map(review => (
            <div key={review.topic.id} className="review-item">
              <div
                className="review-header"
                onClick={() => toggleReviewExpand(review.topic.id)}
              >
                <div className="review-title">
                  <h2>{review.blog_post?.title || 'Untitled'}</h2>
                  <button className="expand-toggle">
                    {expandedReview === review.topic.id ? '▼' : '▶'}
                  </button>
                </div>
                <div className="review-meta">
                  <span>Topic: {review.topic.topic_text}</span>
                  <span>Created: {new Date(review.topic.created_at).toLocaleDateString()}</span>
                  <span>Claim Cards: {review.claim_cards.length}</span>
                </div>
              </div>

              {expandedReview === review.topic.id && (
                <div className="review-body">
                  {/* Article preview */}
                  {review.blog_post && (
                    <div className="article-preview">
                      <h3>Article Body</h3>
                      <div className="article-text">{review.blog_post.article_body}</div>
                    </div>
                  )}

                  {/* Claim cards */}
                  <div className="claim-cards-section">
                    <h3>Component Claim Cards ({review.claim_cards.length})</h3>
                    <div className="claim-cards-list">
                      {review.claim_cards.map(card => (
                        <div key={card.id} className="claim-card-preview">
                          <div
                            className="claim-card-header"
                            onClick={() => toggleCardExpand(card.id)}
                          >
                            <h4>{card.claim_text}</h4>
                            <span className={`verdict-badge ${getVerdictBadgeClass(card.verdict)}`}>
                              {card.verdict}
                            </span>
                            <button className="expand-toggle">
                              {expandedCards.has(card.id) ? '▼' : '▶'}
                            </button>
                          </div>

                          {expandedCards.has(card.id) && (
                            <div className="claim-card-body">
                              <div className="claim-section">
                                <strong>Short Answer:</strong>
                                <p>{card.short_answer}</p>
                              </div>
                              <div className="claim-section">
                                <strong>Deep Answer:</strong>
                                <p>{card.deep_answer}</p>
                              </div>
                              {card.sources && card.sources.length > 0 && (
                                <div className="claim-section">
                                  <strong>Sources ({card.sources.length}):</strong>
                                  <ul className="sources-list">
                                    {card.sources.map(source => (
                                      <li key={source.id}>
                                        <div>{source.citation}</div>
                                        {source.url && (
                                          <a href={source.url} target="_blank" rel="noopener noreferrer">
                                            {source.url}
                                          </a>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {card.category_tags && card.category_tags.length > 0 && (
                                <div className="claim-section">
                                  <strong>Categories:</strong>
                                  <div className="category-tags">
                                    {card.category_tags.map(tag => (
                                      <span key={tag.id} className="category-tag">
                                        {tag.category_name}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Review actions */}
                  <div className="review-actions">
                    <button
                      onClick={() => openActionModal('approve', review)}
                      className="btn-primary btn-approve"
                    >
                      Approve & Publish
                    </button>
                    <button
                      onClick={() => openActionModal('revision', review)}
                      className="btn-secondary"
                    >
                      Request Revision
                    </button>
                    <button
                      onClick={() => openActionModal('reject', review)}
                      className="btn-danger"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Action modals */}
      {actionType && selectedReview && (
        <div className="modal-overlay" onClick={closeActionModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>
              {actionType === 'approve' && 'Approve Blog Post'}
              {actionType === 'reject' && 'Reject Blog Post'}
              {actionType === 'revision' && 'Request Revision'}
            </h2>

            <div className="form-group">
              <label>Reviewer Name:</label>
              <input
                type="text"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                placeholder="Your name"
              />
            </div>

            {actionType === 'revision' && (
              <div className="form-group">
                <label>Revision Scope:</label>
                <select value={revisionScope} onChange={(e) => setRevisionScope(e.target.value as any)}>
                  <option value="composer">Re-run Blog Composer (title/article)</option>
                  <option value="claim_pipeline">Re-run Claim Pipeline (specific cards)</option>
                  <option value="decomposer">Re-run Decomposer (topic breakdown)</option>
                </select>
              </div>
            )}

            <div className="form-group">
              <label>
                {actionType === 'approve' && 'Review Notes (optional):'}
                {actionType === 'reject' && 'Rejection Reason:'}
                {actionType === 'revision' && 'Revision Instructions:'}
              </label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                rows={4}
                placeholder={
                  actionType === 'approve'
                    ? 'Optional notes about this review...'
                    : 'Explain what needs to be fixed...'
                }
              />
            </div>

            <div className="modal-actions">
              <button
                onClick={
                  actionType === 'approve'
                    ? handleApprove
                    : actionType === 'reject'
                    ? handleReject
                    : handleRevision
                }
                disabled={isSubmitting || !reviewerName.trim() || (actionType !== 'approve' && !reviewNotes.trim())}
                className="btn-primary"
              >
                {isSubmitting ? 'Processing...' : 'Confirm'}
              </button>
              <button onClick={closeActionModal} className="btn-secondary">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
