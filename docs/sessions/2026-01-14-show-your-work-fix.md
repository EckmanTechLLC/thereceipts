# Session: Show Your Work UI Fix

**Date:** 2026-01-14
**Phase:** Phase 2 (Conversational Chat) - Bug Fix
**Status:** Complete

---

## Overview

Fixed "Show Your Work" button behavior in ClaimCard component. Subsections are now hidden by default and only appear after clicking the button, matching the expected UX flow.

---

## Issue

**Problem:** Subsections (Deep Answer, Why Persists, Evidence, Sources, Apologetics, Audit) were visible by default with collapse arrows. Users could see and expand them immediately without clicking "Show Your Work" button.

**Reference:** `TESTING_NOTES.md:24-36`

**Expected behavior:**
1. Default view: Short answer + confidence + "Show Your Work" button ONLY
2. Click "Show Your Work": The 6 subsection headers appear (collapsed)
3. Click individual subsection: That section expands with content
4. "Show Your Work" button changes to "Hide Details"

**Current behavior:** Subsections always visible, just with content collapsed. Button expanded/collapsed all sections instead of showing/hiding them.

---

## Root Cause

ClaimCard component rendered all subsections unconditionally (lines 95-244). The `showAll` state only controlled whether sections were expanded, not whether they were visible at all.

---

## Fix

**File:** `src/frontend/src/components/chat/ClaimCard.tsx`

### Changes:

1. **Wrapped subsections in conditional render** (line 90-96, 248-249):
   ```tsx
   {/* Subsections (only visible after Show Your Work clicked) */}
   {showAll && (
     <>
       {/* All 6 subsections here */}
     </>
   )}
   ```

2. **Updated button handler** (lines 31-40):
   - Removed auto-expansion of all sections
   - `showAll = true`: Subsections appear collapsed
   - `showAll = false`: Subsections hidden entirely

   **Before:**
   ```tsx
   setExpandedSections(new Set([
     'deep_answer',
     'why_persists',
     // ... all sections
   ]));
   setShowAll(true);
   ```

   **After:**
   ```tsx
   // Show subsections (they appear collapsed)
   setShowAll(true);
   ```

---

## Behavior After Fix

**Default state:**
- Claim header with verdict + confidence
- Short answer
- "Show Your Work" button
- **No subsection headers visible**

**Click "Show Your Work":**
- Subsection headers appear (all collapsed)
- Button text changes to "Hide Details"
- User clicks individual sections to expand

**Click "Hide Details":**
- All subsections hidden
- Any expanded sections cleared
- Button text changes back to "Show Your Work"

---

## Files Modified

**Frontend (1 file):**
- `src/frontend/src/components/chat/ClaimCard.tsx` - Conditional render + simplified handler

**Lines changed:** ~15

---

## Testing

**Manual test:**
1. Load chat, ask question
2. Claim card appears with short answer only
3. Click "Show Your Work" → 6 subsection headers appear (collapsed)
4. Click "Deep Answer" → expands with content
5. Click "Hide Details" → all subsections disappear

**No regressions:** Existing expand/collapse functionality preserved.

---

## Notes

- Pure UI fix, no backend/API changes
- No database migrations required
- Fix isolated to single component
- Improves UX by reducing cognitive load on initial view

---

**Session Duration:** ~10 minutes
**Complexity:** Low (UI state management)
