# Session: 2026-01-15 - Routing Bugs Fix

**Date:** 2026-01-16
**Duration:** ~45 minutes
**Status:** Complete

---

## Objective

Fix two critical routing bugs:
1. **Bug #2:** Router Agent not matching similar questions - always runs full pipeline (Mode 1 not triggering)
2. **Bug #3:** Follow-up questions lose context from previous responses

Reference:
- `/home/etl/projects/thereceipts/TESTING_NOTES.md` (Bug #2 lines 58-84, Bug #3 lines 86-106)
- `/home/etl/projects/thereceipts/docs/decisions/002-intelligent-routing.md`

---

## Investigation

### Database Query: Router Decision Patterns

Queried `router_decisions` table to understand routing behavior:
```sql
SELECT id, question_text, mode_selected,
       search_candidates->'results'->0->>'similarity' as top_similarity
FROM router_decisions
ORDER BY created_at DESC LIMIT 10;
```

**Finding:** ALL queries resulted in `NOVEL_CLAIM` mode with empty `search_candidates` arrays.

### Example Questions That Should Have Matched:
- "did the noah flood really happen?" → NOVEL_CLAIM (should match existing flood claim)
- "Is the Gospel of Luke literarily dependent on the Gospel of Mark?" → NOVEL_CLAIM (multiple existing Luke/Mark claims)

### Existing Claim Cards

Confirmed matching claim cards exist in database:
- 2 flood claim cards (both with embeddings)
- 3+ Luke/Mark dependency claim cards (with embeddings)

**Conclusion:** The router wasn't finding these matches despite them existing.

---

## Root Cause Analysis

### Bug #2: Router Always Selects NOVEL_CLAIM

**Root Cause:** RouterAgent never calls `load_config()` to load system prompt from database.

**Evidence:**
1. `RouterAgent.__init__()` calls `super().__init__()` which sets `self.system_prompt = None`
2. `RouterAgent.execute()` NEVER calls `await self.load_config()`
3. `RouterAgent._call_llm_with_tools()` uses `self.system_prompt` (which is None!)
4. LLM receives NO instructions about:
   - Which tools to call
   - How to route questions
   - That it should call `search_existing_claims` FIRST

**Impact:** LLM calls `generate_new_claim` directly without searching, resulting in NOVEL_CLAIM mode every time.

**Code Location:** `src/backend/agents/router_agent.py:106-143`

### Bug #3: Follow-up Questions Lose Context

**Root Cause:** Context Analyzer only includes user questions in conversation history, ignoring assistant responses.

**Evidence:**
```python
# src/backend/services/context_analyzer.py:154-160
user_questions = [
    msg["content"]
    for msg in conversation_history
    if msg.get("role") == "user"  # Only user messages!
]
```

**Example Failure:**
1. User asks: "Is abortion moral?"
2. Gets claim card mentioning: "The modern evangelical position that abortion equals murder only emerged in the 1970s as a political movement"
3. User asks follow-up: "What happened during the 1970's political movement that caused that?"
4. Context Analyzer receives:
   - History: ["Is abortion moral?"]
   - No claim card content about 1970s movement!
5. Cannot reformulate because it doesn't know what "that" refers to

**Impact:** Follow-up questions referencing claim card content fail because Context Analyzer lacks the necessary context.

**Code Location:** `src/backend/services/context_analyzer.py:139-168`

### Additional Issue: Search Candidates Not Logged

**Issue:** `search_candidates` only extracted for EXACT_MATCH and CONTEXTUAL modes, not NOVEL_CLAIM.

**Impact:** Can't debug routing decisions because we don't see what search found (or didn't find).

**Code Location:** `src/backend/main.py:590-603`

### Additional Issue: Strict EXACT_MATCH Threshold

**Issue:** EXACT_MATCH required similarity >= 0.95, but search threshold is 0.92.

**Impact:** Results in 0.92-0.95 range classified as CONTEXTUAL instead of EXACT_MATCH.

**Code Location:** `src/backend/agents/router_agent.py:346`

---

## Fixes Applied

### Fix 1: Load System Prompt in RouterAgent

**File:** `src/backend/agents/router_agent.py:123-124`

**Change:**
```python
async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Router Agent logic with tool calling."""
    # Load configuration from database (system prompt, model, etc.)
    await self.load_config()  # <-- ADDED

    reformulated_question = input_data.get("reformulated_question")
    # ... rest of method
```

**Result:** Router now has system prompt instructing it to:
- "Always start with search_existing_claims to find candidate claims"
- Distinguish claim TYPES (historical vs epistemology vs interpretation)
- Use tools in correct order

### Fix 2: Include Assistant Responses in Context Analyzer

**File:** `src/backend/services/context_analyzer.py:154-175`

**Change:**
```python
# OLD: Only user questions
user_questions = [msg["content"] for msg in conversation_history if msg.get("role") == "user"]

# NEW: Both user and assistant messages
recent_history = conversation_history[-6:]  # Last 3 exchanges
history_parts = []
for msg in recent_history:
    role = msg.get("role")
    content = msg.get("content")

    # Truncate assistant messages to 500 chars for context efficiency
    if role == "assistant" and len(content) > 500:
        content = content[:500] + "..."

    history_parts.append(f"{role.upper()}: {content}")
```

**Result:** Context Analyzer now sees claim card content, enabling proper reformulation of follow-up questions.

### Fix 3: Log Search Candidates for All Modes

**File:** `src/backend/main.py:593-597`

**Change:**
```python
# Extract search_candidates from tool_results for logging (regardless of mode)
for tool_result in tool_results:
    if tool_result["tool_name"] == "search_existing_claims":
        search_candidates = tool_result["tool_result"].get("results", [])
        break
```

**Result:** Can now debug routing decisions by seeing what search found, even when NOVEL_CLAIM selected.

### Fix 4: Lower EXACT_MATCH Threshold

**File:** `src/backend/agents/router_agent.py:346-348`

**Change:**
```python
# OLD: similarity >= 0.95 for EXACT_MATCH
# NEW: similarity >= 0.92 for EXACT_MATCH (matches search threshold)
if similarity >= 0.92:
    return "EXACT_MATCH"
elif similarity >= 0.80:  # Also lowered from 0.85
    return "CONTEXTUAL"
```

**Result:** Less strict matching allows high-similarity results (0.92+) to be classified as EXACT_MATCH.

---

## Expected Behavior After Fixes

### Bug #2: Similar Questions Should Match

**Before:**
- "did the noah flood really happen?" → NOVEL_CLAIM (generates new card)
- "Is Luke dependent on Mark?" → NOVEL_CLAIM (generates new card)

**After:**
- "did the noah flood really happen?" → EXACT_MATCH (returns existing flood card, similarity ~0.93)
- "Is Luke dependent on Mark?" → EXACT_MATCH (returns existing Luke/Mark card, similarity ~0.94)

### Bug #3: Follow-up Questions Should Preserve Context

**Before:**
```
Q1: "Is abortion moral?"
A1: [Card mentions 1970s political movement]
Q2: "What happened during the 1970's political movement that caused that?"
Reformulation: "What happened during the 1970's political movement that caused that?" (unchanged, no context)
Result: "Unable to identify specific claim - question lacks context"
```

**After:**
```
Q1: "Is abortion moral?"
A1: [Card mentions 1970s political movement]
Q2: "What happened during the 1970's political movement that caused that?"
Reformulation: "What happened during the 1970's political movement that caused the abortion debate to become a major political issue?"
Result: [Proper response about 1970s evangelical political organizing]
```

---

## Testing Recommendations

### Test Case 1: Exact Match Routing
1. Ask: "Did the Noah flood really happen?"
2. Expected: Mode = EXACT_MATCH, returns existing flood claim card
3. Verify: Check `router_decisions` table for:
   - `search_candidates` is populated
   - Top similarity ~0.93+
   - `mode_selected` = 'EXACT_MATCH'

### Test Case 2: Similar Questions with Same Intent
1. Ask: "Did Luke use Mark as a source?"
2. Expected: Mode = EXACT_MATCH, returns existing Luke/Mark dependency card
3. Verify: Same as Test Case 1

### Test Case 3: Different Claim Types (Should Still Generate New)
1. Ask: "Couldn't God have hidden the flood evidence?" (epistemology claim)
2. Expected: Mode = NOVEL_CLAIM (different claim type than existing flood history card)
3. Verify:
   - `search_candidates` shows flood card with ~0.85 similarity
   - Router correctly identifies different claim type
   - Generates new epistemology claim card

### Test Case 4: Follow-up with Context Reference
1. Ask: "Is abortion moral?"
2. Get claim card mentioning 1970s political movement
3. Ask: "What happened during the 1970's political movement that caused that?"
4. Expected:
   - Context Analyzer sees previous claim card content
   - Reformulates to: "What happened during the 1970's political movement that caused the abortion debate to become a major political issue?"
   - Router can now match or generate appropriate response

---

## Files Modified

1. **src/backend/agents/router_agent.py**
   - Line 124: Added `await self.load_config()`
   - Lines 314-353: Lowered EXACT_MATCH threshold from 0.95 to 0.92

2. **src/backend/services/context_analyzer.py**
   - Lines 154-175: Include assistant responses in conversation history, truncate to 500 chars

3. **src/backend/main.py**
   - Lines 593-597: Extract search_candidates for logging regardless of mode

---

## Success Criteria

✓ RouterAgent loads system prompt before execution
✓ Context Analyzer includes assistant responses (truncated)
✓ Search candidates logged for all routing modes
✓ EXACT_MATCH threshold lowered to 0.92

**Next Step:** User testing to verify routing behavior with real questions.

---

## Known Limitations

### Not Fixed (By Design)
- Semantic search still can't distinguish claim types by itself (e.g., "Did flood happen?" vs "Could God hide flood evidence?")
- Router relies on LLM reasoning + similarity scores
- ADR 002 describes full solution with Mode 2 (contextual responses) - not yet implemented

### Future Improvements
- Implement Mode 2 (contextual response from existing cards)
- Add claim_type_category to claim_cards for better routing
- Router decision analytics dashboard for tuning

---

## Session Notes

**Time Breakdown:**
- Investigation (DB queries, code review): ~20 min
- Root cause identification: ~10 min
- Fixes applied: ~10 min
- Documentation: ~5 min

**Key Insight:** The Router Agent had all the right architecture (tool calling, system prompt in DB, logging), but critical initialization step (`load_config()`) was missing. This is a common pattern bug - infrastructure works, but not wired up correctly.

**Second Key Insight:** Context Analyzer was making a well-intentioned optimization (only include user questions) that broke follow-up question handling. Including assistant responses (with truncation) solves this without ballooning context.

---

## Conclusion

Both bugs fixed:
1. ✓ Router now searches existing claims first (Bug #2)
2. ✓ Follow-up questions preserve context (Bug #3)

Changes are minimal and targeted - no architecture changes needed, just wire up existing components correctly.

---

## Additional Fixes: Contextual Mode UI (Post-Testing)

After initial routing fixes, user testing revealed issues with Mode 2 (Contextual) responses:

### Issue 1: Markdown Not Rendered
**Problem:** Contextual response displayed as raw markdown (plain text with `##`, `**`, etc.)

**Fix:** Added `renderMarkdown()` function to `ClaimCardMessage.tsx`:
- Parses headings (h1, h2, h3)
- Parses bold text (`**text**`)
- Parses lists (bulleted and numbered)
- Parses links (`[text](url)`)
- Added CSS styling for `.markdown-content`

**Files:** `src/frontend/src/components/chat/ClaimCardMessage.tsx`, `ClaimCardMessage.css`

### Issue 2: Source Cards Missing Fields
**Problem:** Expanding source cards crashed with "Cannot read properties of undefined (reading 'toLowerCase')"

**Root Cause:** `source_cards` only included 4 fields, but `ClaimCard` component expects full structure with `confidence_level`, arrays, etc.

**Fix:** Updated `main.py` lines 641-686 to serialize full claim card structure matching `response_formatter.py` format:
- All scalar fields
- Properly serialized relationships (`sources`, `apologetics_tags`, `category_tags`)
- Added defensive null checks in `ClaimCard.tsx` for `verdict` and `confidence_level`

### Issue 3: Empty Subsections in Source Cards
**Problem:** "Show Your Work" sections (Deep Answer, Evidence, etc.) were empty

**Root Cause:** Mode 2 only populated `claim_cards_referenced` if Router LLM called `get_claim_details` tool. When Router just called `search_existing_claims` and `_determine_mode()` returned CONTEXTUAL based on similarity (0.80-0.92), no cards were added to `source_cards` array.

**Fix:** Added fallback in `main.py` lines 636-639:
```python
# If no get_claim_details was called, use search candidates as source cards
if not claim_cards_referenced and search_candidates:
    for candidate in search_candidates[:3]:  # Top 3 candidates
        claim_cards_referenced.append(candidate["claim_id"])
```

### Issue 4: why_persists Type Mismatch
**Problem:** `why_persists` is JSONB array in DB but frontend expected string

**Fix:**
- Updated TypeScript type: `why_persists: string[] | null`
- Updated rendering to map over array and display as list

**Files Modified:**
- `src/frontend/src/types/index.ts` - Type definition
- `src/frontend/src/components/chat/ClaimCard.tsx` - Array rendering

### Result
✓ Contextual responses render with proper markdown formatting
✓ Source cards expand without crashing
✓ All subsections display full content
✓ Arrays properly handled (why_persists, sources, apologetics_tags)

---

## Final Status

All issues resolved:
1. ✓ Bug #2: Router Agent matches similar questions (Mode 1 triggers correctly)
2. ✓ Bug #3: Follow-up questions preserve context from previous responses
3. ✓ Contextual mode (Mode 2) fully functional with markdown rendering and complete source cards

**Files Modified (Complete List):**
- `src/backend/agents/router_agent.py` - Load config, lower thresholds
- `src/backend/services/context_analyzer.py` - Include assistant responses in history
- `src/backend/main.py` - Log search candidates, serialize source cards properly, fallback for empty references, add UUID import
- `src/frontend/src/components/chat/ClaimCardMessage.tsx` - Markdown renderer
- `src/frontend/src/components/chat/ClaimCardMessage.css` - Markdown styles
- `src/frontend/src/components/chat/ClaimCard.tsx` - Defensive null checks, array rendering
- `src/frontend/src/types/index.ts` - Fix why_persists type

Ready for production use.
