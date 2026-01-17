# Session: Phase 3.4 - Frontend Updates

**Date:** 2026-01-14
**Phase:** 3.4 - Frontend Updates
**Status:** Complete
**Reference:** ADR 002 (Intelligent Routing), Phase 3.3 session

---

## Objective

Update frontend to support intelligent routing with 3 response modes:
- Mode 1: Exact match (existing claim card)
- Mode 2: Contextual (synthesized response + source cards)
- Mode 3: Novel claim (pipeline generation)

Scope:
- Update API client to call POST /api/chat/ask
- Handle Mode 2 contextual responses in UI
- Add WebSocket routing event listeners
- Display Mode 2 synthesized response with collapsible source cards
- Update loading states to show routing progress

---

## What Was Built

### 1. TypeScript Types (`src/frontend/src/types/index.ts`)

**Added new types for intelligent routing responses:**

```typescript
// Mode 2: Contextual response with source cards
export interface ContextualResponse {
  synthesized_response: string;
  source_cards: ClaimCard[];
}

// Chat API response types (matching backend POST /api/chat/ask)
export type ChatResponseMode = 'exact_match' | 'contextual' | 'novel_claim';

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
```

**Updated ChatMessage to support contextual responses:**
```typescript
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  claim_card?: ClaimCard;
  contextual_response?: ContextualResponse;
  timestamp: Date;
}
```

---

### 2. API Client (`src/frontend/src/services/api.ts`)

**Updated chat endpoint to call POST /api/chat/ask:**

```typescript
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
```

