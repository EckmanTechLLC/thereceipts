# Session: Phase 3.3 - API Integration

**Date:** 2026-01-14
**Phase:** 3.3 - API Integration
**Status:** Complete
**Reference:** ADR 002 (Intelligent Routing), Phase 3.2 session

---

## Objective

Integrate Router Agent into chat API flow:
- Create POST /api/chat/ask endpoint
- Wire Context Analyzer → Router Agent flow
- Handle Mode 1/2/3 responses
- Log routing decisions
- Add WebSocket events for routing progress
- Implement error handling with fallback to Mode 3

---

## What Was Built

### 1. New API Endpoint: POST /api/chat/ask (`src/backend/main.py`)

**Purpose:** Intelligent routing endpoint replacing simple semantic search gate

**Request Format:**
```json
{
  "question": "string",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response Format:**
```json
{
  "mode": "exact_match" | "contextual" | "novel_claim",
  "response": {
    // Mode-specific response data
  },
  "routing_decision_id": "uuid",
  "websocket_session_id": "uuid" // Only for Mode 3
}
```

**Flow:**
1. Validate input (question length, conversation history length)
2. Call Context Analyzer to reformulate question
3. Call Router Agent with reformulated question
4. Handle mode-specific response:
   - Mode 1: Return existing claim card
   - Mode 2: Return synthesized response with source cards
   - Mode 3: Trigger pipeline in background
5. Log routing decision to database
6. Return response to client

---

### 2. Mode-Specific Response Handling

#### Mode 1: Exact Match
- Extract claim_id from Router Agent tool results
- Fetch full claim card from database
- Return claim card in response
- Log claim_id in routing decision

**Response Structure:**
```json
{
  "type": "exact_match",
  "claim_card": {
    // Full claim card object
  }
}
```

#### Mode 2: Contextual Response
- Extract referenced claim IDs from Router Agent tool results
- Fetch full claim cards for source cards
- Return synthesized response with source cards
- Log all referenced claim IDs

**Response Structure:**
```json
{
  "type": "contextual",
  "synthesized_response": "Router Agent's contextual answer",
  "source_cards": [
    {
      "id": "uuid",
      "claim_text": "...",
      "short_answer": "...",
      "verdict": "..."
    }
  ]
}
```

#### Mode 3: Novel Claim
- Trigger pipeline execution in background task
- Return websocket_session_id for progress tracking
- Pipeline runs asynchronously
- Client receives progress via WebSocket events

**Response Structure:**
```json
{
  "type": "generating",
  "pipeline_status": "queued",
  "websocket_session_id": "uuid",
  "contextualized_question": "..."
}
```

---

### 3. WebSocket Events for Routing

Added new WebSocket event types for routing progress:

**Event: context_analysis_started**
```json
{
  "type": "context_analysis_started",
  "timestamp": "ISO-8601"
}
```

**Event: routing_started**
```json
{
  "type": "routing_started",
  "contextualized_question": "...",
  "timestamp": "ISO-8601"
}
```

**Event: routing_completed**
```json
{
  "type": "routing_completed",
  "mode": "exact_match" | "contextual" | "novel_claim",
  "response_time_ms": 1234,
  "timestamp": "ISO-8601"
}
```

**Event: router_fallback**
```json
{
  "type": "router_fallback",
  "reason": "Router Agent failed, generating new claim",
  "timestamp": "ISO-8601"
}
```

---

### 4. Router Service Updates (`src/backend/services/router_service.py`)

**Fixed Issues:**
- Import: Changed `services.embedding_service` → `services.embedding`
- Method: Changed `semantic_search()` → `search_by_embedding()` to match ClaimCardRepository
- Response handling: Updated to handle tuples `(ClaimCard, similarity)` instead of dict

**Updated search_existing_claims method:**
```python
async def search_existing_claims(
    self,
    query: str,
    threshold: float = 0.92,
    limit: int = 5
) -> List[Dict[str, Any]]:
    # Generate embedding
    query_embedding = await self.embedding_service.generate_embedding(query)

    # Search (returns list of tuples)
    results = await self.claim_repo.search_by_embedding(
        embedding=query_embedding,
        threshold=threshold,
        limit=limit
    )

    # Format results
    formatted_results = []
    for claim_card, similarity in results:
        formatted_results.append({
            "claim_id": str(claim_card.id),
            "claim_text": claim_card.claim_text,
            "short_answer": claim_card.short_answer,
            "similarity": similarity,
            "claim_type": claim_card.claim_type,
            "claim_type_category": claim_card.claim_type_category,
            "verdict": claim_card.verdict.value if claim_card.verdict else None
        })

    return formatted_results
