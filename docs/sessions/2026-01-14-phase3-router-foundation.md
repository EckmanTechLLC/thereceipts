# Session: Phase 3.1 - Router Agent Foundation

**Date:** 2026-01-14
**Phase:** 3.1 - Router Agent Foundation
**Status:** Complete
**Reference:** ADR 002 (Intelligent Routing)

---

## Objective

Implement foundation for Router Agent with tool calling support:
- Router Agent class with 3 tool definitions
- Router service for tool implementations
- Database migration for router_decisions table
- Unit tests for initialization and configuration
- Agent prompt seed data

---

## What Was Built

### 1. Router Agent Class (`src/backend/agents/router_agent.py`)

**Key Features:**
- Extends BaseAgent with tool calling support
- Uses Anthropic API with function calling
- Defines 3 tools:
  1. `search_existing_claims` - Semantic search via pgvector
  2. `get_claim_details` - Fetch specific claim card
  3. `generate_new_claim` - Trigger pipeline

**Tool Execution Loop:**
- Calls LLM with tool definitions
- LLM decides which tools to use
- Executes tools and provides results back to LLM
- LLM provides final routing decision and answer

**Mode Detection:**
- `novel_claim` - If generate_new_claim tool used
- `contextual` - If get_claim_details used OR multiple searches
- `exact_match` - Single high-confidence search result (default: contextual)

**Key Methods:**
```python
async def execute(input_data) -> Dict[str, Any]
    # Main execution: routes question through tools

async def _call_llm_with_tools(user_message) -> Dict[str, Any]
    # Handles Anthropic tool calling loop

async def _execute_tool(tool_name, tool_input) -> Dict[str, Any]
    # Tool execution (placeholder - actual impl in service)

def _determine_mode(tool_results, final_answer) -> str
    # Determines routing mode from tool usage pattern
```

---

### 2. Router Service (`src/backend/services/router_service.py`)

**Purpose:** Implements actual tool logic (called by Router Agent)

**Methods:**

1. **search_existing_claims**
   - Uses EmbeddingService to generate query embedding
   - Calls ClaimCardRepository.semantic_search with pgvector
   - Returns formatted results with similarity scores
   - Default threshold: 0.92 (tuned in Phase 2)

2. **get_claim_details**
   - Fetches full claim card by UUID
   - Returns comprehensive claim data for context

3. **generate_new_claim**
   - Triggers pipeline (Phase 3.3 implementation)
   - For now, returns confirmation placeholder

4. **log_routing_decision**
   - Logs to router_decisions table for analysis
   - Tracks mode, tools used, timing, reasoning
   - Enables prompt tuning and debugging

---

### 3. Database Schema

**New Table: `router_decisions`**

```sql
CREATE TYPE routing_mode AS ENUM ('exact_match', 'contextual', 'novel_claim');

CREATE TABLE router_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    reformulated_question TEXT NOT NULL,
    conversation_context JSONB,
    mode_selected routing_mode NOT NULL,
    claim_cards_referenced UUID[],
    search_candidates JSONB,
    reasoning TEXT,
    response_time_ms INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX ix_router_decisions_mode_selected ON router_decisions(mode_selected);
CREATE INDEX ix_router_decisions_created_at ON router_decisions(created_at);
```

**New Model: `RouterDecision`**
- Added to `src/backend/database/models.py`
- Enum: `RoutingModeEnum` (exact_match, contextual, novel_claim)

**Migration:** `a8b4e7f2d3c5_add_router_decisions_table.py`

---

### 4. Agent Configuration

**Seed Data:** Added to `seed_agent_prompts.py`

**Router Agent Config:**
- Provider: Anthropic
- Model: claude-sonnet-4-5-20250929
- Temperature: 0.1 (deterministic routing)
- Max tokens: 4000

**System Prompt Strategy:**
1. Always search first with search_existing_claims
2. Distinguish claim TYPES (historical vs epistemology vs interpretation)
3. Conservative matching: exact match only if same topic AND same claim type
4. Contextual: multiple claims, comparisons, clarifications
5. Novel: genuinely new claim type
6. Prioritize accuracy over speed

**Examples in Prompt:**
- "Did flood happen?" + flood card = EXACT MATCH
- "Could God hide flood evidence?" + flood card = NOVEL (different type)
- "What's more likely, flood or myth?" = CONTEXTUAL (comparison)

---

### 5. Unit Tests (`tests/test_router_agent.py`)

**Test Coverage:**

**Initialization Tests:**
- Agent name set to "router"
- 3 tools defined
- Tool schemas validated (input_schema, required fields)

**Configuration Tests:**
- Loads Anthropic provider config
- Raises AgentConfigurationError if config missing

**Execution Tests:**
- Validates required input fields (reformulated_question, original_question)
- Builds user message with conversation history
- Includes both question forms in message

**Mode Detection Tests:**
- novel_claim when generate_new_claim called
- contextual when get_claim_details called
- Defaults to contextual for ambiguous cases

**Test Framework:**
- pytest with AsyncMock
- Mocks: Database session, agent config, LLM responses

---

## File Structure

