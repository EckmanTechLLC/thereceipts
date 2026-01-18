/**
 * Settings page.
 *
 * Admin interface for configuring scheduler and auto-suggest settings.
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import type { SchedulerSettings, AutoSuggestSettings } from '../types';
import './SettingsPage.css';

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Scheduler settings
  const [schedulerSettings, setSchedulerSettings] = useState<SchedulerSettings | null>(null);
  const [schedulerEnabled, setSchedulerEnabled] = useState(false);
  const [postsPerDay, setPostsPerDay] = useState(1);
  const [cronHour, setCronHour] = useState(9);
  const [cronMinute, setCronMinute] = useState(0);
  const [isUpdatingScheduler, setIsUpdatingScheduler] = useState(false);

  // Auto-suggest settings
  const [autoSuggestSettings, setAutoSuggestSettings] = useState<AutoSuggestSettings | null>(null);
  const [autoSuggestEnabled, setAutoSuggestEnabled] = useState(false);
  const [maxTopicsPerRun, setMaxTopicsPerRun] = useState(5);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.85);
  const [isUpdatingAutoSuggest, setIsUpdatingAutoSuggest] = useState(false);

  // Manual extraction form
  const [sourceText, setSourceText] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);

  // Database reset
  const [showResetConfirmation, setShowResetConfirmation] = useState(false);
  const [resetConfirmationText, setResetConfirmationText] = useState('');
  const [isResetting, setIsResetting] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);

      const [scheduler, autoSuggest] = await Promise.all([
        api.getSchedulerSettings(),
        api.getAutoSuggestSettings(),
      ]);

      setSchedulerSettings(scheduler);
      setSchedulerEnabled(scheduler.enabled);
      setPostsPerDay(scheduler.posts_per_day);
      setCronHour(scheduler.cron_hour);
      setCronMinute(scheduler.cron_minute);

      setAutoSuggestSettings(autoSuggest);
      setAutoSuggestEnabled(autoSuggest.enabled);
      setMaxTopicsPerRun(autoSuggest.max_topics_per_run);
      setSimilarityThreshold(autoSuggest.similarity_threshold);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load settings';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateScheduler = async () => {
    try {
      setIsUpdatingScheduler(true);
      setError(null);
      setSuccessMessage(null);

      await api.updateSchedulerSettings({
        enabled: schedulerEnabled,
        posts_per_day: postsPerDay,
        cron_hour: cronHour,
        cron_minute: cronMinute,
      });

      setSuccessMessage('Scheduler settings updated successfully');
      loadSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update scheduler settings';
      setError(message);
    } finally {
      setIsUpdatingScheduler(false);
    }
  };

  const handleRunSchedulerNow = async () => {
    if (!confirm('Run scheduler now? This will start generating blog posts immediately.')) return;

    try {
      setError(null);
      await api.runSchedulerNow();
      alert('Scheduler started successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to run scheduler';
      setError(message);
    }
  };

  const handleUpdateAutoSuggest = async () => {
    try {
      setIsUpdatingAutoSuggest(true);
      setError(null);
      setSuccessMessage(null);

      await api.updateAutoSuggestSettings({
        enabled: autoSuggestEnabled,
        max_topics_per_run: maxTopicsPerRun,
        similarity_threshold: similarityThreshold,
      });

      setSuccessMessage('Auto-suggest settings updated successfully');
      loadSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update auto-suggest settings';
      setError(message);
    } finally {
      setIsUpdatingAutoSuggest(false);
    }
  };

  const handleDiscoverTopics = async () => {
    if (!confirm('Discover topics now? This will search the web for recent apologetics content.')) return;

    try {
      setError(null);
      setSuccessMessage(null);
      const result = await api.discoverTopics();
      setSuccessMessage(result.message || 'Topics discovered successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to discover topics';
      setError(message);
    }
  };

  const handleExtractTopics = async () => {
    if (!sourceText.trim()) {
      setError('Source text is required');
      return;
    }

    try {
      setIsExtracting(true);
      setError(null);
      setSuccessMessage(null);

      const result = await api.triggerAutoSuggest(
        sourceText,
        sourceUrl || undefined,
        sourceName || undefined
      );

      setSuccessMessage(result.message || 'Topics extracted successfully');

      // Clear form on success
      setSourceText('');
      setSourceUrl('');
      setSourceName('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to extract topics';
      setError(message);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleResetDatabase = async () => {
    if (resetConfirmationText !== 'RESET') {
      setError('Please type "RESET" to confirm');
      return;
    }

    try {
      setIsResetting(true);
      setError(null);
      setSuccessMessage(null);

      const result = await api.resetDatabase(true);

      setSuccessMessage(
        `Database reset successfully. Deleted: ${result.deleted.claim_cards} claims, ` +
        `${result.deleted.blog_posts} blog posts, ${result.deleted.topics} topics, ` +
        `${result.deleted.router_decisions} router decisions.`
      );

      // Close modal and reset form
      setShowResetConfirmation(false);
      setResetConfirmationText('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reset database';
      setError(message);
    } finally {
      setIsResetting(false);
    }
  };

  const handleCancelReset = () => {
    setShowResetConfirmation(false);
    setResetConfirmationText('');
    setError(null);
  };

  if (loading) {
    return <div className="settings-page"><div className="loading">Loading settings...</div></div>;
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {successMessage && <div className="success-banner">{successMessage}</div>}

      {/* Scheduler Settings */}
      <div className="settings-section">
        <div className="section-header">
          <h2>Scheduler Configuration</h2>
          <button onClick={handleRunSchedulerNow} className="btn-secondary">
            Run Now
          </button>
        </div>

        {schedulerSettings && (
          <div className="current-settings">
            <strong>Current Schedule:</strong> {schedulerSettings.enabled ? 'Enabled' : 'Disabled'} -
            {schedulerSettings.posts_per_day} post(s) per day at {schedulerSettings.cron_hour.toString().padStart(2, '0')}:{schedulerSettings.cron_minute.toString().padStart(2, '0')}
          </div>
        )}

        <form className="settings-form" onSubmit={(e) => { e.preventDefault(); handleUpdateScheduler(); }}>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={schedulerEnabled}
                onChange={(e) => setSchedulerEnabled(e.target.checked)}
              />
              Enable Scheduler
            </label>
            <p className="help-text">When enabled, the scheduler will automatically generate blog posts</p>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Posts Per Day:</label>
              <input
                type="number"
                value={postsPerDay}
                onChange={(e) => setPostsPerDay(parseInt(e.target.value))}
                min={1}
                max={10}
              />
              <p className="help-text">How many blog posts to generate daily</p>
            </div>

            <div className="form-group">
              <label>Run Time (Hour):</label>
              <input
                type="number"
                value={cronHour}
                onChange={(e) => setCronHour(parseInt(e.target.value))}
                min={0}
                max={23}
              />
              <p className="help-text">Hour of day (0-23, 24-hour format)</p>
            </div>
          </div>

          <div className="form-group">
            <label>Run Time (Minute):</label>
            <input
              type="number"
              value={cronMinute}
              onChange={(e) => setCronMinute(parseInt(e.target.value))}
              min={0}
              max={59}
            />
            <p className="help-text">Minute of hour (0-59)</p>
          </div>

          <button
            type="submit"
            disabled={isUpdatingScheduler}
            className="btn-primary"
          >
            {isUpdatingScheduler ? 'Updating...' : 'Update Scheduler Settings'}
          </button>
        </form>
      </div>

      {/* Auto-Suggest Settings */}
      <div className="settings-section">
        <div className="section-header">
          <h2>Auto-Suggest Configuration</h2>
          <button onClick={handleDiscoverTopics} className="btn-secondary">
            Discover Topics
          </button>
        </div>

        {autoSuggestSettings && (
          <div className="current-settings">
            <strong>Current Settings:</strong> {autoSuggestSettings.enabled ? 'Enabled' : 'Disabled'} -
            Max {autoSuggestSettings.max_topics_per_run} topics per run (similarity threshold: {autoSuggestSettings.similarity_threshold})
          </div>
        )}

        <form className="settings-form" onSubmit={(e) => { e.preventDefault(); handleUpdateAutoSuggest(); }}>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={autoSuggestEnabled}
                onChange={(e) => setAutoSuggestEnabled(e.target.checked)}
              />
              Enable Auto-Suggest
            </label>
            <p className="help-text">When enabled, the system will automatically discover new topics</p>
          </div>

          <div className="form-group">
            <label>Max Topics Per Run:</label>
            <input
              type="number"
              value={maxTopicsPerRun}
              onChange={(e) => setMaxTopicsPerRun(parseInt(e.target.value))}
              min={1}
              max={20}
            />
            <p className="help-text">Maximum number of topics to add per auto-suggest run</p>
          </div>

          <div className="form-group">
            <label>Similarity Threshold:</label>
            <input
              type="number"
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
              min={0.5}
              max={1.0}
              step={0.05}
            />
            <p className="help-text">Minimum similarity score to consider topics as duplicates (0.5-1.0)</p>
          </div>

          <button
            type="submit"
            disabled={isUpdatingAutoSuggest}
            className="btn-primary"
          >
            {isUpdatingAutoSuggest ? 'Updating...' : 'Update Auto-Suggest Settings'}
          </button>
        </form>

        {/* Manual Topic Extraction */}
        <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid #ddd' }}>
          <h3 style={{ marginBottom: '1rem' }}>Extract Topics from Text</h3>
          <p style={{ marginBottom: '1rem', color: '#666' }}>
            Paste apologetics content below to extract topics manually (for testing or specific sources).
          </p>

          <div className="form-group">
            <label>Source Text (required):</label>
            <textarea
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Paste apologetics content here (articles, blog posts, etc.)"
              rows={8}
              style={{ width: '100%', padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.9rem' }}
            />
          </div>

          <div className="form-group">
            <label>Source URL (optional):</label>
            <input
              type="text"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://example.com/article"
              style={{ width: '100%' }}
            />
          </div>

          <div className="form-group">
            <label>Source Name (optional):</label>
            <input
              type="text"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              placeholder="Answers in Genesis"
              style={{ width: '100%' }}
            />
          </div>

          <button
            onClick={handleExtractTopics}
            disabled={isExtracting || !sourceText.trim()}
            className="btn-primary"
          >
            {isExtracting ? 'Extracting...' : 'Extract Topics'}
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="settings-section danger-zone">
        <div className="section-header">
          <h2>Danger Zone</h2>
        </div>

        <div className="danger-zone-content">
          <div className="warning-box">
            <h3>Clear Database</h3>
            <p>
              This will permanently delete all generated content while preserving system configuration.
            </p>
            <p><strong>Deleted:</strong></p>
            <ul>
              <li>All claim cards (and their sources, tags)</li>
              <li>All blog posts</li>
              <li>All topics in queue</li>
              <li>All router decisions</li>
            </ul>
            <p><strong>Preserved:</strong></p>
            <ul>
              <li>Agent prompts and configurations</li>
              <li>Verified sources library</li>
            </ul>
            <p style={{ color: '#d73a49', fontWeight: 'bold', marginTop: '1rem' }}>
              This action cannot be undone.
            </p>
          </div>

          <button
            onClick={() => setShowResetConfirmation(true)}
            className="btn-danger"
            style={{
              backgroundColor: '#d73a49',
              color: 'white',
              padding: '0.75rem 1.5rem',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold',
            }}
          >
            Clear Database
          </button>
        </div>
      </div>

      {/* Reset Confirmation Modal */}
      {showResetConfirmation && (
        <div className="modal-overlay" onClick={handleCancelReset}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Confirm Database Reset</h2>
            <p>
              You are about to permanently delete all generated content.
              This action <strong>cannot be undone</strong>.
            </p>
            <p style={{ marginTop: '1rem' }}>
              Type <strong>RESET</strong> to confirm:
            </p>
            <input
              type="text"
              value={resetConfirmationText}
              onChange={(e) => setResetConfirmationText(e.target.value)}
              placeholder="Type RESET"
              style={{
                width: '100%',
                padding: '0.5rem',
                marginTop: '0.5rem',
                fontSize: '1rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
              autoFocus
            />
            <div className="modal-actions" style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
              <button
                onClick={handleCancelReset}
                className="btn-secondary"
                disabled={isResetting}
                style={{
                  flex: 1,
                  padding: '0.75rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleResetDatabase}
                disabled={isResetting || resetConfirmationText !== 'RESET'}
                style={{
                  flex: 1,
                  padding: '0.75rem',
                  backgroundColor: resetConfirmationText === 'RESET' ? '#d73a49' : '#ccc',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: resetConfirmationText === 'RESET' ? 'pointer' : 'not-allowed',
                  fontSize: '1rem',
                  fontWeight: 'bold',
                }}
              >
                {isResetting ? 'Resetting...' : 'Reset Database'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