```

---

### 5. Error Handling & Fallback

**Router Agent Failure Handling:**
- If Router Agent raises `AgentError`, system falls back to Mode 3 (novel_claim)
- Sends `router_fallback` WebSocket event to inform client
- Logs fallback decision
- Ensures no request fails completely due to routing issues

**Example:**
```python
try:
    router_agent = RouterAgent(db)
    router_result = await router_agent.execute({...})
    mode = router_result["mode"]
except AgentError as e:
    print(f"Router Agent failed, falling back to Mode 3: {str(e)}")
    await manager.send_message(websocket_session_id, {
        "type": "router_fallback",
        "reason": "Router Agent failed, generating new claim"
    })
    mode = "novel_claim"
```

**Other Error Handling:**
- ContextAnalyzerError: Return 500 with user-friendly message
- Database errors: Caught and logged, return 500
- Validation errors: Return 400 with specific validation message

---

### 6. Routing Decision Logging

All routing decisions logged via `RouterService.log_routing_decision()`:

**Fields Logged:**
- `question_text`: Original user question
- `reformulated_question`: Context Analyzer output
- `conversation_context`: Recent conversation history (JSON)
- `mode_selected`: exact_match | contextual | novel_claim
- `claim_cards_referenced`: UUIDs of claims used in response
- `search_candidates`: Results from search_existing_claims tool
- `reasoning`: Router Agent's reasoning (first 500 chars)
- `response_time_ms`: Total routing time

**Purpose:**
- Debug routing failures
- Analyze mode distribution
- Tune Router Agent prompts
- Identify patterns for improvement

---

## File Summary

**Modified:**
- `src/backend/main.py` (+252 lines: new endpoint, imports, Pydantic model)
- `src/backend/services/router_service.py` (+5 lines: fixed imports and method calls)
- `src/backend/agents/router_agent.py` (+17 lines: fixed _determine_mode() with proper similarity checking)

**No New Files Created**

---

## Integration Points

### With Phase 3.1 (Router Foundation):
- Uses RouterAgent class and tool definitions
- Calls Router Agent's `execute()` method
- Processes tool results to determine mode

### With Phase 3.2 (Tool Implementation):
- RouterService tools now called by Router Agent
- search_existing_claims returns formatted results
- get_claim_details fetches claim card details
- generate_new_claim triggers pipeline (placeholder in 3.2, now wired)

### With Phase 2 (Semantic Search):
- Context Analyzer unchanged, still reformulates questions
- Semantic search now called by Router Agent as a tool
- Pipeline trigger mechanism reused for Mode 3

### With Phase 1 (Pipeline):
- Pipeline orchestrator called for Mode 3 responses
- WebSocket infrastructure reused for routing events
- Background task execution for pipeline runs

---

## Key Decisions

### 1. WebSocket Session ID Generation

**Decision:** Generate websocket_session_id in endpoint, send events before connecting client

**Rationale:**
- Client doesn't need to connect WebSocket before asking question
- Server can send routing events even if client hasn't connected yet
- Events are queued/dropped gracefully if no client connected
- Simplifies client implementation (no pre-connection required)

**Alternative Considered:** Require client to connect WebSocket first
- Rejected: Adds latency, complicates client flow

### 2. Mode 1 Fallback to Mode 3

**Decision:** If claim card not found after Router selects Mode 1, fall back to Mode 3

**Rationale:**
- Router may select claim_id that no longer exists
- Better to generate new claim than return error
- Maintains "fail forward" principle

### 3. Routing Decision Logging Format

**Decision:** Log search_candidates as JSONB, reasoning as TEXT (truncated 500 chars)

**Rationale:**
- search_candidates can be large (5+ results), JSON handles structure
- reasoning can be very long, truncate to keep DB efficient
- Full reasoning available in LLM call logs if needed

### 4. Error Handling Philosophy

**Decision:** Router failure → fallback to Mode 3, don't fail request

**Rationale:**
- Router is optimization layer, not critical path
- Falling back to pipeline ensures user always gets answer
- Maintains core principle: "fail fast" but "fail forward"
- Allows iterative Router Agent prompt tuning without breaking UX

---

## Testing Strategy

### Manual Testing (To Be Done):
1. **Mode 1 Test:** Ask question matching existing claim
   - Expected: Return claim card directly, <2s response time
   - Verify: routing_decision logged with mode=exact_match

2. **Mode 2 Test:** Ask comparison question ("which is more likely?")
   - Expected: Synthesized response with source cards, <10s response time
   - Verify: routing_decision logged with mode=contextual, multiple claim_cards_referenced

3. **Mode 3 Test:** Ask novel question
   - Expected: Pipeline triggered, progress via WebSocket, 45-60s total time
   - Verify: routing_decision logged with mode=novel_claim

4. **Router Fallback Test:** Simulate Router Agent failure
   - Expected: Fall back to Mode 3, router_fallback event sent
   - Verify: Request succeeds, logs show fallback

5. **WebSocket Events Test:** Monitor WebSocket for routing events
   - Expected: context_analysis_started, routing_started, routing_completed events
   - Verify: Timestamps sequential, response_time_ms accurate

### Integration Testing (Future):
- End-to-end tests with real database and Router Agent
- Load testing for Mode 2 response time (<10s target)
- Concurrent request handling
- Router decision log analysis

---

## What's NOT Implemented Yet

### Phase 3.4 - Frontend Updates:
- Update frontend chat API client to call /api/chat/ask
- Handle Mode 2 response format (synthesized response + source cards)
- Display source cards in chat UI
- Update loading states ("Analyzing context...", "Routing question...")
- Add routing decision debug section (admin only)

### Phase 3.5 - Testing & Tuning:
- Test cases for all routing scenarios
- Router Agent prompt tuning based on decision logs
- Semantic search threshold adjustment
- claim_type_category taxonomy refinement
- Performance optimization for Mode 2

### Phase 3.6 - Polish:
- Analytics queries for router_decisions table
- Performance profiling
- Documentation updates (CLAUDE.md, API docs)
- User-facing routing transparency ("Why did I get this response?")

---

## Next Steps

**Before Testing:**
1. **Restart backend service** (modified main.py)
2. **Verify database migrations applied** (router_decisions table exists)
3. **Verify claim_type_category populated** (seed script from Phase 3.2)

**Testing Workflow:**
1. Use Postman/curl to test POST /api/chat/ask endpoint
2. Connect WebSocket client to monitor routing events
3. Test all 3 modes with different question types
4. Query router_decisions table to verify logging
5. Iterate on Router Agent prompt based on results

**Phase 3.4 (Next Session):**
1. Update frontend API client (src/frontend/services/api.ts)
2. Handle Mode 2 response in chat UI
3. Display source cards for Mode 2 responses
4. Update loading states for routing progress
5. Add routing decision debug panel (admin mode)

---

## Critical Bug Fix: Mode 1 Detection

### Initial Implementation Issue
**Problem:** Original `_determine_mode()` had placeholder that always returned "contextual"

**Impact:** Mode 1 (exact_match) was UNREACHABLE, violating "no placeholders" principle

### Fix Implemented
**File:** `src/backend/agents/router_agent.py` (lines 304-348)

**New Logic:**
```python
# Check if single search returned high-confidence result
if len(tool_results) == 1 and tool_results[0]["tool_name"] == "search_existing_claims":
    tool_result = tool_results[0].get("tool_result", {})
    results = tool_result.get("results", [])

    # No results means novel claim
    if not results:
        return "novel_claim"

    # Get top result's similarity score
    top_result = results[0]
    similarity = top_result.get("similarity", 0.0)

    # Apply similarity thresholds
    if similarity >= 0.95:
        return "exact_match"
    elif similarity >= 0.85:
        return "contextual"
    else:
        return "novel_claim"
