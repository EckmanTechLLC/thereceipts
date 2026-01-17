# ADR 002: Intelligent Routing & Response Classification

**Status:** Proposed
**Date:** 2026-01-14
**Deciders:** User + Claude
**Related:** ADR 001 (Core Architecture)

---

## Context

Phase 2 testing revealed a critical limitation in semantic search: **it cannot distinguish between different claim TYPES about the same topic**.

### The Problem (From Testing)

**Bug #2: Semantic search matches different claims on same topic**

User flow:
1. User asks: "Couldn't have God made the evidence disappear?"
2. System returns: Flood historicity claim ("A global flood covered the entire Earth...")

These are fundamentally different claims:
- User question: Epistemology/unfalsifiability claim ("Could God hide evidence?")
- System response: Historical claim ("Did the flood happen?")

They share topic context (flood) but address completely different questions.

**Why this happens:**
- Semantic search (pgvector cosine similarity) matches on topic/keyword overlap
- Cannot understand WHAT KIND of claim is being asked
- Threshold tuning (0.85 → 0.92) doesn't solve this—it's a fundamental limitation
- Embeddings encode meaning similarity, not intent or claim type

**Impact:**
- Returns wrong information
- Breaks user trust
- User questions unfalsifiability but gets historicity argument
- System appears to not understand the question

**Similar issues from testing:**
- User asked about divine inspiration as alternative explanation
- Got same "Matthew copied Mark" claim card back
- These are different claims requiring different analysis

---

## Current Flow

```
Question
  ↓
Context Analyzer (reformulate with conversation history)
  ↓
Semantic Search (pgvector, >0.92 similarity)
  ↓
If match found → Return existing card
If no match → Run 5-agent pipeline
```

**Limitation:** The binary "match/no match" decision loses nuance. Cannot detect:
- Same claim vs new claim
- Clarifying question about existing claim
- Comparison between existing claims
- Related but different claim type

---

## Decision: LLM-Based Routing with Tools

Replace semantic search gate with **LLM reasoning layer** that has access to structured tools.

### High-Level Flow

```
Question + Conversation Context
  ↓
Context Analyzer (reformulate as before)
  ↓
Router Agent (NEW) - LLM with tools
  ├─ search_existing_claims(query) → Returns candidate claim cards
  ├─ get_claim_details(claim_id) → Fetches specific card
  └─ generate_new_claim() → Triggers full 5-agent pipeline
  ↓
Router decides response mode based on tool results
```

The Router Agent reasons about:
- Is this an exact match to an existing claim?
- Is this asking to compare/clarify existing claims?
- Is this a novel claim requiring full pipeline?
- Are there relevant claims to use as context?

---

## Response Mode Classification

The Router Agent classifies each question into one of three modes:

### Mode 1: Exact Match (~2s)
**Definition:** Question matches an existing audited claim

**Examples:**
- "Did Matthew copy Mark?" → Existing claim card
- "Was there a global flood?" → Existing claim card

**Implementation:**
- Router uses `search_existing_claims(query)` tool
- Evaluates candidates for semantic + intent match
- Returns card_id if exact match found

**Response:** Return existing claim card directly

---

### Mode 2: Contextual Response (~5-10s)
**Definition:** Question requires reasoning about existing claims but doesn't match one directly

**Examples:**
- "Which explanation is more likely?" (after seeing 2 claims)
- "How does this relate to X?" (where X is existing claim)
- "What's the difference between Y and Z?" (both existing claims)
- "Why would someone believe this?" (clarification about existing claim)

**Implementation:**
- Router uses `get_claim_details(claim_id)` for relevant cards
- Feeds card(s) to fast LLM as context
- Generates response grounded in audited claims
- No pipeline run needed—reusing existing analysis

**Response:** Fast LLM synthesis with explicit citation of source cards

**Critical distinction:** This is NOT returning the same card. It's generating a new contextual response that references specific existing cards.

---

### Mode 3: Novel Claim (~45-60s)
**Definition:** Question asks about a claim not yet audited

**Examples:**
- "Could God hide the flood evidence?" (epistemology claim, not historical)
- "Did the Council of Nicaea add books to the Bible?" (new historical claim)
- "Does Isaiah 53 predict Jesus?" (new interpretation claim)

**Implementation:**
- Router determines no existing card answers the question
- Calls `generate_new_claim()` tool
- Triggers full 5-agent pipeline
- Returns new claim card with full audit

**Response:** Newly generated claim card

---

## Tool Design

### Tool 1: search_existing_claims
**Purpose:** Query claim card database

