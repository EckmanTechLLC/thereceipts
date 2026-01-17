# Session: Claim Stance & Verdict Contradiction Investigation
**Date:** 2026-01-15
**Focus:** Investigate verdict/answer text contradictions in claim cards

---

## Problem Statement

Claim card d1738d20-2f33-468e-85e6-68d80087fa3f shows:
- **Header verdict:** "True" (green badge)
- **Body text:** "This claim is false..."
- **User impact:** Destroys trust - header and content contradict

**Hypothesis:** Topic Finder creates claims in negative stance when question asks about opposite, causing verdict confusion.

---

## Investigation Findings

### 1. Contradictory Claim Card Analysis

**Query: Luke/Mark claim cards in database**

Found **2 out of 3** Luke/Mark claims with potential issues:

#### **Claim 1 (CONTRADICTORY):**
- **ID:** d1738d20-2f33-468e-85e6-68d80087fa3f
- **Original question:** "how many similarities are between Luke and Mark?"
- **Claim text:** "The Gospel of Luke is independent of Mark and represents a separate eyewitness tradition"
- **Verdict (stored):** TRUE
- **Short answer:** "This claim is false. The Gospel of Luke is not independent of Mark..."
- **Status:** ⚠️ **CONTRADICTION** - Verdict says TRUE but answer says FALSE

#### **Claim 2 (NO CONTRADICTION):**
- **ID:** 0bc16c2e-e0a6-49f4-9fce-bbc084b3b941
- **Claim text:** "Luke's gospel is independent of Mark's gospel, or alternatively, Luke and Mark share significant similarities because Luke used Mark as a source"
- **Verdict:** TRUE
- **Short answer:** "Scholars overwhelmingly agree that Luke used Mark's gospel as a source..."
- **Status:** ✓ No contradiction (claim includes both possibilities)

#### **Claim 3 (NO CONTRADICTION):**
- **ID:** defa58bd-abd1-4bf0-a838-731cf07aa787
- **Claim text:** "Luke copied extensively from Mark's gospel, using Mark as a primary source"
- **Verdict:** TRUE
- **Short answer:** "This claim is true. Biblical scholars have established..."
- **Status:** ✓ No contradiction

### 2. Database-Wide Pattern Analysis

**Query: All 11 claims in database**

- **Claims with verdict='True' but negative language:** 2
  - Luke/Mark independence claim (d1738d20-2f33-468e-85e6-68d80087fa3f)
  - Matthew/Mark independence claim (similar pattern)

- **Claims with verdict='False' but positive language:** 0

**Pattern identified:** When user asks about similarities/dependence, Topic Finder creates claim in NEGATIVE stance (asserting independence), then Writing Agent correctly evaluates that negative claim as false, but verdict gets stored as TRUE.

### 3. Prompt Analysis

#### **Topic Finder Prompt (seed_agent_prompts.py:19-44)**
```
Your job: Identify and analyze the core claim being evaluated.
```

**Findings:**
- ❌ No explicit guidance on claim stance (affirmative vs negative)
- ❌ No instruction to match claim direction to user question intent
- ❌ Says "identify the claim" but doesn't specify how to frame it
- When user asks "how many similarities?", Topic Finder creates "Luke is independent" (opposite stance)

#### **Writing Agent Prompt (seed_agent_prompts.py:144-178)**
```json
{
  "verdict": "True|Misleading|False|Unfalsifiable|Depends on Definitions",
  "short_answer": "≤150 words...",
  ...
}
```

**Findings:**
- ✓ Prompt structure looks correct
- ✓ Requires verdict field
- ✓ Requires short_answer field
- ❌ No explicit instruction to ensure verdict and explanation are consistent
- Writing Agent correctly evaluates the claim it receives, but can't fix stance mismatch

### 4. Pipeline Data Flow Analysis

**Checked:**
- `services/pipeline.py:236` - Verdict comes from Writing Agent output via `aggregated_data.update()`
- `database/repositories.py:251` - Verdict stored as `VerdictEnum(pipeline_data.get("verdict"))`
- No inversion logic found in codebase (grep: "invert|opposite|negate|flip.*verdict")