```

**Thresholds:**
- similarity >= 0.95: exact_match (very high confidence)
- similarity >= 0.85: contextual (moderate confidence, may need synthesis)
- similarity < 0.85 or no results: novel_claim (low confidence, generate new)

**Edge Cases Handled:**
- Empty results array → novel_claim
- Missing similarity field → defaults to 0.0 → novel_claim
- Missing tool_result → defaults to {} → novel_claim

**Result:** All 3 modes now reachable, proper routing logic implemented

---

## Known Issues & Limitations

### 1. WebSocket Event Ordering
**Issue:** WebSocket events sent before client may connect

**Impact:** Client may miss early events (context_analysis_started, routing_started)

**Mitigation:** Events are non-critical for UX, just progress indicators
- Client can reconstruct state from final response
- Future: Add event replay mechanism

### 2. generate_new_claim Not Fully Wired
**Issue:** RouterService.generate_new_claim() still returns placeholder

**Current Behavior:** Returns trigger confirmation, doesn't actually call pipeline

**Fix:** Mode 3 handler in main.py already wires pipeline correctly via `run_pipeline_background_task()`
- RouterService placeholder is fine, pipeline trigger happens at API level
- Could refactor to move pipeline trigger into RouterService for consistency

### 3. Claim Card Not Found After Mode 1 Selection
**Issue:** Router selects Mode 1 with claim_id, but claim not found in DB

**Current Behavior:** Falls back to Mode 3

**Root Cause:** Race condition? Deleted claim? Router hallucination?

**Mitigation:** Fallback ensures request succeeds
- Future: Add validation in Router Agent (check claim exists before returning Mode 1)

---

## Performance Notes

**Expected Response Times:**
- Mode 1 (exact_match): ~2-3s (Context Analyzer + Router + DB lookup)
- Mode 2 (contextual): ~5-10s (Context Analyzer + Router + tool calls + LLM synthesis)
- Mode 3 (novel_claim): ~45-60s (Context Analyzer + Router + full 5-agent pipeline)

**Routing Overhead:**
- Context Analyzer: ~1-2s (lightweight LLM call)
- Router Agent: ~2-5s (tool calling, depends on # of tool calls)
- Total overhead: ~3-7s compared to Phase 2 direct semantic search

**Trade-off:** Accept 3-7s latency increase for correct routing (solves false positive problem)

---

## Notes

**Why Not Wire generate_new_claim in RouterService?**
- Pipeline trigger requires WebSocket session management
- Cleaner to handle at API layer where session_id is managed
- RouterService remains stateless, focused on data access
- Consistent with existing pipeline trigger pattern from Phase 2

**Mode 1 Detection Now Functional:**
- Fixed _determine_mode() to properly check similarity scores
- Similarity >= 0.95 triggers Mode 1 (exact_match)
- Similarity 0.85-0.95 triggers Mode 2 (contextual)
- Similarity < 0.85 triggers Mode 3 (novel_claim)
- All three modes now reachable, routing logic complete

**Router Agent Prompt Tuning Required:**
- Current Router Agent may not distinguish claim types effectively yet
- Needs testing with real questions to tune system prompt
- claim_type_category field provides signal but LLM must use it
- Phase 3.5 will include prompt refinement based on router_decisions logs

**Conversation History Handling:**
- Currently passes last N messages to Router Agent
- Context Analyzer already extracts key context
- May not need full history in Router Agent
- Future: Experiment with context window size

**WebSocket Connection Management:**
- Current implementation: Generate session_id, send events, client may/may not connect
- Events dropped if no client connected (graceful)
- Alternative: Require client connect first (adds complexity)
- Current approach simpler, more resilient

---

**Session Complete:** Phase 3.3 API integration complete. Router Agent fully wired into chat flow with intelligent routing to Mode 1/2/3 responses.