**Parameters:**
- `query` (string): Reformulated question
- `limit` (int): Max candidates to return (default 5)

**Returns:**
- List of candidate claim cards (id, claim_text, verdict, short_answer, confidence, embedding_similarity)
- Empty list if no candidates above threshold

**Implementation notes:**
- Still uses pgvector semantic search under the hood
- Returns candidates, not decision—Router LLM decides match quality
- Lower threshold (0.80?) since LLM will filter false positives

### Tool 2: get_claim_details
**Purpose:** Fetch full claim card for contextual response

**Parameters:**
- `claim_id` (UUID): Specific card to fetch

**Returns:**
- Full claim card object (all fields)
- Null if ID not found

**Implementation notes:**
- Simple DB lookup
- Router may call multiple times for comparison questions

### Tool 3: generate_new_claim
**Purpose:** Trigger full 5-agent pipeline

**Parameters:**
- `claim_text` (string): The claim to audit
- `context` (optional string): Conversation context for agents

**Returns:**
- Pipeline execution ID (for WebSocket progress tracking)
- Final claim card once pipeline completes

**Implementation notes:**
- Async execution
- Router waits for pipeline completion
- WebSocket events sent to frontend during execution

---

## Router Agent Implementation

### LLM Configuration
- **Provider:** Anthropic (Claude Sonnet or Haiku)
- **Temperature:** 0.1 (deterministic routing)
- **Max tokens:** 4000
- **Tools:** Function calling for 3 tools above

### System Prompt (High-Level)

The Router Agent receives:
1. Reformulated question from Context Analyzer
2. Conversation history
3. Tool definitions

Prompt instructs:
- Use `search_existing_claims` first to find candidates
- Evaluate candidates for intent match (not just topic match)
- Distinguish claim TYPES: historical vs epistemology vs interpretation vs ethics
- If exact match: Return card_id
- If clarification/comparison: Use `get_claim_details` for context, generate response
- If novel: Use `generate_new_claim`
- Be conservative: When uncertain, generate new claim (favor accuracy over speed)

### Key Routing Logic

**Intent matching criteria:**
- Same topic + same claim type + same question structure = Exact match
- Same topic + different claim type = Novel claim
- Multiple existing claims referenced = Contextual response
- Clarifying question about one existing claim = Contextual response

**Example routing decisions:**
- "Did flood happen?" + existing flood historicity card = Exact match
- "Could God hide flood evidence?" + existing flood historicity card = Novel (different type)
- "Which is more likely, X or Y?" + existing X and Y cards = Contextual
- "Why do people believe X?" + existing X card = Contextual

---

## Database Schema Changes

### New Table: router_decisions
Track routing decisions for analysis/improvement

Fields:
- id (UUID)
- question_text (text)
- reformulated_question (text)
- conversation_context (JSONB)
- mode_selected (enum: exact_match, contextual, novel_claim)
- claim_cards_referenced (UUID array)
- search_candidates (JSONB: what search_existing_claims returned)
- reasoning (text: why Router chose this mode)
- response_time (interval)
- created_at (timestamp)

**Purpose:**
- Debug routing failures
- Tune Router prompts
- Analyze mode distribution
- Identify patterns for improvement

### Modified Table: claim_cards
Add field:
- claim_type_category (text): Broad classification for routing (historical, epistemology, interpretation, ethics, etc.)

**Purpose:**
- Help Router distinguish claim types
- Can be set by Topic Finder agent during pipeline
- Searchable alongside embedding

---

## API Changes

### New Endpoint: POST /api/chat/ask
Replaces current chat logic

