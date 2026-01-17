/**
 * TypeScript type definitions for TheReceipts frontend.
 *
 * Matches backend API response structures from FastAPI endpoints.
 */

// Enums matching backend
export type VerdictType = 'True' | 'Misleading' | 'False' | 'Unfalsifiable' | 'Depends on Definitions';
export type ConfidenceLevelType = 'High' | 'Medium' | 'Low';
export type SourceType = 'primary_historical' | 'scholarly_peer_reviewed';
export type TopicStatus = 'queued' | 'processing' | 'completed' | 'failed';

// Source entity
export interface Source {
  id: string;
  source_type: SourceType;
  citation: string;
  url: string | null;
  quote_text: string | null;
  usage_context: string | null;
}

// Apologetics tag entity
export interface ApologeticsTag {
  id: string;
  technique_name: string;
  description: string | null;
}

// Category tag entity
export interface CategoryTag {
  id: string;
  category_name: string;
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
  why_persists: string[] | null; // JSONB array of reasons
  confidence_level: ConfidenceLevelType;
  confidence_explanation: string;
  agent_audit: Record<string, unknown>; // JSONB field
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
  sources: Source[];
  apologetics_tags: ApologeticsTag[];
  category_tags: CategoryTag[];
}

// Agent prompt configuration
export interface AgentPrompt {
  id: string;
  agent_name: string;
  llm_provider: string;
  model_name: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  created_at: string;
  updated_at: string;
}

// Topic queue entry
export interface TopicQueueEntry {
  id: string;
  topic_text: string;
  priority: number;
  status: TopicStatus;
  source: string | null;
  claim_card_ids: string[];
  scheduled_for: string | null; // ISO timestamp
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

// API response types
export interface ClaimCardsResponse {
  claim_cards: ClaimCard[];
  pagination: {
    skip: number;
    limit: number;
    count: number;
  };
}

export interface CategoriesResponse {
  categories: string[];
  count: number;
}

export interface AgentPromptsResponse {
  agent_prompts: AgentPrompt[];
}

export interface TopicQueueResponse {
  topics: TopicQueueEntry[];
  pagination: {
    skip: number;
    limit: number;
    count: number;
  };
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

// Chat message types
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  claim_card?: ClaimCard;
  contextual_response?: ContextualResponse;
  timestamp: Date;
}

// Mode 2: Contextual response with source cards
export interface ContextualResponse {
  synthesized_response: string;
  source_cards: ClaimCard[];
}

// Chat API response types (matching backend POST /api/chat/ask)
export type ChatResponseMode = 'EXACT_MATCH' | 'CONTEXTUAL' | 'NOVEL_CLAIM';

export interface ChatResponse {
  mode: ChatResponseMode;
  response: ExactMatchResponse | ContextualResponseData | NovelClaimResponse;
  routing_decision_id: string;
  websocket_session_id?: string;
}

export interface ExactMatchResponse {
  type: 'exact_match';
  claim_card: ClaimCard;
}

export interface ContextualResponseData {
  type: 'contextual';
  synthesized_response: string;
  source_cards: ClaimCard[];
}

export interface NovelClaimResponse {
  type: 'generating';
  pipeline_status: string;
  websocket_session_id: string;
  contextualized_question: string;
}

// Blog post entity (Phase 3.5+)
export interface BlogPost {
  id: string;
  title: string;
  article_body: string;
  claim_card_ids: string[];
  published_at: string; // ISO timestamp
  created_at: string; // ISO timestamp
}

// Blog posts API response (GET /api/blog/posts)
export interface BlogPostsResponse {
  posts: BlogPost[];
  total: number;
  has_more: boolean;
}

// Audits cards API response (GET /api/audits/cards)
export interface AuditCardsResponse {
  claim_cards: ClaimCard[];
  total: number;
  has_more: boolean;
}
