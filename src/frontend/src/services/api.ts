/**
 * API client for TheReceipts backend.
 *
 * Provides typed methods for all FastAPI endpoints.
 */

import type {
  ClaimCardsResponse,
  CategoriesResponse,
  AgentPromptsResponse,
  TopicQueueResponse,
  HealthResponse,
  TopicStatus,
  ChatMessage,
  ChatResponse,
  BlogPostsResponse,
  BlogPost,
  AuditCardsResponse,
  ClaimCard,
  PublicMetricsResponse,
  SourcesResponse,
  GraphResponse,
} from '../types';

class APIClient {
  private baseURL: string;

  constructor() {
    // Use Vite proxy in development, or environment variable
    this.baseURL = import.meta.env.VITE_API_BASE_URL || '';
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed: ${response.status} - ${errorText}`);
    }

    return response.json();
  }

  // Health check
  async checkHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // Claim cards
  async getClaimCards(params?: {
    skip?: number;
    limit?: number;
    category?: string;
  }): Promise<ClaimCardsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.category) searchParams.append('category', params.category);

    const query = searchParams.toString();
    const endpoint = query ? `/api/claim-cards?${query}` : '/api/claim-cards';
    return this.request<ClaimCardsResponse>(endpoint);
  }

  // Categories
  async getCategories(): Promise<CategoriesResponse> {
    return this.request<CategoriesResponse>('/api/categories');
  }

  // Agent prompts
  async getAgentPrompts(): Promise<AgentPromptsResponse> {
    return this.request<AgentPromptsResponse>('/api/agent-prompts');
  }

  // Topic queue
  async getTopicQueue(params?: {
    skip?: number;
    limit?: number;
    status?: TopicStatus;
  }): Promise<TopicQueueResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.status) searchParams.append('status', params.status);

    const query = searchParams.toString();
    const endpoint = query ? `/api/topic-queue?${query}` : '/api/topic-queue';
    return this.request<TopicQueueResponse>(endpoint);
  }

  // Pipeline execution
  async runPipeline(question: string, websocketSessionId?: string): Promise<any> {
    return this.request<any>('/api/pipeline/test', {
      method: 'POST',
      body: JSON.stringify({
        question,
        websocket_session_id: websocketSessionId,
      }),
    });
  }

  // Chat - Intelligent routing endpoint
  async sendChatMessage(
    message: string,
    conversationHistory: ChatMessage[] = []
  ): Promise<ChatResponse> {
    return this.request<ChatResponse>('/api/chat/ask', {
      method: 'POST',
      body: JSON.stringify({
        question: message,
        conversation_history: conversationHistory.map(msg => ({
          role: msg.role,
          content: msg.content,
        })),
      }),
    });
  }

  // Blog posts (Read page)
  async getBlogPosts(params?: {
    skip?: number;
    limit?: number;
  }): Promise<BlogPostsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());

    const query = searchParams.toString();
    const endpoint = query ? `/api/blog/posts?${query}` : '/api/blog/posts';
    return this.request<BlogPostsResponse>(endpoint);
  }

  async getBlogPost(postId: string): Promise<BlogPost> {
    return this.request<BlogPost>(`/api/blog/posts/${postId}`);
  }

  // Audit cards (Audits page)
  async getAuditCards(params?: {
    skip?: number;
    limit?: number;
    category?: string;
    verdict?: string;
    search?: string;
  }): Promise<AuditCardsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.category) searchParams.append('category', params.category);
    if (params?.verdict) searchParams.append('verdict', params.verdict);
    if (params?.search) searchParams.append('search', params.search);

    const query = searchParams.toString();
    const endpoint = query ? `/api/audits/cards?${query}` : '/api/audits/cards';
    return this.request<AuditCardsResponse>(endpoint);
  }

  async getAuditCard(cardId: string): Promise<ClaimCard> {
    return this.request<ClaimCard>(`/api/audits/cards/${cardId}`);
  }

  // Public metrics (Home page)
  async getPublicMetrics(): Promise<PublicMetricsResponse> {
    return this.request<PublicMetricsResponse>('/api/public/metrics');
  }

  // Sources (Sources page)
  async getSources(params?: {
    skip?: number;
    limit?: number;
    verification_status?: string;
    source_type?: string;
  }): Promise<SourcesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.verification_status) searchParams.append('verification_status', params.verification_status);
    if (params?.source_type) searchParams.append('source_type', params.source_type);

    const query = searchParams.toString();
    const endpoint = query ? `/api/public/sources?${query}` : '/api/public/sources';
    return this.request<SourcesResponse>(endpoint);
  }

  // Knowledge graph (Graph page)
  async getGraph(): Promise<GraphResponse> {
    return this.request<GraphResponse>('/api/public/graph');
  }
}

// Export singleton instance
export const api = new APIClient();