**Request:**
```
{
  "question": "string",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response:**
```
{
  "mode": "exact_match" | "contextual" | "novel_claim",
  "response": {
    // Mode 1: claim_card object
    // Mode 2: { synthesized_response, source_cards[] }
    // Mode 3: pipeline_id (WebSocket for progress)
  },
  "reasoning": "string (optional, debug)"
}
```

### Modified WebSocket Events
Add event type for Mode 2 responses:
- `contextual_response_started`
- `contextual_response_completed`

---

## Integration Points

### 1. Context Analyzer (Existing)
- No changes needed
- Still reformulates question with conversation history
- Output feeds into Router Agent

### 2. Semantic Search (Modified Role)
- Becomes a tool called by Router, not a gate
- Returns candidates, not binary decision
- May lower threshold since LLM filters false positives

### 3. Five-Agent Pipeline (No Changes)
- Router calls pipeline when Mode 3 selected
- Pipeline execution unchanged
- Returns claim card as before

### 4. Frontend Chat UI (Minor Changes)
- Handle Mode 2 responses (new format)
- Display "Analyzing existing claims..." during Mode 2
- Show source cards referenced in Mode 2 responses
- Mode 1 and 3 rendering unchanged

---

## Implementation Task Breakdown

### Session 1: Router Agent Foundation
- Create Router Agent class with tool definitions
- Implement system prompt (initial version)
- Add router_decisions table migration
- Create router service module
- Unit tests for Router Agent initialization

### Session 2: Tool Implementation
- Implement search_existing_claims tool (wraps existing semantic search)
- Implement get_claim_details tool (DB lookup)
- Implement generate_new_claim tool (pipeline trigger)
- Add claim_type_category to claim_cards table
- Seed existing cards with claim type categories

### Session 3: API Integration
- Create POST /api/chat/ask endpoint
- Integrate Context Analyzer → Router → Tools flow
- Add router_decisions logging
- Update WebSocket events for Mode 2
- Error handling for Router failures

### Session 4: Frontend Updates
- Update chat API client for new endpoint
- Handle Mode 2 response format
- Display source cards referenced in Mode 2
- Update loading states ("Searching existing claims...", "Analyzing context...", "Generating new claim...")
- Add expandable "Routing Decision" debug section (admin only)

### Session 5: Testing & Tuning
- Test case: Same topic, different claim types (flood history vs flood evidence)
- Test case: Comparison questions
- Test case: Clarification questions
- Test case: Novel claims
- Tune Router prompt based on results
- Adjust claim_type_category taxonomy if needed

### Session 6: Polish & Documentation
- Update CLAUDE.md with Phase 3 completion
- Document Router Agent prompts
- Add routing decision analytics queries
- Performance profiling (Mode 2 should be <10s)
- Update testing notes with Router behavior

**Estimated total:** 6 sessions (4-6 hours)

---

## Success Criteria

The Router succeeds if:

1. **Claim type distinction:** "Could God hide evidence?" routes to Mode 3 (novel), not Mode 1 (flood history)
2. **Comparison handling:** "Which is more likely?" routes to Mode 2, synthesizes from existing cards
3. **Exact matches still fast:** "Did flood happen?" routes to Mode 1, returns in ~2s
4. **Transparency:** router_decisions table shows reasoning for every routing choice
5. **Conservative on ambiguity:** When uncertain, routes to Mode 3 (generate new) rather than returning wrong card

### Key Metrics

- Mode 1 response time: <2s (unchanged)
- Mode 2 response time: <10s (new capability)
- Mode 3 response time: 45-60s (unchanged)
- False positive rate (wrong Mode 1 match): <5%
- Router reasoning logged: 100%

---

## Consequences

### Benefits

1. **Solves the bug:** Can distinguish flood history from flood epistemology claims
2. **New capability:** Fast contextual responses without full pipeline (Mode 2)
3. **Transparency:** Every routing decision logged and auditable
4. **Tunable:** Router prompt can be refined based on decision logs
5. **Preserves core principle:** Novel claims still go through full 5-agent pipeline

### Trade-offs

1. **Added complexity:** Extra LLM call adds ~2-3s to all responses
2. **Cost increase:** Router LLM call per question (mitigated by using Haiku for routing)
3. **Tool calling dependency:** Requires LLM with reliable function calling (Anthropic, OpenAI)
4. **Prompt maintenance:** Router prompt becomes critical infrastructure requiring tuning

### Risks

1. **Router failure:** If Router crashes, entire chat breaks (mitigation: fallback to Mode 3)
2. **False Mode 1 routing:** If Router wrongly picks exact match, returns wrong card (mitigation: conservative tuning, decision logging)
3. **Mode 2 quality:** Contextual responses lack full audit trail (mitigation: cite source cards, mark as non-audited synthesis)

---

## Open Questions

1. **Claim type taxonomy:** What categories? (historical, epistemology, interpretation, ethics, institutional, linguistic, etc.)
2. **Mode 2 transparency:** How to show users that response is synthesized, not audited?
3. **Router model selection:** Sonnet (better reasoning) vs Haiku (faster, cheaper)?
4. **Fallback behavior:** If Router fails, default to Mode 3 or error?
5. **Threshold tuning:** Keep semantic search at 0.92 or lower since Router filters?

---

## Future Enhancements (Out of Scope)

- Multi-turn routing: Router tracks conversation state across messages
- Confidence scoring: Router assigns confidence to mode selection
- A/B testing: Compare Router vs semantic-only performance
- User feedback: "Was this the right claim?" button to improve routing
- Hybrid search: Add keyword/claim_type filters to semantic search tool
