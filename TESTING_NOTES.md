# Testing Notes - Phase 2

**Date Started:** 2026-01-13
**Purpose:** Track UX issues, bugs, and improvements discovered during testing

---

## UI/UX Issues

### 1. Claim card header is confusing
**Issue:** The claim text at the top looks like a statement of fact, not the claim being evaluated.

**Example:**
```
"Matthew's gospel is literarily independent from Mark's gospel"
[True] [High Confidence]
```
Then body says "This claim is false" - contradictory appearance.

**User confusion:** Thought the header WAS the answer, not the claim being tested.

**Proposed fix:** Add label "Claim:" or "Claim Being Evaluated:" before the claim text to clarify it's what's being audited.

### 2. "Show Your Work" subsections always visible
**Issue:** User shouldn't see the 6 subsections (Deep Answer, Why Persists, Evidence, Sources, Apologetics, Audit) AT ALL by default.

**Expected behavior:**
- Default view: Short answer + confidence + "Show Your Work" button ONLY
- Click "Show Your Work": The 6 subsection headers appear (collapsed)
- Click individual subsection: That section expands with content
- "Show Your Work" button changes to "Hide Details"

**Current behavior:** Subsections are visible by default with collapse arrows. User never clicked "Show Your Work" but can already see and expand them.

**Fix needed:** `src/frontend/src/components/chat/ClaimCard.tsx` - subsections should be hidden until Show Your Work clicked

---

## Bugs

### 1. Follow-up question returns same claim card incorrectly
**Issue:** Asked follow-up about divine inspiration as alternative explanation, but got the same "Matthew copied Mark" claim card back.

**User flow:**
1. Q1: "Did Matthew copy Mark?" → Got claim card
2. Q2: "How do we know Matthew was copying? Couldn't they have determined the exact same messaging through divine inspiration?"
3. Got same claim card again (wrong - this is a DIFFERENT claim)

**Expected:** New claim card addressing "Divine inspiration could explain gospel similarities" claim.

**Root cause:** Likely one of:
- Context Analyzer didn't recognize this as a NEW claim (should reformulate to "Could divine inspiration explain Matthew/Mark similarities?")
- Semantic search incorrectly matched it to existing claim (threshold too permissive or embedding too similar)
- System needs to distinguish between: (a) clarifying questions about same claim vs (b) alternative explanations (new claims)

**Impact:** High - Breaks conversational flow. Users asking "but what about X?" expect analysis of X, not repeat of previous answer.

### 2. Semantic search matches different claims on same topic **(FIXED 2026-01-16)**
**Issue:** Question about divine evidence manipulation matched to flood historicity claim because they share topic context.

**User flow:**
1. Q: "Couldn't have God made the evidence disappear?"
2. Got flood claim card: "A global flood covered the entire Earth approximately 4,000-5,000 years ago..."

**Problem:** These are DIFFERENT claims:
- User asking: "Could God hide evidence?" (epistemology/unfalsifiability claim)
- System returned: "Did the flood happen?" (historical claim)
- They share topic (flood) but are fundamentally different claims

**Root cause:**
- Semantic search (pgvector cosine similarity) matches on topic/keyword overlap
- Can't distinguish between claims ABOUT the same topic
- Threshold tuning (0.92) doesn't solve this - it's a fundamental limitation

**Resolution:** Implemented LLM-based Router Agent with tool calling (Phase 3)
- Router Agent now uses system prompt with instructions to distinguish claim types
- Router calls `search_existing_claims` first, then reasons about whether results match user intent
- Can distinguish: historical claims vs epistemology claims vs interpretation claims
- Similarity thresholds: >= 0.92 (EXACT_MATCH), 0.80-0.92 (CONTEXTUAL), < 0.80 (NOVEL_CLAIM)
- Router Agent was missing `await self.load_config()` - now fixed
- See: `/docs/sessions/2026-01-15-routing-bugs-fix.md`

**Impact:** Critical bug now resolved. Router Agent correctly distinguishes claim types on same topic.

### 3. Context lost on follow-up question referencing previous response **(FIXED 2026-01-16)**
**Issue:** Follow-up question referencing content from previous claim card treated as standalone question with no context.

**User flow:**
1. Q: "Is abortion moral?" → Got claim card mentioning "The modern evangelical position that abortion equals murder only emerged in the 1970s as a political movement"
2. Q: "What happened during the 1970's political movement that caused that?"
3. Got claim card: "Unable to identify specific claim - question lacks context"

