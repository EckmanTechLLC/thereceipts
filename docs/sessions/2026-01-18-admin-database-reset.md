# Session: Admin Database Reset Feature

**Date:** 2026-01-18
**Status:** Complete
**Phase:** 4.4

## Objective

Implement database reset feature for admin UI to clear generated content while preserving system configuration (per ADR 004).

## Implementation

### Backend (src/backend/main.py)

**Request Model:**
- `DatabaseResetRequest` (line 385-387): Requires `confirm: bool` field

**Endpoint: POST /api/admin/database/reset** (line 1564-1655)
- Transaction-based deletion (all or nothing)
- Deletes in correct order to avoid FK constraint violations:
  1. router_decisions (no dependencies)
  2. blog_posts (FK to topic_queue with SET NULL)
  3. claim_cards (cascades to sources, apologetics_tags, category_tags)
  4. topic_queue (safe after blog_posts nullified)
- Counts records before deletion
- Returns summary: deleted counts + preserved items
- Rollback on any error

**What Gets Deleted:**
- All claim cards (cascades to sources, apologetics_tags, category_tags)
- All blog posts
- All topics in queue
- All router decisions

**What Gets Preserved:**
- Agent prompts (system configuration)
- Verified sources library (verified_sources table)

### Admin API Client (src/admin/src/api.ts)

**Method: `resetDatabase(confirm: boolean)`** (line 192-197)
- POST to /api/admin/database/reset
- Sends `{ confirm }` in request body
- Returns deletion summary

### Admin UI (src/admin/src/pages/SettingsPage.tsx)

**State Management:**
- `showResetConfirmation`: Controls modal visibility
- `resetConfirmationText`: User input for "RESET" confirmation
- `isResetting`: Loading state during API call

**Handlers:**
- `handleResetDatabase()`: Validates "RESET" input, calls API, shows success message
- `handleCancelReset()`: Closes modal and resets form

**UI Components:**

1. **Danger Zone Section** (line 417-463)
   - Red bordered section at bottom of settings page
   - Warning box explaining what gets deleted/preserved
   - "This action cannot be undone" warning
   - Red "Clear Database" button

2. **Confirmation Modal** (line 465-528)
   - Overlay with centered modal
   - Clear warning text
   - Text input requiring "RESET" to enable confirmation
   - Cancel and Reset Database buttons
   - Disabled state until "RESET" typed correctly

### Styling (src/admin/src/pages/SettingsPage.css)

**Danger Zone Styles** (line 144-190)
- Red border (2px #d73a49)
- Light red background (#fff5f5)
- Red section header and title
- White warning box with red border
- Clear visual hierarchy

**Modal Styles** (line 192-223)
- Fixed overlay with semi-transparent background
- Centered white modal with shadow
- Red heading matching danger zone theme
- Responsive width (90% max 500px)

## Files Modified

1. `src/backend/main.py` (+94 lines)
   - DatabaseResetRequest model
   - POST /api/admin/database/reset endpoint

2. `src/admin/src/api.ts` (+6 lines)
   - resetDatabase() method

3. `src/admin/src/pages/SettingsPage.tsx` (+151 lines)
   - State for reset confirmation
   - Reset handlers
   - Danger Zone section JSX
   - Confirmation modal JSX

4. `src/admin/src/pages/SettingsPage.css` (+80 lines)
   - Danger zone styling
   - Modal styling

## Testing Notes

**Manual Testing Required:**
1. Navigate to Admin UI Settings page
2. Scroll to Danger Zone section at bottom
3. Click "Clear Database" button
4. Verify modal appears with correct warning text
5. Try submitting without typing "RESET" (should show error)
6. Type "RESET" exactly (case-sensitive)
7. Click "Reset Database" button
8. Verify success message shows deleted counts
9. Verify database content deleted but agent prompts + verified sources preserved
10. Check transaction atomicity: If any deletion fails, all should rollback

**Edge Cases:**
- Non-confirmed request (confirm: false) → 400 error
- Empty database → Returns zero counts, succeeds
- Database error during deletion → Rollback, 500 error
- Modal cancel → Closes modal, resets form
- Typing "reset" (lowercase) → Stays disabled (case-sensitive)

## Success Criteria

✅ Backend endpoint deletes correct tables in transaction
✅ Agent prompts and verified_sources preserved
✅ Admin UI shows danger zone with clear warnings
✅ Two-step confirmation (button + "RESET" text input)
✅ Success feedback shows deletion summary
✅ Error handling with rollback
✅ Styling matches danger zone theme (red borders, warnings)

## Notes

- Deletion order critical to avoid FK constraint violations
- blog_posts FK to topic_queue uses SET NULL (must delete before topics)
- claim_cards cascade deletes sources, apologetics_tags, category_tags
- Transaction ensures atomicity (all or nothing)
- Case-sensitive "RESET" confirmation prevents accidental execution
- Verified sources library preserved per ADR 004 (hard-won metadata)

## Bug Fix (During Testing)

**Issue:** FK constraint violation when deleting claim_cards
- Error: `sources_claim_card_id_fkey` constraint violation
- Root cause: SQLAlchemy `cascade="all, delete-orphan"` only works with ORM operations, not bulk SQL `__table__.delete()`
- Bulk deletes bypass ORM and hit database FK constraints directly

**Fix:** Delete child tables explicitly before parent
- Added Source, ApologeticsTag, CategoryTag to deletion sequence
- New order:
  1. router_decisions
  2. blog_posts
  3. **sources, apologetics_tags, category_tags** (claim_cards children)
  4. claim_cards (now safe)
  5. topic_queue

**Lesson:** Always check actual FK constraints in migrations, not just SQLAlchemy relationship definitions.

## Next Steps

User will test the feature manually by:
1. Starting backend and admin services
2. Using the Clear Database feature
3. Verifying correct deletion/preservation behavior

---

**Session Complete** - Database reset feature ready for testing (bug fixed).
