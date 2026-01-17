# Session: Pipeline Progress Visibility

**Date:** 2026-01-14
**Phase:** Phase 2 (Conversational Chat) - UX Enhancement
**Status:** Complete

---

## Overview

Improve pipeline progress visibility during claim generation. Current progress indicator is too subtle - users can't easily see which agent is running or understand what's happening.

**References:**
- `/home/etl/projects/thereceipts/TESTING_NOTES.md` (lines 101-114)
- `/home/etl/projects/thereceipts/docs/sessions/2026-01-13-phase2-fixes.md`

---

## Problem

**CRITICAL:** Pipeline progress component was never shown because WebSocket events were ignored.

Original AskPage.tsx (lines 78-128):
- WebSocket receives `agent_started` and `agent_completed` events but doesn't process them (line 128 comment)
- `pipeline.isRunning` and `pipeline.agentProgress` never updated during chat flow
- Chat flow creates its own WebSocket, doesn't integrate with usePipeline hook
- Progress component relied on state that was never set

**Additional issues:**
- Generic "Generating response..." text
- Raw agent names: `topic_finder`, `source_checker`, etc.
- No descriptions of what each agent does
- No visual indicator of overall progress (X of 5 agents complete)

**User impact:**
- Progress component never appeared at all
- Can't tell where pipeline is in execution
- Don't know what each agent is doing

---

## Scope

**Frontend files to modify:**
- `src/frontend/src/pages/AskPage.tsx` (pipeline progress component)
- `src/frontend/src/pages/AskPage.css` (visual styling)

**Requirements:**
1. Show user-friendly agent names: TopicFinder, SourceChecker, Adversarial, Writer, Publisher
2. Show what each agent is doing (not just status)
3. Add visual progress bar showing X of 5 agents complete
4. Make progress component more prominent and always visible during execution

---

## Implementation

### 1. Agent Display Names & Descriptions

Map raw agent identifiers to user-friendly names and descriptions:

| Agent ID | Display Name | Description |
|----------|--------------|-------------|
| `topic_finder` | TopicFinder | Identifying core claim and context |
| `source_checker` | SourceChecker | Finding academic sources |
| `adversarial_checker` | Adversarial | Evaluating counterarguments |
| `writing_agent` | Writer | Composing response |
| `publisher` | Publisher | Finalizing claim card |

### 2. Visual Progress Bar

Add progress indicator showing completed/total:
- "Agent 3 of 5: Adversarial - Evaluating counterarguments"
- Visual progress bar with fill percentage
- Clear completion state

### 3. Enhanced Visibility

Make progress component more prominent:
- Larger, bolder text
- Better spacing and hierarchy
- Color-coded status indicators
- Always visible during pipeline execution

---

## Files Modified

### 1. `src/frontend/src/pages/AskPage.tsx`

**ROOT CAUSE FIX: Added local agent progress tracking (lines 49-63):**
- Previous code relied on `pipeline.isRunning` and `pipeline.agentProgress` which were never updated
- Added local state: `isPipelineRunning` and `agentProgress`
- These are now updated directly when WebSocket events are received

**Added agent display configuration (lines 17-47):**
```typescript
const AGENT_DISPLAY_INFO: Record<string, { name: string; description: string }> = {
  topic_finder: { name: 'TopicFinder', description: 'Identifying core claim and context' },
  source_checker: { name: 'SourceChecker', description: 'Finding academic sources' },
  adversarial_checker: { name: 'Adversarial', description: 'Evaluating counterarguments' },
  writing_agent: { name: 'Writer', description: 'Composing response' },
  publisher: { name: 'Publisher', description: 'Finalizing claim card' }
};
```

**CRITICAL FIX: Handle WebSocket events (lines 123-163):**
```typescript
setIsPipelineRunning(true);  // Start progress tracking
setAgentProgress(AGENT_ORDER.map(...));  // Reset to pending

ws.onmessage = (event) => {
  if (data.type === 'agent_started') {
    // Update agent to 'running' status
    setAgentProgress(prev => prev.map(...));
  } else if (data.type === 'agent_completed') {
    // Update agent to 'completed'/'failed' status
    setAgentProgress(prev => prev.map(...));
  } else if (data.type === 'claim_card_ready') {
    setIsPipelineRunning(false);  // Stop progress tracking
  }
};
```
**Previously:** These events were received but completely ignored (line 128 comment)
**Now:** Events update local state in real-time

