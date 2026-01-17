# Session: Phase 3.2 - Tool Implementation

**Date:** 2026-01-14
**Phase:** 3.2 - Tool Implementation
**Status:** Complete
**Reference:** ADR 002 (Intelligent Routing), Phase 3.1 session

---

## Objective

Wire Router Agent tools to actual implementations:
- Connect RouterAgent._execute_tool to RouterService methods
- Add claim_type_category field to database schema
- Seed existing claim cards with claim type categories
- Create integration tests for RouterService tools

---

## What Was Built

### 1. Router Agent Tool Execution (`src/backend/agents/router_agent.py`)

**Changes:**
- Replaced placeholder `_execute_tool` method with actual RouterService calls
- Added RouterService import
- Implemented error handling for tool execution

**Tool Routing Logic:**

```python
async def _execute_tool(tool_name, tool_input):
    router_service = RouterService(self.db_session)

    if tool_name == "search_existing_claims":
        # Calls router_service.search_existing_claims()
        # Returns: {status, results, count}

    elif tool_name == "get_claim_details":
        # Calls router_service.get_claim_details()
        # Returns: {status, claim} or {status, message}

    elif tool_name == "generate_new_claim":
        # Calls router_service.generate_new_claim()
        # Returns pipeline trigger confirmation
```

**Error Handling:**
- Catches exceptions during tool execution
- Returns structured error responses
- Tool failures don't crash Router Agent

---

### 2. Database Schema Update (`src/backend/database/models.py`)

**New Field: `claim_type_category`**

Added to ClaimCard model (line 77):
```python
claim_type_category = Column(Text, nullable=True)
```

**Purpose:**
- Categorizes claims by TYPE (historical, epistemology, interpretation, theological, textual)
- Distinct from `claim_type` (flexible technical categorization)
- Used by Router Agent to distinguish between different claim types about same topic

**Examples:**
- "Did flood happen?" → historical
- "Could God hide flood evidence?" → epistemology
- "What does Genesis symbolize?" → interpretation

---

### 3. Database Migration

**Migration:** `b9e5a8c4d7f6_add_claim_type_category_to_claim_cards.py`

**upgrade():**
- Adds claim_type_category column (nullable text)

**downgrade():**
- Drops claim_type_category column

**Location:** `/src/backend/database/migrations/versions/`

---

### 4. Claim Type Category Seed Script (`seed_claim_type_categories.py`)

**Purpose:** Populate claim_type_category for existing claim cards

**Algorithm:**
1. Fetch all claim cards without claim_type_category
2. Analyze claim_text with keyword matching
3. Assign category based on highest keyword match score
4. Fallback to claim_type field if no keywords match
5. Commit all updates

**Categories and Keywords:**

**historical:**
- Keywords: flood, noah, exodus, moses, resurrection, archaeological, evidence, happened, historical, event

**epistemology:**
- Keywords: faith, reason, evidence, prove, unfalsifiable, science, knowledge, belief, testable, hide, disappear

**interpretation:**
- Keywords: symbolic, literal, metaphor, interpretation, prophecy, context, meaning, represent, allegory

**theological:**
- Keywords: god's nature, omnipotent, omniscient, moral, evil, free will, divine, attributes

**textual:**
- Keywords: contradiction, authorship, translation, manuscript, gospel, canon, verse, text, biblical

**Usage:**
```bash
cd src/backend
source venv/bin/activate
python database/seeds/seed_claim_type_categories.py
```

---

### 5. RouterService Updates

**Added claim_type_category to responses:**

**search_existing_claims results:**
```python
{
    "claim_id": str,
    "claim_text": str,
    "short_answer": str,
    "similarity": float,
    "claim_type": str,
    "claim_type_category": str,  # NEW
    "verdict": str
}
```

**get_claim_details response:**
```python
{
    "claim_id": str,
    "claim_text": str,
    "claimant": str,
    "claim_type": str,
    "claim_type_category": str,  # NEW
    "verdict": str,
    "short_answer": str,
    "deep_answer": str,
    "confidence_level": str,
    "confidence_explanation": str,
    "why_persists": list,
    "created_at": str
}
```

**Benefit:** Router Agent LLM can use claim_type_category to distinguish between:
- Same claim (exact match) vs
- Different claim about same topic (novel/contextual)

---

### 6. Integration Tests (`tests/test_router_service.py`)

**New test file:** 232 lines of integration tests

**Test Coverage:**

**TestSearchExistingClaims:**
- test_search_returns_formatted_results
  - Mocks EmbeddingService and ClaimCardRepository
  - Verifies embedding generation called with query
  - Verifies semantic_search called with embedding and threshold
  - Validates result format (claim_id, claim_text, similarity, verdict)
- test_search_with_custom_threshold
  - Verifies custom threshold parameter respected

**TestGetClaimDetails:**
- test_get_claim_details_returns_full_data
  - Verifies comprehensive claim data returned
  - Checks all fields present (including claim_type_category)
- test_get_claim_details_not_found
  - Verifies None returned for missing claim
- test_get_claim_details_invalid_uuid
  - Handles invalid UUID strings gracefully

**TestGenerateNewClaim:**
- test_generate_new_claim_returns_trigger_confirmation
  - Verifies pipeline trigger placeholder returns expected structure

