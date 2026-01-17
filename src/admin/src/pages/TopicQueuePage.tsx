/**
 * Topic Queue Management page.
 *
 * Admin interface for managing topic queue: list, add, edit, delete.
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import type { AdminTopic, TopicStatus, ReviewStatus } from '../types';
import './TopicQueuePage.css';

export function TopicQueuePage() {
  const [topics, setTopics] = useState<AdminTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<TopicStatus | ''>('');
  const [reviewFilter, setReviewFilter] = useState<ReviewStatus | ''>('');

  // Add topic modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTopicText, setNewTopicText] = useState('');
  const [newTopicPriority, setNewTopicPriority] = useState(5);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit topic modal state
  const [editingTopic, setEditingTopic] = useState<AdminTopic | null>(null);
  const [editText, setEditText] = useState('');
  const [editPriority, setEditPriority] = useState(5);
  const [editStatus, setEditStatus] = useState<TopicStatus>('queued');

  useEffect(() => {
    loadTopics();
  }, [statusFilter, reviewFilter]);

  const loadTopics = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getTopics({
        status: statusFilter || undefined,
        review_status: reviewFilter || undefined,
        limit: 100,
      });
      setTopics(response.topics);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load topics';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTopic = async () => {
    if (!newTopicText.trim()) {
      alert('Topic text is required');
      return;
    }

    try {
      setIsSubmitting(true);
      await api.createTopic({
        topic_text: newTopicText.trim(),
        priority: newTopicPriority,
        source: 'manual',
      });
      setShowAddModal(false);
      setNewTopicText('');
      setNewTopicPriority(5);
      loadTopics();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create topic';
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditTopic = (topic: AdminTopic) => {
    setEditingTopic(topic);
    setEditText(topic.topic_text);
    setEditPriority(topic.priority);
    setEditStatus(topic.status);
  };

  const handleUpdateTopic = async () => {
    if (!editingTopic || !editText.trim()) return;

    try {
      setIsSubmitting(true);
      await api.updateTopic(editingTopic.id, {
        topic_text: editText.trim(),
        priority: editPriority,
        status: editStatus,
      });
      setEditingTopic(null);
      loadTopics();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update topic';
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteTopic = async (topicId: string) => {
    if (!confirm('Delete this topic? This action cannot be undone.')) return;

    try {
      await api.deleteTopic(topicId);
      loadTopics();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete topic';
      alert(message);
    }
  };

  const getStatusBadgeClass = (status: TopicStatus): string => {
    const map: Record<TopicStatus, string> = {
      queued: 'status-queued',
      processing: 'status-processing',
      completed: 'status-completed',
      failed: 'status-failed',
    };
    return map[status] || 'status-queued';
  };

  const getReviewBadgeClass = (review: ReviewStatus): string => {
    const map: Record<ReviewStatus, string> = {
      pending_review: 'review-pending',
      approved: 'review-approved',
      rejected: 'review-rejected',
      needs_revision: 'review-revision',
    };
    return map[review] || 'review-pending';
  };

  return (
    <div className="topic-queue-page">
      <div className="page-header">
        <h1>Topic Queue</h1>
        <button onClick={() => setShowAddModal(true)} className="btn-primary">
          Add Topic
        </button>
      </div>

      {/* Filters */}
      <div className="filters">
        <div className="filter-group">
          <label>Status:</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as TopicStatus | '')}>
            <option value="">All</option>
            <option value="queued">Queued</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Review:</label>
          <select value={reviewFilter} onChange={(e) => setReviewFilter(e.target.value as ReviewStatus | '')}>
            <option value="">All</option>
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="needs_revision">Needs Revision</option>
          </select>
        </div>

        <button onClick={loadTopics} className="btn-secondary">Refresh</button>
      </div>

      {/* Topic list */}
      {loading && <div className="loading">Loading topics...</div>}
      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && topics.length === 0 && (
        <div className="empty-state">No topics found</div>
      )}

      {!loading && !error && topics.length > 0 && (
        <div className="topic-list">
          {topics.map(topic => (
            <div key={topic.id} className="topic-item">
              <div className="topic-header">
                <span className={`badge ${getStatusBadgeClass(topic.status)}`}>
                  {topic.status}
                </span>
                <span className={`badge ${getReviewBadgeClass(topic.review_status)}`}>
                  {topic.review_status}
                </span>
                <span className="priority">Priority: {topic.priority}</span>
              </div>

              <div className="topic-text">{topic.topic_text}</div>

              <div className="topic-meta">
                <span className="meta-item">Source: {topic.source || 'N/A'}</span>
                <span className="meta-item">Created: {new Date(topic.created_at).toLocaleDateString()}</span>
                {topic.error_message && (
                  <span className="meta-item error-text">Error: {topic.error_message}</span>
                )}
              </div>

              <div className="topic-actions">
                <button onClick={() => handleEditTopic(topic)} className="btn-sm btn-secondary">
                  Edit
                </button>
                <button onClick={() => handleDeleteTopic(topic.id)} className="btn-sm btn-danger">
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Topic Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Add New Topic</h2>

            <div className="form-group">
              <label>Topic Text:</label>
              <textarea
                value={newTopicText}
                onChange={(e) => setNewTopicText(e.target.value)}
                placeholder="Enter topic or claim to analyze..."
                rows={4}
              />
            </div>

            <div className="form-group">
              <label>Priority (1-10):</label>
              <input
                type="number"
                value={newTopicPriority}
                onChange={(e) => setNewTopicPriority(parseInt(e.target.value))}
                min={1}
                max={10}
              />
            </div>

            <div className="modal-actions">
              <button
                onClick={handleAddTopic}
                disabled={isSubmitting || !newTopicText.trim()}
                className="btn-primary"
              >
                {isSubmitting ? 'Adding...' : 'Add Topic'}
              </button>
              <button onClick={() => setShowAddModal(false)} className="btn-secondary">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Topic Modal */}
      {editingTopic && (
        <div className="modal-overlay" onClick={() => setEditingTopic(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Topic</h2>

            <div className="form-group">
              <label>Topic Text:</label>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                rows={4}
              />
            </div>

            <div className="form-group">
              <label>Priority (1-10):</label>
              <input
                type="number"
                value={editPriority}
                onChange={(e) => setEditPriority(parseInt(e.target.value))}
                min={1}
                max={10}
              />
            </div>

            <div className="form-group">
              <label>Status:</label>
              <select value={editStatus} onChange={(e) => setEditStatus(e.target.value as TopicStatus)}>
                <option value="queued">Queued</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            <div className="modal-actions">
              <button
                onClick={handleUpdateTopic}
                disabled={isSubmitting || !editText.trim()}
                className="btn-primary"
              >
                {isSubmitting ? 'Updating...' : 'Update'}
              </button>
              <button onClick={() => setEditingTopic(null)} className="btn-secondary">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
