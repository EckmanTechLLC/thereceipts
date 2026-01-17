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

  const handleTriggerAutoSuggest = async () => {
    if (!confirm('Trigger auto-suggest now? This will search for new topics.')) return;

    try {
      setError(null);
      await api.triggerAutoSuggest();
      alert('Auto-suggest started successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to trigger auto-suggest';
      setError(message);
    }
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
          <button onClick={handleTriggerAutoSuggest} className="btn-secondary">
            Trigger Now
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
      </div>
    </div>
  );
}
