# ADR 001: Core Architecture & System Design

**Status:** Accepted
**Date:** 2026-01-12
**Deciders:** User + Claude

---

## Context

Build a claim-analysis platform for Christianity-related claims. Users in deconversion or questioning stages need fast, accurate, sourced answers to apologetics claims. The system audits claims (not beliefs) through a transparent multi-agent verification pipeline.

Core requirement: Every answer must be audited through a 5-agent pipeline. No shortcuts, no LLM ad-hoc responses.

---

## Decisions

### 1. Tech Stack

**Backend:** Python + FastAPI
- AI ecosystem dominance (anthropic, openai libraries)
- Async/await for LLM orchestration
- Pydantic for type safety

**Frontend:** React
- Interactive UI (not dashboard-style)
- Component reusability for claim cards
- Real-time WebSocket updates

**Database:** PostgreSQL + pgvector extension
- Single database (no microservices)
- pgvector for semantic search of existing claims
- JSONB for flexible agent audit trails
- Full-text search built-in

**Deployment:**
- Python venv for dependency isolation (shared dev server)
- Services bind to 0.0.0.0 (accessible on internal network)
- Separate database/user from other projects

---

### 2. Multi-Agent Pipeline

**Five agents run sequentially** (each depends on previous output):

1. **Topic Finder Agent** - Identifies claim + claimant + why it matters
2. **Source Checker Agent** - Collects primary historical sources + scholarly consensus
3. **Adversarial Checker Agent** - Attempts to falsify the draft, verifies quotes/sources
4. **Writing Agent** - Produces final prose (calm, direct, forensic tone)
5. **Transparency/Publisher Agent** - Publishes content + audit summary + limitations

**LLM Strategy:**
- Different LLMs per agent based on strengths (currently: Anthropic + OpenAI keys)
- System prompts stored in database (editable without code changes)
- Each agent configurable: provider, temperature, max_tokens

**Execution:**
- Sequential for single claim (~45-60s)
- Parallel pipelines if question decomposes into multiple claims
- Real-time WebSocket progress updates to frontend
- Fail fast: No retries, no defaults, no placeholders

---

### 3. Chat vs Blog Architecture

**Chat Mode:**
- User asks any question
- Context Analyzer reformulates with conversation history
- Semantic search existing claim cards (pgvector, >0.92 similarity match)
- If match found: Return pre-audited card instantly (~2s)
- If novel: Run full 5-agent pipeline with live progress (45-60s)
- Conversational synthesis allowed for comparing/clarifying existing audited claims
- Session-based: conversation context preserved (frontend sessionStorage)

**Blog Mode:**
- Curated feed of claim cards (auto-generated + reviewed)
- Claim cards = pre-audited knowledge base powering chat

**Critical constraint:** Semantic search is a cache of audited claims, NOT a bypass. Novel claims always run full pipeline.

### Chat Interface Philosophy

**Two-layer architecture:**

1. **Data integrity layer:** All factual claims audited through 5-agent pipeline (no shortcuts)
   - Novel factual claim: "Did X happen?" → Full pipeline required
   - Every claim card goes through all 5 agents
   - No ad-hoc generation of factual assertions

2. **Conversational layer:** Natural navigation of audited claims (fast synthesis encouraged)
   - Comparison: "Which is more likely based on what we've seen?" → Fast LLM synthesis
   - Clarification: "How does this relate to X?" → Contextual explanation
   - Navigation: "What's the difference between Y and Z?" → Comparative analysis

**Mode distinction:**
- Making new factual claims = Pipeline audit required
- Discussing existing audited claims = Fast conversational synthesis allowed

The pipeline guarantees data integrity. The chat interface provides natural conversation.

Conversational responses don't make new factual assertions - they help users understand and explore existing audited claims. This enables fast back-and-forth dialogue without waiting 45-60s for every follow-up question.

---

### 4. Auto-Blog System

**Topic Queue:**
- Database table storing potential topics/claims to audit
- Fields: topic_text, priority, status, source, scheduled_for
- Statuses: queued, processing, completed, failed

**Scheduled Generation:**
- Configurable rate (X posts per day/week via admin settings)
- Picks highest priority queued topic
- Runs decomposer → identifies component claims
- Checks existing claims (skip duplicates)
- Runs full 5-agent pipeline for new claims
- Generates blog post from claim cards
- Queues for admin review (not auto-published)

**Auto-Suggest (Optional):**
- Configurable toggle + frequency in admin portal
- LLM + web search to find new apologetics claims from sources (AiG, WLC, etc.)
- Auto-adds to topic queue with suggested priority
- Admin reviews and adjusts