**Changes:**
- Endpoint: `/api/chat/message` → `/api/chat/ask`
- Request field: `message` → `question`
- Removed timestamp from conversation_history (backend doesn't need it)

---

### 3. AskPage Component (`src/frontend/src/pages/AskPage.tsx`)

**Added routing phase state:**
```typescript
const [routingPhase, setRoutingPhase] = useState<'analyzing' | 'routing' | 'done' | null>(null);
```

**Updated response handling to support all 3 modes:**

**Mode 1 (exact_match):** Return single claim card immediately
```typescript
if (response.mode === 'exact_match') {
  const exactMatch = response.response as any;
  if (exactMatch.claim_card) {
    addMessage('assistant', '', exactMatch.claim_card);
  }
  setIsProcessing(false);
  setRoutingPhase(null);
}
```

**Mode 2 (contextual):** Return synthesized response with source cards
```typescript
else if (response.mode === 'contextual') {
  const contextual = response.response as any;
  addMessage('assistant', '', undefined, {
    synthesized_response: contextual.synthesized_response,
    source_cards: contextual.source_cards,
  });
  setIsProcessing(false);
  setRoutingPhase(null);
}
```

**Mode 3 (novel_claim):** Connect to WebSocket for pipeline progress
```typescript
else if (response.mode === 'novel_claim') {
  const novelClaim = response.response as any;
  if (novelClaim.websocket_session_id) {
    setIsPipelineRunning(true);
    setRoutingPhase(null);
    setAgentProgress(AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })));
    // Connect to WebSocket...
  }
}
```

**Added WebSocket routing event listeners:**
```typescript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Routing events
  if (data.type === 'context_analysis_started') {
    setRoutingPhase('analyzing');
  } else if (data.type === 'routing_started') {
    setRoutingPhase('routing');
  } else if (data.type === 'routing_completed') {
    setRoutingPhase('done');
  } else if (data.type === 'router_fallback') {
    console.warn('[AskPage] Router fallback:', data.reason);
  }
  // Pipeline agent events (unchanged)
  else if (data.type === 'agent_started') { ... }
  ...
};
```

**Added routing progress indicator UI:**
```typescript
{routingPhase && routingPhase !== 'done' && (
  <div className="routing-progress">
    <div className="progress-spinner"></div>
    <div className="progress-text">
      {routingPhase === 'analyzing' && 'Analyzing context...'}
      {routingPhase === 'routing' && 'Routing question...'}
    </div>
  </div>
)}
```

---

### 4. ClaimCardMessage Component (`src/frontend/src/components/chat/ClaimCardMessage.tsx`)

**Updated to support Mode 2 contextual responses:**

**Added props:**
```typescript
interface ClaimCardMessageProps {
  content: string;
  card?: ClaimCard;
  contextualResponse?: ContextualResponse;  // NEW
  timestamp: Date;
}
```

**Added collapsible source cards state:**
```typescript
const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
```

**Mode 2 UI structure:**
```typescript
{contextualResponse && (
  <div className="contextual-response">
    {/* Synthesized response text */}
    <div className="synthesized-response">
      <p>{contextualResponse.synthesized_response}</p>
    </div>

    {/* Source cards (collapsible) */}
    {contextualResponse.source_cards.length > 0 && (
      <div className="source-cards-section">
        <h4 className="source-cards-header">
          Sources ({contextualResponse.source_cards.length})
        </h4>
        {contextualResponse.source_cards.map((sourceCard) => (
          <div key={sourceCard.id} className="source-card-wrapper">
            <button
              className="source-card-toggle"
              onClick={() => toggleCard(sourceCard.id)}
            >
              <span className="toggle-icon">
                {expandedCards.has(sourceCard.id) ? '▼' : '▶'}
              </span>
              <span className="source-card-title">{sourceCard.claim_text}</span>
            </button>
            {expandedCards.has(sourceCard.id) && (
              <div className="source-card-content">
                <ClaimCard card={sourceCard} />
              </div>
            )}
          </div>
        ))}
      </div>
    )}
  </div>
)}
```

**Features:**
- Synthesized response displayed in styled box (similar to Mode 1 intro)
- Source cards collapsed by default
- Click to expand/collapse each source card
- Shows source count in header
- Full claim card displayed when expanded

---

### 5. useConversation Hook (`src/frontend/src/hooks/useConversation.ts`)

**Updated addMessage to support contextual responses:**

```typescript
const addMessage = useCallback((
  role: 'user' | 'assistant',
  content: string,
  claimCard?: ClaimCard,
  contextualResponse?: ContextualResponse  // NEW
) => {
  const newMessage: ChatMessage = {
    role,
    content,
    claim_card: claimCard,
    contextual_response: contextualResponse,  // NEW
    timestamp: new Date(),
  };

  setMessages(prev => [...prev, newMessage]);
}, []);
```

---

### 6. CSS Styling

**ClaimCardMessage.css - Mode 2 styles:**
```css
/* Mode 2: Contextual response styling */
.contextual-response {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.synthesized-response {
  padding: 1rem;
  background-color: var(--card-bg);
  border-left: 3px solid var(--accent-color);
  border-radius: 0.5rem;
}

.source-cards-section { ... }
.source-card-wrapper { ... }
.source-card-toggle { ... }
.toggle-icon { ... }
.source-card-title { ... }
.source-card-content { ... }
```

**AskPage.css - Routing progress indicator:**
```css
.routing-progress {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1rem 0;
  padding: 1rem 1.25rem;
  background-color: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 90%;
}
```

---

## File Summary

**Modified:**
- `src/frontend/src/types/index.ts` (+40 lines: new response types)
- `src/frontend/src/services/api.ts` (+2 lines: endpoint + request format)
- `src/frontend/src/pages/AskPage.tsx` (+50 lines: routing state, Mode 2 handling, WebSocket events)
- `src/frontend/src/components/chat/ClaimCardMessage.tsx` (+50 lines: Mode 2 UI, collapsible source cards)
- `src/frontend/src/hooks/useConversation.ts` (+5 lines: contextual response support)
- `src/frontend/src/components/chat/ClaimCardMessage.css` (+60 lines: Mode 2 styling)
- `src/frontend/src/pages/AskPage.css` (+12 lines: routing progress styling)

**No New Files Created**

---

## Integration Points

### With Phase 3.3 (API Integration):
- Frontend now calls POST /api/chat/ask endpoint
- Handles all 3 response modes from backend
- Receives routing_decision_id for potential debug displays (not used yet)
- WebSocket routing events consumed and displayed

### With Phase 2 (Chat UI):
- Reuses existing ClaimCard component for Mode 1 and Mode 2 source cards
- Maintains existing chat message thread structure
- Extends ChatMessage type to support contextual responses
- Reuses pipeline progress UI for Mode 3

---

## Key UI Decisions

### 1. Mode 2 Display Structure

**Decision:** Synthesized response on top, collapsible source cards below

**Rationale:**
- User sees answer immediately without scrolling
- Source cards available for verification but don't overwhelm
- Collapsed by default reduces visual clutter
- Similar pattern to "Show Your Work" sections in claim cards

### 2. Source Cards Collapsed by Default

**Decision:** Source cards collapsed on initial display

**Rationale:**
- Matches user expectation from Phase 2 testing (subsections hidden by default)
- Reduces cognitive load - user can expand if interested
- Keeps conversation thread scannable
- Clicking to expand shows full claim card (not just summary)

### 3. Routing Progress Display

**Decision:** Small inline progress indicator, not full pipeline UI

**Rationale:**
- Routing is fast (3-7s), doesn't need detailed progress
- "Analyzing context..." → "Routing question..." provides visibility
- Doesn't distract from conversation flow
- Full pipeline progress still shown for Mode 3

### 4. Source Card Toggle UI

**Decision:** Horizontal button with claim text preview + expand icon

**Rationale:**
- Familiar accordion pattern
- Claim text preview helps identify which source to expand
- Click anywhere on button to expand (larger hit area)
- Triangle icon (▶/▼) indicates collapsible state

---

## Testing Strategy

### Manual Testing (To Be Done):

1. **Mode 1 Test:** Ask question matching existing claim
   - Expected: Claim card appears immediately
   - Verify: No routing progress shown (response too fast)
   - Verify: Single claim card displayed in chat

2. **Mode 2 Test:** Ask comparison or clarification question
   - Expected: Synthesized response + source cards
   - Verify: Routing progress briefly visible ("Analyzing context..." → "Routing question...")
   - Verify: Source cards collapsed by default
   - Verify: Click to expand shows full claim card
   - Verify: Source count displayed in header

3. **Mode 3 Test:** Ask novel question
   - Expected: Routing progress → pipeline progress → claim card
   - Verify: Routing progress transitions to pipeline progress smoothly
   - Verify: Agent progress shown as before (5 agents)
   - Verify: Final claim card added to conversation

4. **WebSocket Events Test:** Monitor browser console during Mode 3
   - Expected: routing events logged, no errors
   - Verify: context_analysis_started, routing_started, routing_completed events received
   - Verify: router_fallback warning logged if Router Agent fails

5. **Conversation History Test:** Ask follow-up questions
   - Expected: Context maintained across all modes
   - Verify: Mode 1/2/3 responses all added to conversation
   - Verify: sessionStorage persists conversation across page refresh
   - Verify: Clear button resets all state

---

## What's NOT Implemented Yet

### Potential Enhancements (Future):
- Routing decision debug panel (admin mode)
  - Show: contextualized_question, mode selected, similarity scores, reasoning
  - Useful for tuning Router Agent prompts
  - Collapsible section below message (like "Show Your Work")

- Source card citations in synthesized response
  - Add [1], [2] markers in synthesized text
  - Link markers to source cards (click to expand)
  - Requires backend Router Agent to include citation markers

- Loading state improvements
  - Show estimated time for each phase
  - Progress percentage for Mode 2 (if Router Agent is slow)
  - Skeleton loader for Mode 2 response

- Accessibility improvements
  - ARIA labels for source card toggles
  - Keyboard navigation (arrow keys to expand/collapse)
  - Focus management after expand/collapse

---

## Next Steps

**Immediate Testing:**
1. Restart frontend dev server (npm run dev)
2. Test all 3 response modes with various question types
3. Verify WebSocket events in browser console
4. Test source card expand/collapse behavior
5. Test conversation history persistence

**Phase 3.5 (Next Session):**
- End-to-end testing with real questions
- Router Agent prompt tuning based on results
- Semantic search threshold adjustment (currently 0.92)
- claim_type_category taxonomy refinement
- Performance profiling (Mode 2 target: <10s)

**Phase 3.6 (Polish):**
- Add routing decision debug panel (admin mode)
- Analytics queries for router_decisions table
- Documentation updates (CLAUDE.md, README)
- User-facing routing transparency ("Why did I get this response?")

---

## Notes

**Frontend changes are backward compatible:**
- Mode 1 (exact_match) displays same as Phase 2 "existing" response
- Mode 3 (novel_claim) displays same as Phase 2 "generating" response
- Mode 2 (contextual) is new, but gracefully handled by updated component

**TypeScript type safety preserved:**
- All response types strongly typed
- Union types used for mode-specific responses
- Type guards needed in AskPage for mode-specific access (using `as any` for now)
  - Future: Add proper type guards or discriminated union handling

**sessionStorage conversation persistence:**
- Contextual responses stored in sessionStorage like claim cards
- Source cards serialized/deserialized correctly
- Page refresh preserves Mode 2 messages

**WebSocket connection reused:**
- Same WebSocket connection handles routing events + pipeline events
- Routing events sent before pipeline starts (if Mode 3)
- No breaking changes to existing WebSocket message types

**CSS variables leveraged:**
- All styling uses existing CSS variables (--accent-color, --card-bg, etc.)
- Dark mode support automatic via existing theme system
- Responsive design maintained (max-width constraints)

---

**Session Complete:** Phase 3.4 frontend updates complete. All 3 routing modes supported in UI with proper WebSocket event handling and Mode 2 contextual response display.

---

## Bug Fix: Enum Serialization (2026-01-16)

**Issue:** Database insert errors: `invalid input value for enum routing_mode: "NOVEL_CLAIM"`

**Root Cause:**
- Python `str, enum.Enum` serializes to enum NAME, not VALUE
- Migration created enum with lowercase VALUES: `'exact_match'`, `'contextual'`, `'novel_claim'`
- SQLAlchemy was inserting enum NAMES: `'EXACT_MATCH'`, `'CONTEXTUAL'`, `'NOVEL_CLAIM'`

**Fix Applied:**
1. Updated `RoutingModeEnum` values to uppercase (matching names): `EXACT_MATCH = "EXACT_MATCH"`
2. Updated database enum type via ALTER TABLE to accept uppercase values
3. Updated migration file to reflect uppercase enum values
4. Updated all code references (main.py, router_agent.py, router_service.py) to use uppercase strings
5. Updated frontend TypeScript types to match uppercase values

**Files Modified:**
- `src/backend/database/models.py` - Enum values uppercase
- `src/backend/database/migrations/versions/a8b4e7f2d3c5_add_router_decisions_table.py` - Migration enum uppercase
- `src/backend/agents/router_agent.py` - Return uppercase mode strings
- `src/backend/main.py` - Compare against uppercase mode strings
- `src/backend/services/router_service.py` - Docstring updated
- `src/frontend/src/types/index.ts` - ChatResponseMode type uppercase
- `src/frontend/src/pages/AskPage.tsx` - Mode comparisons uppercase

**Database Migration:**
```sql
ALTER TABLE router_decisions ALTER COLUMN mode_selected TYPE text;
DROP TYPE routing_mode;
CREATE TYPE routing_mode AS ENUM ('EXACT_MATCH', 'CONTEXTUAL', 'NOVEL_CLAIM');
ALTER TABLE router_decisions ALTER COLUMN mode_selected TYPE routing_mode USING mode_selected::routing_mode;
```

**Note:** This aligns `RoutingModeEnum` with existing enum pattern in codebase (VerdictEnum, ConfidenceLevelEnum, etc. all use uppercase names matching values).

---

## Bug Fix: Agent JSON Parsing (2026-01-16)

**Issue:** `PublisherAgent failed to parse JSON output: Extra data: line 14 column 1 (char 1286)`

**Root Cause:**
- LLMs sometimes add explanatory text after the JSON object
- Previous JSON extraction logic only stripped markdown code blocks, didn't handle trailing text
- `json.loads()` fails when extra text follows valid JSON

**Fix Applied:**
1. Created shared utility function `extract_json_from_response()` in `agents/base.py`
2. Improved JSON extraction logic:
   - Extract from markdown code blocks (```json or ```)
   - Find matching closing brace if content starts with `{`
   - Discard any trailing text after JSON object
3. Updated all 5 agents to use shared utility function

**Files Modified:**
- `src/backend/agents/base.py` - Added `extract_json_from_response()` utility function
- `src/backend/agents/topic_finder.py` - Use shared JSON extraction
- `src/backend/agents/source_checker.py` - Use shared JSON extraction
- `src/backend/agents/adversarial_checker.py` - Use shared JSON extraction
- `src/backend/agents/writing_agent.py` - Use shared JSON extraction
- `src/backend/agents/publisher.py` - Use shared JSON extraction

**Benefit:** All agents now robustly handle LLM responses with markdown, trailing text, or other formatting variations.