**Problem:** System completely lost context
- "that" clearly refers to the 1970s political movement mentioned in previous response
- Context Analyzer should reformulate to include the reference
- Router Agent should recognize this as clarification question (Mode 2)
- Should explain the 1970s political movement, not claim it can't identify the question

**Root cause:**
- Context Analyzer only included USER messages in conversation history
- Assistant responses (claim card content) were excluded
- Context Analyzer couldn't reformulate follow-ups because it didn't know what "that" referred to

**Resolution:** Context Analyzer now includes assistant responses in history
- Updated `context_analyzer.py` lines 154-175
- Now includes last 6 messages (3 exchanges) with both user and assistant
- Assistant messages truncated to 500 chars for context efficiency
- Context Analyzer can now see previous claim card content
- Can properly reformulate follow-up questions with pronouns/references
- See: `/docs/sessions/2026-01-15-routing-bugs-fix.md`

**Impact:** Critical bug now resolved. Follow-up questions preserve context from previous responses.

---

## Agent Output Issues

### 1. Claims to provide quotes but doesn't
**Issue:** Text says "as evidenced by the provided quotes and sources" but no actual quotes appear in the response.

**Example:** "The consensus among critical scholars, as evidenced by the provided quotes and sources..."

**Fix needed:** Agent should either include actual quoted text from sources OR not claim quotes are provided.

### 2. Source links are COMPLETELY WRONG
**Issue:** URLs lead to irrelevant books. Example: Question about Matthew/Mark copying → link goes to "International Trade Law" book.

**Root cause:** Prompt says "EVERY source MUST have a URL" + "REQUIRED: WorldCat URL..." which forces agent to hallucinate URLs rather than leave empty.

**Fix needed:**
- Change prompt: "Provide URL ONLY if you can verify it matches the citation. Use empty string if URL unavailable or unverifiable."
- Remove "REQUIRED" language that forces hallucination
- Don't hardcode WorldCat - agent should find appropriate URL source (DOI, publisher, etc.)
- File: `src/backend/database/seeds/seed_agent_prompts.py` lines 75-99

### 3. Sources are useless - no links, context, or purchase info
**Issue:** 10 sources listed but:
- Only 1 has a link (broken)
- No context for how sources were used
- No DOIs, ISBNs, or ways to find/buy them
- Just listing sources to list them - performative, not functional

**Example:** "Stein, Robert H. 'The Synoptic Problem: An Introduction.' Baker Academic, 1987, pp. 45-96."
- Can't click it
- Don't know what it said or how it supports the claim
- Can't buy or find this book

**Fix needed:**
- Sources need URLs (WorldCat, DOI, publisher, Amazon, Google Books)
- Sources need quotes showing what they actually said
- Sources need context: "Used to establish X" or "Quote supporting Y"

---

## Performance Issues

### 1. Pipeline progress not visible enough
**Issue:** "Generating response..." shows sometimes but agent progress isn't visible during 45-60s wait. User can't see what agents are doing.

**Current state:**
- `AskPage.tsx` lines 162-177 shows progress component with agent list
- Only shows "Generating response..." text + agent names with status
- User says: "I only ever see 'Generating response...' sometimes, I want to see what the agents are doing and progress!"

**Fix needed:**
- Make pipeline progress ALWAYS visible and prominent when running
- Show each agent clearly: TopicFinder → SourceChecker → Adversarial → Writer → Publisher
- Show what each agent is currently doing (not just "running")
- Visual progress indicator (e.g., "2 of 5 agents complete")
- File: `src/frontend/src/pages/AskPage.tsx` + CSS improvements

---

## Nice-to-Have Improvements

### 1. Fast contextual responses for follow-ups
**Idea:** Some follow-ups don't need full 5-agent pipeline - use existing claim cards as context.

**Example:**
- User gets 2 claim cards (Matthew/Mark copying, divine inspiration)
- Asks: "So which explanation is more likely?"
- System could: Feed both cards to LLM as context, get fast response (5-10s vs 45-60s)

**Distinction from current bug:** This is different from returning the SAME card. It's generating a NEW contextual response grounded in existing audited cards.

**Three response modes:**
1. Exact match → Return existing card (~2s)
2. Clarifying/comparing existing cards → Fast LLM with context (~5-10s) **[NEW]**
3. Novel claim → Full pipeline (~45-60s)

**Decision needed:** How to detect mode 2 vs mode 3? Context Analyzer enhancement?