**Review & Feedback:**
- Admin interface shows generated-but-unpublished posts
- Actions: Approve | Reject | Send Feedback
- Feedback re-runs pipeline with admin notes injected as context

**Failure Handling:**
- Always fail hard and fast
- No automatic retries
- Failed topics flagged for manual review in admin portal

---

### 5. Data Model

**Design Note:** Category tags provide broad user-friendly navigation (Genesis, Canon, Doctrine, Ethics, Institutions) while claim_type remains flexible for technical accuracy. This dual approach supports The Elevator principle: simple browsing by category, depth via specific claim types.

**Claim Cards** (core entity):
- claim_text, claimant, claim_type, verdict
- short_answer, deep_answer
- confidence_level (High/Medium/Low + explanation)
- agent_audit (JSONB: full pipeline execution trace)
- embedding (vector for semantic search)
- created_at, updated_at

**Verdicts:** True | Misleading | False | Unfalsifiable | Depends on Definitions

**Sources** (separate table, linked to claim cards):
- source_type (primary historical | scholarly peer-reviewed)
- citation, url, quote_text

**Category Tags** (separate table, linked to claim cards):
- Broad navigation categories: Genesis, Canon, Doctrine, Ethics, Institutions
- Multiple categories per claim allowed
- For UI navigation and filtering (The Elevator principle)

**Apologetics Tags** (separate table, linked to claim cards):
- Technique used (quote-mining, category error, false dichotomy, etc.)
- claim_type remains flexible for technical precision

**Agent Prompts:**
- agent_name, llm_provider, system_prompt
- temperature, max_tokens
- Editable in admin portal

**Topic Queue:**
- topic_text, priority, status, source
- claim_card_ids (links to generated cards)

---

### 6. Admin Portal

**Required Features:**

1. **Topic Queue Management**
   - View/add/edit/delete topics
   - Adjust priorities
   - Bulk import

2. **Settings Dashboard**
   - Generation rate configuration
   - Auto-suggest toggle + frequency
   - Agent prompt editor (per-agent)
   - LLM provider selection per agent

3. **Review Interface**
   - Queue of unpublished blog posts
   - Claim card preview + agent audit trail
   - Approve/Reject/Send Feedback actions

4. **Failure Monitor**
   - Failed topics with error details
   - Manual retry option

---

### 7. Output Structure (Mandatory)

Every claim card must include:

1. **Claim** - Exact quote/paraphrase + source
2. **Verdict** - One of five categories
3. **Short Answer** - Plain-language summary (≤150 words)
4. **Why This Claim Persists** - Psychological/social/institutional reasons
5. **Evidence Review** - Primary sources + scholarly sources (clearly distinguished)
6. **Sources** - Separated by type (primary | scholarly)
7. **Apologetics Techniques Used** - If applicable
8. **Confidence Level** - High/Medium/Low + explanation
9. **Agent Audit Summary** - What was checked, limitations, what would change verdict

**The Elevator Principle:**
- Simple by default, depth on demand
- Bottom line always visible (standalone accurate summary)
- Details expandable (reasoning, evidence, sources, audit)
- No assumption of prior biblical/academic/theological knowledge

---

### 8. UI Expectations

- Chat interface for questions
- Blog/archive view of claim cards
- Expandable "Show Your Work" sections per claim
- Sources panel with clear primary vs scholarly distinction
- Confidence indicator (visual + explanation)
- Real-time agent progress display (WebSocket)
- No gamification, no social metrics, no user accounts

---

## Consequences

**Benefits:**
- Pre-generated claim library makes common questions instant (8-15s)
- Full audit trail preserved for every claim
- System grows smarter over time (semantic search improves with more claims)
- Admin can adjust agent behavior without code changes (DB-stored prompts)
- Transparent: users see exactly what was checked

**Trade-offs:**
- Novel questions take 45-60s (acceptable for quality)
- LLM costs for auto-blog generation (acceptable per user)
- Complex multi-agent orchestration (mitigated by Python async ecosystem)

**Constraints:**
- No logins, no tenants, no subscriptions
- No "both sides" framing, no apologetics, no advocacy
- Every factual assertion must be sourced
- Uncertainty stated explicitly
- No shortcuts around the 5-agent pipeline for novel factual claims (conversational synthesis of existing audited claims is allowed)

---

## Non-Goals

- Debates with believers
- Religious accommodation
- Neutrality framing
- Legal or educational compliance targets
- SEO optimization over accuracy
- Social features or user-generated content

---

## Success Criteria

The system succeeds if:
- User can quickly determine whether a Christian claim is BS
- Sources are clear and checkable
- Confidence feels earned, not asserted
- System explains why the claim feels convincing (even if false)
- Agent pipeline is transparent and auditable