**TestLogRoutingDecision:**
- test_log_routing_decision_creates_record
  - Verifies RouterDecision record created
  - Checks DB session add/commit/refresh called

**TestRouterServiceIntegration:**
- test_search_then_get_details_workflow
  - Tests typical Router Agent workflow
  - Search → get top result ID → get full details

**Test Framework:**
- pytest with AsyncMock
- Patches EmbeddingService and ClaimCardRepository
- Uses MagicMock for ClaimCard models

---

## File Summary

**Modified:**
- `src/backend/agents/router_agent.py` (+45 lines tool execution, -15 lines placeholder)
- `src/backend/database/models.py` (+1 line claim_type_category field)
- `src/backend/services/router_service.py` (+2 lines claim_type_category in responses)

**Created:**
- `src/backend/database/migrations/versions/b9e5a8c4d7f6_add_claim_type_category_to_claim_cards.py` (27 lines)
- `src/backend/database/seeds/seed_claim_type_categories.py` (122 lines)
- `tests/test_router_service.py` (232 lines)

---

## Key Decisions

### 1. Tool Execution Error Handling

**Decision:** Catch exceptions in _execute_tool and return structured errors

**Rationale:**
- Tool failures shouldn't crash Router Agent
- LLM can reason about errors (e.g., "claim not found")
- Graceful degradation: if search fails, LLM can try different approach

### 2. claim_type_category as Nullable Text

**Decision:** Text field, nullable, no enum constraint

**Rationale:**
- Flexibility for future category additions
- Avoids migration complexity of enum updates
- Seed script can evolve categories without schema changes
- Router Agent prompt guides usage, not DB constraint

### 3. Keyword-Based Categorization

**Decision:** Simple keyword matching for seed script

**Rationale:**
- Good enough for initial categorization
- Fast, deterministic, no external dependencies
- Can be refined later with LLM-based categorization
- Phase 3.2 goal: get categories populated, not perfect

### 4. Include claim_type_category in Tool Results

**Decision:** Add to both search and get_claim_details responses

**Rationale:**
- Router Agent LLM needs category info to distinguish claim types
- Critical for solving "flood" vs "could God hide flood evidence" problem
- Small payload increase, high value for routing logic

---

## Testing Strategy

**Phase 3.2 (This Session):**
- Integration tests with mocked repositories
- Verifies tool implementations called correctly
- Tests result formatting and error handling

**Next Phase (3.3):**
- End-to-end tests with real database
- Test full Context Analyzer → Router → Tools flow
- Verify claim_type_category actually improves routing accuracy

---

## Integration Points

### With Phase 3.1 (Router Foundation):
- RouterAgent now calls actual RouterService methods
- Tools return real data instead of placeholders
- Mode detection can use tool result contents

### With Phase 2 (Semantic Search):
- search_existing_claims wraps existing pgvector semantic_search
- Same embedding service, same threshold (0.92 default)
- Results now include claim_type_category

### Future (Phase 3.3 - API Integration):
- POST /api/chat/ask will call Router Agent
- Tools will execute during chat request
- claim_type_category will guide routing decisions

---

## What's NOT Implemented Yet

### Phase 3.3 - API Integration:
- POST /api/chat/ask endpoint
- Context Analyzer → Router flow
- Pipeline trigger from generate_new_claim
- WebSocket events for Mode 2 progress
- router_decisions logging in API layer

### Phase 3.4 - Frontend Updates:
- Handle Mode 2 contextual responses
- Display source cards referenced
- "Analyzing..." loading state
- Show claim_type_category in UI (optional)

### Phase 3.5 - Tuning:
- Analyze router_decisions logs
- Tune system prompt based on routing patterns
- Validate claim_type_category improves accuracy
- Adjust thresholds for exact match detection

---

## Next Steps

**Session 3 (Phase 3.3 - API Integration):**
1. Create POST /api/chat/ask endpoint
2. Integrate Context Analyzer → Router → Response
3. Wire generate_new_claim to orchestrator
4. Add router_decisions logging
5. Update WebSocket events for routing progress
6. Error handling for Router failures

**Before Session 3, User Should Run:**

1. **Run migration:**
```bash
cd src/backend
source venv/bin/activate
alembic upgrade head
```

2. **Seed claim type categories:**
```bash
python database/seeds/seed_claim_type_categories.py
```

3. **Run tests (optional):**
```bash
cd /home/etl/projects/thereceipts
pytest tests/test_router_service.py -v
```

---

## Notes

**claim_type vs claim_type_category:**
- `claim_type`: Technical, flexible, set by Topic Finder Agent (e.g., "history", "science", "doctrine")
- `claim_type_category`: Routing-focused, set by seed script or future agents (e.g., "historical", "epistemology", "interpretation")
- Both serve different purposes, both are useful

**Seed Script Limitations:**
- Keyword matching is simple but effective
- May misclassify edge cases
- Future improvement: LLM-based categorization
- Current accuracy: Good enough for Phase 3 testing

**Tool Execution Performance:**
- Each tool call is an async operation
- LLM may chain multiple tool calls (search → get_details → get_details)
- Total routing time depends on tool call count
- router_decisions.response_time_ms will track this

---

**Session Complete:** Phase 3.2 tool implementation complete. Router Agent tools wired and ready for API integration.
