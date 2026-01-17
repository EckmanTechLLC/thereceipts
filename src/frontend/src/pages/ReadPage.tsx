/**
 * Read page - Blog articles (synthesized prose from claim cards).
 *
 * Shows published blog posts with full article view and claim card references.
 */

import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { BlogPost } from '../types';
import './ReadPage.css';

export function ReadPage() {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPost, setSelectedPost] = useState<BlogPost | null>(null);
  const [skip, setSkip] = useState(0);
  const limit = 20;

  // Load blog posts
  useEffect(() => {
    loadPosts();
  }, [skip]);

  const loadPosts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getBlogPosts({ skip, limit });
      setPosts(response.posts);
      setTotal(response.total);
      setHasMore(response.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load blog posts');
    } finally {
      setLoading(false);
    }
  };

  const handlePostClick = (post: BlogPost) => {
    setSelectedPost(post);
  };

  const handleBack = () => {
    setSelectedPost(null);
  };

  const handleLoadMore = () => {
    setSkip(skip + limit);
  };

  const handleLoadPrevious = () => {
    setSkip(Math.max(0, skip - limit));
  };

  // Detail view
  if (selectedPost) {
    return (
      <div className="read-page">
        <div className="read-container">
          <button onClick={handleBack} className="back-button">
            ← Back to articles
          </button>
          <article className="article-detail">
            <h1>{selectedPost.title}</h1>
            <div className="article-meta">
              <span>{new Date(selectedPost.published_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}</span>
            </div>
            <div className="article-body">
              {selectedPost.article_body.split('\n').map((paragraph, idx) => (
                <p key={idx}>{paragraph}</p>
              ))}
            </div>
            {selectedPost.claim_card_ids.length > 0 && (
              <div className="article-references">
                <h3>Referenced Claim Cards</h3>
                <p className="references-note">
                  This article references {selectedPost.claim_card_ids.length} claim card
                  {selectedPost.claim_card_ids.length !== 1 ? 's' : ''}.
                  View the full audit library on the <a href="/audits">Audits</a> page.
                </p>
              </div>
            )}
          </article>
        </div>
      </div>
    );
  }

  // List view
  return (
    <div className="read-page">
      <div className="read-container">
        <div className="page-header">
          <div>
            <h1>Read</h1>
            <p className="subtitle">In-depth articles analyzing religious claims</p>
          </div>
          {total > 0 && (
            <div className="total-count">
              {total} article{total !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠</span>
            <span>{error}</span>
          </div>
        )}

        {loading && posts.length === 0 ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading articles...</p>
          </div>
        ) : posts.length === 0 ? (
          <div className="empty-state">
            <h2>No articles yet</h2>
            <p>Published blog articles will appear here.</p>
          </div>
        ) : (
          <>
            <div className="articles-list">
              {posts.map((post) => (
                <article
                  key={post.id}
                  className="article-card"
                  onClick={() => handlePostClick(post)}
                >
                  <h2>{post.title}</h2>
                  <div className="article-excerpt">
                    {post.article_body.slice(0, 300)}...
                  </div>
                  <div className="article-footer">
                    <span className="article-date">
                      {new Date(post.published_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </span>
                    <span className="read-more">Read more →</span>
                  </div>
                </article>
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
                  Showing {skip + 1}-{skip + posts.length} of {total}
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
      </div>
    </div>
  );
}
