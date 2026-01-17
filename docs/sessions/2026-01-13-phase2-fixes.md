# Session: Phase 2 Fixes

**Date:** 2026-01-13
**Phase:** Phase 2 (Conversational Chat) - Bug Fixes
**Status:** Complete

---

## Overview

Fixed 5 issues discovered during Phase 2 testing. All fixes are backend/frontend integration improvements that enhance UX and data quality.

---

## Issues Fixed

### 1. Follow-up Questions Return Same Claim Card (CRITICAL) ✓

**Problem:** ALL questions returning the same claim card, even completely unrelated ones.

**Root Cause:** Semantic search threshold too low (0.85). Related but different claims were matching.
Example: "Could divine inspiration explain gospel similarities?" matched "Matthew independent from Mark" with 0.894 similarity because both are about gospel relationships, but they're OPPOSING claims about the same topic.

**Fix:**
- Raised threshold from 0.85 → 0.92
- Tested extensively with various questions
- Now correctly distinguishes:
  - Same claim, different wording (0.92+ → returns existing card)
  - Different claim, same topic (< 0.92 → generates new card)
- File: `src/backend/config.py:34`

**Test Results:**
- "Did Matthew copy Mark?" → 0.923 similarity → Match ✓
- "Is Matthew independent from Mark?" → 0.950 → Match ✓
- "Could divine inspiration explain...?" → 0.894 → No match, new card ✓
- "Did Luke copy Mark?" → No match, new card ✓

### 2. Context Analyzer Not Recognizing Alternative Explanations ✓

**Problem:** Alternative explanations treated as clarifications, not new claims.
Example: "Couldn't divine inspiration explain this?" should be a NEW claim about divine inspiration, not clarification of copying claim.

**Root Cause:** Context Analyzer prompt didn't distinguish between:
- Clarifying questions about same claim
- Alternative explanations (new claims)

**Fix:**
- Updated `context_analyzer.py` system prompt to recognize alternative explanations
- Added examples showing "couldn't X explain this?" patterns
- Reformulates alternatives as new standalone claims
- File: `src/backend/services/context_analyzer.py:27-63`

**Test Result:**
- Input: "How do we know Matthew was copying? Couldn't they have determined the exact same messaging through divine inspiration?"
- Output: "Could divine inspiration explain the similarities between Matthew and Mark's gospels?"
- Correctly reformulated as NEW claim ✓

### 3. Sources Missing URLs, Context, Quotes ✓

**Problem:** Sources listed without:
- URLs (can't access or purchase)
- Context (how source was used)
- Quotes (what source actually said)

**Fixes:**

**Backend:**
- Added `usage_context` field to Source model (`database/models.py:124`)
- Created migration: `f01c3b619027_add_usage_context_to_sources.py`
- Updated source_checker prompt to REQUIRE URLs and context (`database/seeds/seed_agent_prompts.py:48-103`)
- URL priority: DOI → WorldCat → Publisher → Google Books → Amazon
- Updated source_checker agent to request usage_context (`agents/source_checker.py:59-93`)
- Updated repository to store usage_context (`database/repositories.py:263-287`)
- Updated API responses to include usage_context:
  - `main.py:144-154`
  - `services/chat_pipeline.py:120-130`

**Frontend:**
- Added usage_context to Source type (`src/frontend/src/types/index.ts:14-21`)
- Display usage_context in ClaimCard component (`src/frontend/src/components/chat/ClaimCard.tsx:179-183`)

### 4. Agent Claims "Provided Quotes" When None Exist ✓

**Problem:** Writing agent output said "as evidenced by the provided quotes" when no quotes were included.

**Fix:**
- Updated writing_agent system prompt with explicit instruction:
  - NEVER reference "provided quotes" without actual quoted text
  - Reference sources by author/work name instead
  - Example: "According to Ehrman..." vs "as shown in provided quotes"
- File: `database/seeds/seed_agent_prompts.py:149-187`

### 5. Claim Card Header Confusing ✓

**Problem:** Claim text looked like statement of fact, not claim being evaluated.
Users confused about which part was the verdict.

**Fix:**
- Added "Claim:" label before claim text in header
- File: `src/frontend/src/components/chat/ClaimCard.tsx:74-76`

---

## Files Modified

### Backend (9 files)
1. `src/backend/config.py` - Raised semantic search threshold 0.85 → 0.92
2. `src/backend/services/context_analyzer.py` - Enhanced prompt for alternative explanations
3. `src/backend/database/models.py` - Added usage_context field to Source
4. `src/backend/database/migrations/versions/f01c3b619027_*.py` - Migration for usage_context
5. `src/backend/database/seeds/seed_agent_prompts.py` - Updated source_checker and writing_agent prompts
6. `src/backend/agents/source_checker.py` - Request usage_context in agent output
7. `src/backend/database/repositories.py` - Store usage_context field
8. `src/backend/main.py` - Include usage_context in API response
9. `src/backend/services/chat_pipeline.py` - Include usage_context in WebSocket response

### Frontend (2 files)
1. `src/frontend/src/types/index.ts` - Added usage_context to Source type
2. `src/frontend/src/components/chat/ClaimCard.tsx` - Display "Claim:" label and usage_context

---

## Testing Required

**Before deploying:**
1. Run migration: `alembic upgrade head` (in backend/)
2. Re-seed agent prompts: `python database/seeds/seed_agent_prompts.py`
3. Restart backend service
4. Test with follow-up questions

**Test cases:**
- Q1: "Did Matthew copy Mark?" → Get claim card (similarity ~0.92)
- Q2: "Couldn't divine inspiration explain this?" → Should get DIFFERENT claim card about divine inspiration (similarity ~0.89 < 0.92)
- Q3: "Is Matthew independent from Mark?" → Should get same card as Q1 (similarity ~0.95)
- Sources should have WorldCat/DOI links
- Sources should show usage context (e.g., "Demonstrates scholarly consensus")
- Claim header should say "Claim: [text]"

---

## Database Migration

**Migration:** `f01c3b619027_add_usage_context_to_sources`
**Type:** ALTER TABLE sources ADD COLUMN usage_context TEXT NULL

Run before testing: `cd src/backend && alembic upgrade head`

---

## Root Cause Analysis

The "everything returns same card" bug was caused by:
1. **Threshold too low:** 0.85 allowed ~89% similarity to match
2. **Only 1 card in DB:** Every related question matched it
3. **Semantic similarity limitation:** Can't distinguish opposing claims about same topic

The fix (threshold 0.92) requires ~92% similarity, which:
- Still matches legitimate rephrases (0.92-0.95)
- Blocks related but different claims (< 0.92)
- Will need tuning as more cards are added

**Future consideration:** If false negatives occur (legitimate matches blocked), may need:
- Claim text comparison layer
- Verdict contradiction detection
- Hybrid search (semantic + keyword)

---

## Notes

- All fixes are non-breaking (usage_context is nullable)
- Existing claim cards won't have usage_context (NULL is fine)
- New claims will have richer source metadata
- Context Analyzer changes are prompt-only (no schema changes)
- Writing agent improvements prevent future "phantom quotes" issue
- **Threshold 0.92 is critical** - do not lower without extensive testing

---

**Session Duration:** ~45 minutes
**Lines Changed:** ~65 backend, ~15 frontend
**Complexity:** Medium (threshold tuning required testing + field addition)