```
src/backend/
├── agents/
│   ├── router_agent.py (NEW - 370 lines)
│   └── base.py (existing)
├── services/
│   └── router_service.py (NEW - 196 lines)
├── database/
│   ├── models.py (UPDATED - added RouterDecision, RoutingModeEnum)
│   ├── migrations/versions/
│   │   └── a8b4e7f2d3c5_add_router_decisions_table.py (NEW)
│   └── seeds/
│       └── seed_agent_prompts.py (UPDATED - added router config)

tests/
├── __init__.py (NEW)
└── test_router_agent.py (NEW - 232 lines)
```

---

## Key Decisions

### 1. Tool Calling vs Simple Completion

**Decision:** Use Anthropic tool calling (function calling) for Router Agent

**Rationale:**
- Structured tool definitions enforce correct usage
- LLM decides which tools to call based on question
- Can chain multiple tool calls (search → get_details → synthesize)
- Better than prompt engineering for structured decisions

### 2. Placeholder Tool Execution in Agent

**Decision:** RouterAgent._execute_tool returns placeholder, actual impl in service

**Rationale:**
- Agent focuses on LLM orchestration
- Service layer has access to repositories/embedding
- Cleaner separation of concerns
- Will wire up in Phase 3.2

### 3. Conservative Mode Detection

**Decision:** Default to "contextual" for ambiguous cases

**Rationale:**
- Safer to synthesize answer than return wrong card
- "exact_match" only for clear single high-confidence result
- Can tune threshold in Phase 3.4 based on router_decisions logs

### 4. Low Temperature for Router

**Decision:** Temperature 0.1 for deterministic routing

**Rationale:**
- Routing should be consistent
- Don't want creative interpretation of questions
- Tools provide flexibility, LLM provides reasoning

---

## Testing Strategy

**Phase 3.1 (This Session):**
- Unit tests for initialization, config, tool definitions
- Mock LLM responses to test mode detection logic

**Phase 3.2 (Next Session):**
- Integration tests with actual tool execution
- Test search_existing_claims with real pgvector queries
- Test get_claim_details with real database

**Phase 3.3:**
- End-to-end tests with full pipeline integration
- Test generate_new_claim triggering orchestrator

**Phase 3.4:**
- A/B testing different system prompts
- Analyze router_decisions logs for accuracy

---

## Integration Points

### With Existing Systems:

1. **Context Analyzer (Phase 2)**
   - Router receives reformulated_question from Context Analyzer
   - Context Analyzer output becomes Router input

2. **Semantic Search (Phase 2)**
   - search_existing_claims wraps existing pgvector search
   - Uses same embedding service and threshold (0.92)

3. **Claim Cards Repository (Phase 1)**
   - get_claim_details uses ClaimCardRepository
   - Returns existing claim card schema

### Future Integration (Phase 3.2+):

1. **Pipeline Orchestrator**
   - generate_new_claim will trigger orchestrator
   - Pass question through full 5-agent pipeline

2. **Chat API**
   - New POST /api/chat/ask endpoint
   - Integrates: Context Analyzer → Router → Response

3. **Frontend Chat UI**
   - Display mode-specific responses
   - Show "Analyzing existing claims..." for Mode 2

---

## What's NOT Implemented Yet

### Phase 3.2 - Tool Implementation:
- Wire Router Agent to Router Service tools
- Actual tool execution (currently placeholders)
- claim_type_category field on claim_cards (for better routing)
- Seed existing cards with claim type categories

### Phase 3.3 - API Integration:
- POST /api/chat/ask endpoint
- Context Analyzer → Router flow
- Pipeline trigger from generate_new_claim
- WebSocket events for Mode 2 progress

### Phase 3.4 - Frontend Updates:
- Handle Mode 2 contextual responses
- Display source cards referenced
- "Analyzing..." loading state

### Phase 3.5 - Tuning & Monitoring:
- Prompt tuning based on router_decisions logs
- Mode distribution analysis
- Accuracy metrics

---

## Next Steps

**Session 2 (Phase 3.2):**
1. Wire RouterAgent to RouterService tools
2. Implement actual tool execution in agent
3. Add claim_type_category to claim_cards table
4. Seed existing cards with categories
5. Integration tests with real tools

**Session 3 (Phase 3.3):**
1. Create POST /api/chat/ask endpoint
2. Integrate Context Analyzer → Router
3. Connect generate_new_claim to orchestrator
4. Update WebSocket events for routing

**Session 4 (Phase 3.4):**
1. Frontend: Handle Mode 2 responses
2. Display contextual answers with source cards
3. Loading states for routing
4. End-to-end testing

**Session 5 (Phase 3.5):**
1. Analyze router_decisions logs
2. Tune system prompt based on patterns
3. Adjust thresholds for exact match detection
4. Performance optimization

---

## Commands for Next Session

**Run migration:**
```bash
cd src/backend
source venv/bin/activate
alembic upgrade head
```

**Seed router agent config:**
```bash
python database/seeds/seed_agent_prompts.py
```

**Run tests:**
```bash
pytest tests/test_router_agent.py -v
```

---

## Notes

- Router Agent system prompt will be tuned in Phase 3.5 based on real usage
- Initial prompt emphasizes conservative exact matching
- Mode detection logic may need adjustment after testing
- router_decisions table will be critical for prompt iteration

---

**Session Complete:** Phase 3.1 foundation complete. Router Agent ready for tool integration.