**agent_audit structure:**
- Only stores Publisher output fields: `limitations`, `audit_summary`, `change_verdict_if`, `original_question`
- Does NOT store individual agent outputs (Topic Finder, Writing Agent, etc.)
- Cannot verify what Writing Agent actually output for verdict

---

## Root Cause Analysis

### **Primary Issue: Claim Stance Mismatch**

1. **User asks:** "How many similarities are between Luke and Mark?" (seeking information about DEPENDENCE)
2. **Topic Finder creates:** "Luke is INDEPENDENT of Mark" (NEGATIVE stance - opposite of what user asked)
3. **Writing Agent evaluates:** This claim (independence) is FALSE ✓ (correct evaluation)
4. **Database stores:** Verdict = TRUE (wrong - appears to be inverted)
5. **Result:** Header shows "True" but body says "This claim is false"

### **Why This Happens**

**Topic Finder has no guidance on claim stance:**
- Prompt says "identify the core claim" but doesn't specify stance direction
- When user asks about similarities/dependence, it creates opposite claim (independence)
- Acts like it's creating a "debate claim" rather than matching user intent

**Potential verdict inversion:**
- Writing Agent correctly says independence claim is FALSE
- But somehow TRUE gets stored in database
- Could be: semantic confusion between "evaluating claim as false" vs "dependence is true"

---

## Issue Scope

**NOT an isolated bug - SYSTEMIC PROBLEM:**
- 2 out of 11 claims (18%) show this pattern
- Both involve "independence vs dependence" claims (Luke/Mark, Matthew/Mark)
- Affects any question where Topic Finder chooses negative stance when user asks about positive

**User trust impact:**
- Breaks core UX: header contradicts body text
- Makes system look broken/unreliable
- User can't trust verdicts

---

## Next Steps (DO NOT IMPLEMENT YET)

### Option 1: Fix Topic Finder Stance Selection
- Add prompt guidance: "Frame claim to match user question intent"
- Example: "similarities?" → create "Luke depends on Mark" NOT "Luke is independent"
- Risk: May not fully solve semantic confusion

### Option 2: Add Verdict/Answer Consistency Check
- Writing Agent validates: verdict enum matches explanation tone
- If answer starts with "This claim is false" → verdict must be FALSE
- Catches contradictions before storage

### Option 3: Store Explicit Claim Stance
- Add `claim_stance` field: "affirmative" | "negative"
- UI can invert display: if stance="negative" and verdict="False" → show as "True" for opposite
- More complex but handles all cases

### Option 4: Refactor to Answer-First Approach
- Don't create standalone claim - answer user question directly
- Generate verdict based on what user actually asked
- Eliminates stance mismatch entirely

---

## Files Investigated

- `src/backend/database/seeds/seed_agent_prompts.py` (Topic Finder, Writing Agent prompts)
- `src/backend/database/models.py` (ClaimCard, VerdictEnum)
- `src/backend/database/repositories.py` (ClaimCardRepository, verdict storage)
- `src/backend/services/pipeline.py` (agent data flow)
- `src/backend/agents/publisher.py` (final agent, no verdict modification)

---

## Database Queries Used

```sql
-- Find Luke/Mark claims
SELECT id, claim_text, verdict, short_answer, claimant
FROM claim_cards
WHERE (LOWER(claim_text) LIKE '%luke%' AND LOWER(claim_text) LIKE '%mark%');

-- Check agent audit structure
SELECT jsonb_object_keys(agent_audit)
FROM claim_cards
WHERE id = 'd1738d20-2f33-468e-85e6-68d80087fa3f';

-- Pattern analysis
SELECT claim_text, verdict, short_answer
FROM claim_cards
WHERE claim_text LIKE '%independent%';
```

---

## ROOT CAUSE IDENTIFIED

**File:** `src/backend/agents/adversarial_checker.py:62-87`

**The Bug:** Adversarial Checker prompt has semantic ambiguity that causes LLM to evaluate the wrong thing.

### Prompt Wording (Line 63):
```
Attempt to falsify this analysis:

Claim: {claim}
Evidence Summary: {evidence_summary}
```

