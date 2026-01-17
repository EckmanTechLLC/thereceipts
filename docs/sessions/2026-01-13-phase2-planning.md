# Phase 2 Planning Session

**Date:** 2026-01-13
**Type:** Planning/Architecture Discussion
**Participants:** User + Claude (foundation session)

---

## Context

Phase 1 (Foundation) is complete. Before implementing Phase 2 (Core Features), we needed to resolve architectural questions raised in NOTES.md, particularly around conversational chat and follow-up questions.

---

## Key Question from NOTES.md

> "Not every chat session is a novel question or lookup, what if the user responds and asks a follow up questions?"

**Decision:** Implement conversational chat with session-based context (not persisted long-term).

---

## Architecture Decisions

### 1. Conversational Flow: Hybrid Intelligent Routing

**Principle:** Every message (initial or follow-up) is treated the same way. The system reasons about context and decides how to respond.

**Flow:**
1. **Context Analyzer** - Reformulates user message with conversation history
   - Input: Conversation history + new user message
   - Output: Contextualized question (e.g., "What about Luke?" → "Did Luke copy Mark?")
   - Implementation: Lightweight LLM call (fast, cheap)

2. **Semantic Search** - Search existing claim cards
   - Uses contextualized question
   - If match >0.85 similarity → Return existing card

3. **Decision Point** - System decides next action
   - Found relevant card → Return conversationally
   - No match → Run full 5-agent pipeline

4. **Response** - Rendered as claim card in conversation thread
   - Real-time progress if pipeline runs
   - Instant if using cached card
   - User doesn't know/care about source

**Result:** System intelligently handles all follow-up types without explicit categorization.

---

### 2. Session Storage

**Approach:** Frontend-only (sessionStorage)

**What's stored:**
- Message history (user + bot messages)
- Claim card IDs referenced in conversation
- Session ID (UUID, frontend-generated)
- WebSocket session ID (for pipeline progress)

**Lifetime:** Until browser tab closes (no long-term persistence)

**Rationale:**
- Simple implementation
- No backend state management
- Natural conversation reset on tab close
- Survives page refresh within session

---

### 3. UI Design - Chat Interface

**Style:** Traditional conversational chat (like ChatGPT/Claude)

**Layout:**
- Full width utilization (desktop only, no mobile)
- Top nav: Ask | Read | Audits + theme toggle
- Message thread: Scrollable vertical conversation
- User messages: Right-aligned bubbles
- Bot responses: Left-aligned with embedded claim cards
- Input: Bottom-fixed text area + send button

**Claim Card Rendering in Chat:**
- Short answer visible by default
- Expandable sections:
  - Deep answer (expand)
  - Why this claim persists (expand)
  - Evidence review (expand)
  - Sources (expand with links)
  - Apologetics techniques (expand)
  - Agent audit trail (expand)
  - Confidence level (always visible)

**Real-time Progress:**
- During pipeline execution, show agent progress in message area
- WebSocket updates display current agent status
- Smooth transition to final claim card when complete

---

### 4. Semantic Search with Context

**Challenge:** Follow-up questions lack context ("What about Luke?")

**Solution:** Context Analyzer reformulates before search
- "What about Luke?" becomes "Did Luke copy Mark?" based on conversation history
- Semantic search uses full contextualized question
- Maintains conversation coherence

**Implementation:**
- pgvector cosine similarity on claim_text embeddings
- Threshold: >0.85 for match
- Uses OpenAI ada-002 embeddings (1536 dimensions)

---

### 5. Follow-Up Question Handling

**All follow-up types handled uniformly:**

**Clarification:**
- "Can you explain that more?" → Return same card with conversational framing

**Related claims:**
- "What about Luke?" → Context: "Did Luke copy Mark?" → Search/pipeline

**Drilling deeper:**
- "What's the archaeological evidence?" → Context adds previous topic → Search/pipeline

**Challenging answers:**
- "But what about Nicaea?" → Treat as new question with context → Search/pipeline

**Key insight:** Don't categorize follow-ups. Let Context Analyzer + semantic search decide.

---

## Phase 2 Implementation Plan

### Phase 2.1: Context Analyzer & Semantic Search
- Context Analyzer service (LLM reformulation)
- Embedding generation (OpenAI ada-002)
- Semantic search repository methods (pgvector)
- Backend endpoint: POST /api/chat/message (with optional conversation history)

### Phase 2.2: Chat Backend Integration
- Modify pipeline orchestrator to accept conversation context
- Response formatter (converts claim card to conversational response)
- Session management (temporary in-memory or Redis with TTL)

### Phase 2.3: Chat UI Implementation
- Conversational message thread component
- Message bubbles (user + bot)
- Claim card rendering in chat context
- Expandable sections ("Show Your Work")
- Session state management (sessionStorage)
- Real-time progress integration (WebSocket)

### Phase 2.4: Integration & Polish
- Wire Context Analyzer → Semantic Search → Pipeline flow
- Handle edge cases (empty history, malformed questions)
- Error states and loading indicators
- "New conversation" / "Clear chat" functionality

---

## Non-Goals for Phase 2

**Deferred to later phases:**
- Long-term conversation persistence
- User accounts/authentication
- Abuse prevention mechanisms
- Blog post images/icons (Phase 3)
- Disclaimers (Phase 4+)
- Mobile responsiveness

---

## Technical Decisions Summary

| Component | Technology/Approach |
|-----------|---------------------|
| Context Analyzer | Lightweight LLM call (Anthropic/OpenAI) |
| Embeddings | OpenAI ada-002 (1536 dimensions) |
| Vector Search | pgvector with cosine similarity |
| Session Storage | Frontend sessionStorage |
| Chat UI | Full-width message thread, expandable claim cards |
| Message Flow | Context → Search → Pipeline (if needed) |

---

## Success Criteria for Phase 2

Phase 2 succeeds when:
- User can have natural conversational interactions
- System understands context in follow-up questions
- Existing claim cards returned instantly (<2s)
- Novel claims generate through full pipeline with progress
- Chat UI is clear, expandable, and utilizes full screen
- Session persists across page refresh but clears on tab close

---

## Next Steps

1. Implement Phase 2.1 (Context Analyzer + Semantic Search)
2. Test context reformulation with sample conversations
3. Implement Phase 2.2 (Backend integration)
4. Implement Phase 2.3 (Chat UI)
5. Integrate and test end-to-end (Phase 2.4)

---

**Status:** Planning complete, ready for implementation.