**Updated pipeline progress component (lines 230-280):**
- Changed from `pipeline.isRunning` → `isPipelineRunning` (local state)
- Changed from `pipeline.agentProgress` → `agentProgress` (local state)
- Calculate completed agents count and progress percentage
- Display current agent number: "Agent 3 of 5: Adversarial"
- Show agent description: "Evaluating counterarguments"
- Visual progress bar with dynamic width
- Use display names instead of raw agent IDs in agent list

**Updated empty state check (line 209):**
- Changed from `!pipeline.isRunning` → `!isPipelineRunning`

**Updated clear conversation handler (lines 188-195):**
- Reset local agent progress state when conversation cleared

### 2. `src/frontend/src/pages/AskPage.css`

**Enhanced `.pipeline-progress` container (lines 75-83):**
- Increased padding: 1rem → 1.5rem
- Added accent border: 2px solid accent color
- Increased max-width: 85% → 90%
- Added box shadow for prominence
- Larger border radius

**Added progress text structure (lines 92-107):**
- `.progress-text`: Flex container for title/subtitle
- `.progress-title`: Larger (1.125rem), bold (700), prominent
- `.progress-subtitle`: Smaller (0.875rem), secondary color, shows agent description

**Enhanced spinner (lines 109-118):**
- Larger size: 1rem → 1.5rem
- Thicker border: 2px → 3px
- Added min-width to prevent flex shrink

**Added progress bar (lines 126-141):**
- `.progress-bar-container`: 8px height, rounded, secondary background
- `.progress-bar-fill`: Gradient fill (accent → blue), smooth transition
- Width controlled by inline style (dynamic)

**Enhanced agent items (lines 149-168):**
- Increased padding: 0.5rem → 0.625rem 0.75rem
- Added transition for smooth state changes
- `.agent-running`: Blue background with border highlight
- Larger agent name font: 0.875rem → 0.9375rem, medium weight

---

## Testing Required

**Before:**
1. Start backend + frontend
2. Ask question to trigger pipeline
3. Observe progress indicator during execution

**After:**
1. Should see clear agent names (TopicFinder, not topic_finder)
2. Should see what each agent is doing
3. Should see progress: "Agent X of 5"
4. Should have visual progress bar
5. Component should be prominent and easy to read

---

## Notes

- No backend changes required (WebSocket events already being sent correctly)
- **Root cause:** Frontend was receiving events but not processing them
- Fixed by adding local state tracking and handling agent_started/agent_completed events
- Progress component now updates in real-time as agents execute
- Agent order is fixed: topic_finder → source_checker → adversarial_checker → writing_agent → publisher

## Debugging Notes

**Initial mistake:** Modified UI without checking if underlying state was being updated
**Discovery:** User reported no changes visible → investigated WebSocket handling → found events ignored
**Fix:** Added local state tracking + event handlers to update state in real-time

---

**Session Duration:** ~45 minutes (initial approach was wrong, had to debug and fix properly)
**Lines Changed:** ~85 TypeScript, ~50 CSS
**Complexity:** Medium (required debugging to find root cause - WebSocket events not being processed)

---

## Visual Changes Summary

**Before:**
```
[spinner] Generating response...

topic_finder         pending
source_checker       pending
adversarial_checker  pending
writing_agent        pending
publisher            pending
```

**After:**
```
[spinner] Agent 3 of 5: Adversarial
          Evaluating counterarguments

[========>------] 40%

TopicFinder     ✓ completed
SourceChecker   ✓ completed
Adversarial     ▸ running
Writer            pending
Publisher         pending
```

**Key improvements:**
1. Current agent prominently displayed: "Agent 3 of 5: Adversarial"
2. Description shows what agent is doing: "Evaluating counterarguments"
3. Visual progress bar shows completion percentage
4. User-friendly agent names (TopicFinder vs topic_finder)
5. Running agent highlighted with blue background/border
6. Larger, bolder text throughout
7. More prominent container with accent border and shadow