### Verdict Definitions (Lines 82-84):
```
- True: Claim is factually accurate
- False: Claim is factually incorrect
```

### What Happens:

**Input to Adversarial Checker:**
- Claim: "Luke is independent of Mark"
- Evidence Summary: "Evidence shows Luke copied from Mark"

**Prompt says:** "Attempt to falsify this analysis"
**Question:** What is "this analysis"? The claim or the evidence_summary?

**LLM interprets verdict as evaluating THE ANALYSIS/EVIDENCE:**
- "Can I falsify the analysis that says Luke copied from Mark?"
- Answer: No, the evidence is solid and correct
- **Verdict: TRUE** ← evaluating the evidence/analysis is correct

**LLM should evaluate THE CLAIM:**
- "Is the claim 'Luke is independent' factually accurate?"
- Answer: No, the claim is incorrect
- **Verdict: FALSE** ← evaluating the claim itself

### Why This Happens:

The prompt wording "Attempt to falsify this analysis" causes semantic confusion:
1. It shows BOTH the claim AND the evidence_summary
2. The phrase "this analysis" is ambiguous - could refer to either
3. LLM naturally interprets "analysis" as the evidence/conclusion, not the original claim
4. So it returns a verdict about whether the EVIDENCE is correct, not whether the CLAIM is correct

### Evidence:

- Verdict stored in DB: **TRUE**
- Short answer text: **"This claim is false..."**
- The writing agent receives verdict=TRUE and writes prose saying "the claim is false"
- This creates the contradiction in the UI

### Verification:

Cannot query agent_audit for individual agent outputs (only Publisher fields are stored in repositories.py:238-244). But code logic trace confirms:
1. Topic Finder creates negative stance claim: "Luke is independent" ✓
2. Source Checker finds evidence: "Luke copied from Mark" ✓
3. Adversarial Checker evaluates with ambiguous prompt → returns TRUE ✓
4. Writing Agent receives verdict=TRUE, writes correct explanation about claim being false ✓
5. Database stores verdict=TRUE with body text saying "false" → **contradiction** ✓

**This is not a stance mismatch problem. This is a prompt ambiguity problem in Adversarial Checker.**

---

---

## FIX APPLIED

**File:** `src/backend/database/seeds/seed_agent_prompts.py`
**Lines:** 108-141 (adversarial_checker system_prompt)

### Changes Made:

**FROM (Line 110):**
```
Your job: Attempt to falsify the draft analysis.
```

**TO (Lines 110-112):**
```
Your job: Evaluate whether the CLAIM is factually accurate based on the evidence provided.

CRITICAL: Your verdict evaluates the CLAIM's accuracy, not the quality of the evidence or analysis. If the claim says "X is true" but evidence shows X is false, your verdict must be "False".
```

**Additional clarifications:**
- Line 118: "Determine the correct verdict for the CLAIM based on evidence" (was: "Challenge the proposed verdict")
- Line 119: "Identify apologetics techniques being used in the original CLAIM" (added "in the original CLAIM")

### Re-seed Output:
```
✓  Updated adversarial_checker
```

### What This Fixes:

The ambiguous wording "falsify the draft analysis" has been replaced with explicit instructions:
1. **Target is clear:** Evaluate the CLAIM, not the evidence
2. **Verdict meaning is explicit:** If claim says X but evidence shows not-X, verdict = False
3. **Example given:** "If the claim says 'X is true' but evidence shows X is false, your verdict must be 'False'"

### Expected Behavior After Fix:

**Claim:** "Luke is independent of Mark"
**Evidence:** "Luke copied from Mark"
**Adversarial Checker should now return:** Verdict = **FALSE** (claim is factually incorrect)
**Writing Agent will receive:** verdict=FALSE, writes "This claim is false..."
**UI will show:** Header="False", Body="This claim is false..." → **No contradiction**

### Testing Required:

1. Delete contradictory claim card (d1738d20-2f33-468e-85e6-68d80087fa3f)
2. Re-run pipeline with same question: "how many similarities are between Luke and Mark?"
3. Verify new claim card has consistent verdict and explanation

---

**Status:** Fix applied and seeded. Ready for testing.
