/**
 * API client for TheReceipts Admin backend.
 *
 * Provides typed methods for admin API endpoints.
 */

import type {
  AdminTopicsResponse,
  AdminTopicCreateRequest,
  AdminTopicUpdateRequest,
  PendingReviewsResponse,
  ReviewApproveRequest,
  ReviewRejectRequest,
  ReviewRevisionRequest,
  SchedulerSettings,
  SchedulerSettingsRequest,
  AutoSuggestSettings,
  AutoSuggestSettingsRequest,
  TopicStatus,
  ReviewStatus,
} from './types';

class AdminAPIClient {
  private baseURL: string;

  constructor() {
    // Use Vite proxy in development, direct URL in production
    this.baseURL = import.meta.env.VITE_API_BASE_URL || '';
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;

    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API request failed: ${response.status} - ${errorText}`);
      }

      return response.json();
    } catch (err) {
      clearTimeout(timeoutId);

      if (err instanceof Error) {
        if (err.name === 'AbortError') {
          throw new Error(`Request timeout: ${endpoint} (is backend running?)`);
        }
        throw err;
      }

      throw new Error(`Network error: ${endpoint}`);
    }
  }

  // Topic queue management
  async getTopics(params?: {
    skip?: number;
    limit?: number;
    status?: TopicStatus;
    review_status?: ReviewStatus;
  }): Promise<AdminTopicsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.status) searchParams.append('status', params.status);
    if (params?.review_status) searchParams.append('review_status', params.review_status);

    const query = searchParams.toString();
    const endpoint = query ? `/api/admin/topics?${query}` : '/api/admin/topics';
    return this.request<AdminTopicsResponse>(endpoint);
  }

  async createTopic(request: AdminTopicCreateRequest): Promise<any> {
    return this.request<any>('/api/admin/topics', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async updateTopic(topicId: string, request: AdminTopicUpdateRequest): Promise<any> {
    return this.request<any>(`/api/admin/topics/${topicId}`, {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  async deleteTopic(topicId: string): Promise<any> {
    return this.request<any>(`/api/admin/topics/${topicId}`, {
      method: 'DELETE',
    });
  }

  // Review workflow
  async getPendingReviews(params?: {
    skip?: number;
    limit?: number;
  }): Promise<PendingReviewsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());

    const query = searchParams.toString();
    const endpoint = query ? `/api/admin/review/pending?${query}` : '/api/admin/review/pending';
    return this.request<PendingReviewsResponse>(endpoint);
  }

  async approveBlogPost(topicId: string, request: ReviewApproveRequest): Promise<any> {
    return this.request<any>(`/api/admin/review/${topicId}/approve`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async rejectBlogPost(topicId: string, request: ReviewRejectRequest): Promise<any> {
    return this.request<any>(`/api/admin/review/${topicId}/reject`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async requestRevision(topicId: string, request: ReviewRevisionRequest): Promise<any> {
    return this.request<any>(`/api/admin/review/${topicId}/revision`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Scheduler settings
  async getSchedulerSettings(): Promise<SchedulerSettings> {
    return this.request<SchedulerSettings>('/api/admin/scheduler/settings');
  }

  async updateSchedulerSettings(request: SchedulerSettingsRequest): Promise<any> {
    return this.request<any>('/api/admin/scheduler/settings', {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  async runSchedulerNow(): Promise<any> {
    return this.request<any>('/api/admin/scheduler/run-now', {
      method: 'POST',
    });
  }

  // Auto-suggest settings
  async getAutoSuggestSettings(): Promise<AutoSuggestSettings> {
    return this.request<AutoSuggestSettings>('/api/admin/autosuggest/settings');
  }

  async updateAutoSuggestSettings(request: AutoSuggestSettingsRequest): Promise<any> {
    return this.request<any>('/api/admin/autosuggest/settings', {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  async triggerAutoSuggest(sourceText: string, sourceUrl?: string, sourceName?: string): Promise<any> {
    return this.request<any>('/api/admin/autosuggest/trigger', {
      method: 'POST',
      body: JSON.stringify({
        source_text: sourceText,
        source_url: sourceUrl,
        source_name: sourceName,
        skip_deduplication: false,
      }),
    });
  }

  async discoverTopics(): Promise<any> {
    return this.request<any>('/api/admin/autosuggest/discover', {
      method: 'POST',
    });
  }

  // Database management
  async resetDatabase(confirm: boolean): Promise<any> {
    return this.request<any>('/api/admin/database/reset', {
      method: 'POST',
      body: JSON.stringify({ confirm }),
    });
  }
}

// Export singleton instance
export const api = new AdminAPIClient();
