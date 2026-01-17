/**
 * TypeScript type definitions for TheReceipts Admin.
 *
 * Matches backend API response structures from FastAPI endpoints.
 */

// Enums matching backend
export type VerdictType = 'True' | 'Misleading' | 'False' | 'Unfalsifiable' | 'Depends on Definitions';
export type ConfidenceLevelType = 'High' | 'Medium' | 'Low';
export type SourceType = 'primary_historical' | 'scholarly_peer_reviewed';
export type TopicStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ReviewStatus = 'pending_review' | 'approved' | 'rejected' | 'needs_revision';

// Source entity
export interface Source {
  id: string;
  source_type: SourceType;
  citation: string;
  url: string | null;
  quote_text: string | null;
  usage_context: string | null;
}

// Category tag entity
export interface CategoryTag {
  id: string;
  category_name: string;
  description: string | null;
}

// Apologetics tag entity
export interface ApologeticsTag {
  id: string;
  technique_name: string;
  description: string | null;
}

// Claim card entity (core)
export interface ClaimCard {
  id: string;
  claim_text: string;
  claimant: string | null;
  claim_type: string;
  verdict: VerdictType;
  short_answer: string;
  deep_answer: string;
  why_persists: string[] | null;
  confidence_level: ConfidenceLevelType;
  confidence_explanation: string;
  agent_audit: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  sources: Source[];
  apologetics_tags: ApologeticsTag[];
  category_tags: CategoryTag[];
}

// Blog post entity
export interface BlogPost {
  id: string;
  topic_queue_id: string;
  title: string;
  article_body: string;
  claim_card_ids: string[];
  published_at: string | null;
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
}

// Admin topic management types
export interface AdminTopic {
  id: string;
  topic_text: string;
  priority: number;
  status: TopicStatus;
  source: string | null;
  review_status: ReviewStatus;
  reviewed_at: string | null;
  admin_feedback: string | null;
  blog_post_id: string | null;
  claim_card_ids: string[];
  scheduled_for: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminTopicsResponse {
  topics: AdminTopic[];
  pagination: {
    skip: number;
    limit: number;
    count: number;
  };
}

export interface AdminTopicCreateRequest {
  topic_text: string;
  priority: number;
  source?: string;
}

export interface AdminTopicUpdateRequest {
  topic_text?: string;
  priority?: number;
  status?: string;
  source?: string;
}

// Admin review types
export interface PendingReview {
  topic: AdminTopic;
  blog_post: BlogPost | null;
  claim_cards: ClaimCard[];
}

export interface PendingReviewsResponse {
  reviews: PendingReview[];
  pagination: {
    skip: number;
    limit: number;
    count: number;
  };
}

export interface ReviewApproveRequest {
  reviewed_by: string;
  review_notes?: string;
}

export interface ReviewRejectRequest {
  reviewed_by: string;
  admin_feedback: string;
}

export interface ReviewRevisionRequest {
  reviewed_by: string;
  admin_feedback: string;
  revision_scope: 'decomposer' | 'claim_pipeline' | 'composer';
  revision_details?: Record<string, any>;
}

// Admin settings types
export interface SchedulerSettings {
  enabled: boolean;
  posts_per_day: number;
  cron_hour: number;
  cron_minute: number;
  max_concurrent: number;
}

export interface SchedulerSettingsRequest {
  enabled: boolean;
  posts_per_day: number;
  cron_hour: number;
  cron_minute: number;
}

export interface AutoSuggestSettings {
  enabled: boolean;
  max_topics_per_run: number;
  similarity_threshold: number;
  default_priority: number;
}

export interface AutoSuggestSettingsRequest {
  enabled: boolean;
  max_topics_per_run: number;
  similarity_threshold: number;
}
