# Session: Sources Page Implementation
**Date:** 2026-01-18
**Focus:** Add Sources page displaying all sources sorted by reference count

---

## Objective
Implement a new Sources page that displays all sources used across claim cards, sorted by reference count (most referenced first), with filtering capabilities and verification status display.

---

## Changes Made

### Backend (Python/FastAPI)

#### 1. New API Endpoint: `/api/public/sources`
**File:** `src/backend/main.py` (lines 1811-1891)

- Added `GET /api/public/sources` endpoint
- Query features:
  - Groups sources by ID and counts references
  - Orders by reference count (descending), then created_at (descending)
  - Supports pagination (skip/limit parameters)
  - Filters: verification_status, source_type
- Returns source data with verification metadata:
  - citation, source_type, url
  - verification_method, verification_status, content_type, url_verified
  - usage_count (number of claim cards referencing each source)

**SQL Query Logic:**
```python
select(Source, func.count().label("usage_count"))
.group_by(Source.id)
.order_by(func.count().desc(), Source.created_at.desc())
```

---

### Frontend (React/TypeScript)

#### 2. Type Definitions
**File:** `src/frontend/src/types/index.ts`

Added new interfaces:
- `SourceWithCount` - Source entity with usage_count field
- `SourcesResponse` - API response structure with sources array and pagination

#### 3. API Client Method
**File:** `src/frontend/src/services/api.ts`

Added `getSources()` method:
- Accepts skip, limit, verification_status, source_type parameters
- Returns typed `SourcesResponse`

#### 4. Sources Page Component
**File:** `src/frontend/src/pages/SourcesPage.tsx` (new)

Features:
- Table layout displaying sources sorted by reference count
- Filter dropdowns:
  - Source Type (primary_historical, scholarly_peer_reviewed)
  - Verification Status (verified, partially_verified, unverified)
- Table columns:
  - Citation (full text)
  - Type (formatted source type)
  - Verification (badge with color coding)
  - References (usage count, highlighted)
  - Link (view button if URL available)
- Pagination controls (Previous/Next)
- Loading and error states

#### 5. Styles
**File:** `src/frontend/src/pages/SourcesPage.css` (new)

Styling features:
- Consistent with existing page designs (Audits, Read)
- Table layout with hover effects
- Verification badges with color coding:
  - Verified: green
  - Partially verified: yellow
  - Unverified: gray
- Responsive design (mobile scrollable table)
- Filter section matching existing filter UI patterns

#### 6. Routing
**File:** `src/frontend/src/App.tsx`

- Added `/sources` route pointing to SourcesPage component
- Imported SourcesPage component

#### 7. Navigation
**File:** `src/frontend/src/components/TopNav.tsx`

- Added "Sources" link after "Audits" in top navigation
- Active state styling matches other nav links

---

## Implementation Notes

### Design Decisions

1. **Table vs Card Layout**: Chose table layout over card grid
   - Sources are best viewed in compact, scannable format
   - Reference count is a key metric (highlighted column)
   - Citations are text-heavy (better in table rows)

2. **Sorting**: Fixed sort by reference count descending
   - Most referenced sources are most relevant
   - Secondary sort by created_at for consistency

3. **Verification Display**: Badge format (not prominent)
   - Follows ADR 004 principle: "Transparent about verification status in UI (not prominent but visible)"
   - Color-coded for quick scanning
   - Doesn't dominate the UI

4. **Pagination**: Simple Previous/Next controls
   - Consistent with Audits page pattern
   - Shows current range (e.g., "Showing 1-50")
   - No jump-to-page (keeps UI simple)

### Database Performance

Query uses:
- GROUP BY on indexed column (sources.id)
- COUNT aggregation for usage statistics
- Indexes on verification_method, verification_status (already exist)

Performance should be good for current dataset size. If sources table grows large (>100k rows), consider:
- Materialized view for usage counts
- Caching for filtered queries

---

## Testing Checklist

**Backend:**
- [ ] Endpoint returns 200 OK with valid pagination params
- [ ] Filtering by verification_status works
- [ ] Filtering by source_type works
- [ ] Sources ordered by usage_count descending
- [ ] Pagination controls work (skip/limit)
- [ ] Returns correct usage_count for each source

**Frontend:**
- [ ] Page loads without errors
- [ ] Table displays sources correctly
- [ ] Filter dropdowns apply filters on change
- [ ] Clear Filters button resets all filters
- [ ] Pagination buttons work (Previous/Next)
- [ ] Verification badges display with correct colors
- [ ] View links open in new tab
- [ ] Responsive layout works on mobile
- [ ] Loading state shows while fetching
- [ ] Error state displays on API failure

**Integration:**
- [ ] Navigation link highlights when on Sources page
- [ ] Route /sources loads SourcesPage component
- [ ] API endpoint returns data matching frontend expectations
- [ ] Sources with no URL show "—" instead of link

---

## Files Changed

**Backend:**
- `src/backend/main.py` - Added /api/public/sources endpoint

**Frontend:**
- `src/frontend/src/types/index.ts` - Added SourceWithCount, SourcesResponse types
- `src/frontend/src/services/api.ts` - Added getSources() method
- `src/frontend/src/pages/SourcesPage.tsx` - New component (table layout)
- `src/frontend/src/pages/SourcesPage.css` - New styles
- `src/frontend/src/App.tsx` - Added /sources route
- `src/frontend/src/components/TopNav.tsx` - Added Sources link

**Documentation:**
- `docs/sessions/2026-01-18-sources-page.md` - This session note

---

## Next Steps

1. User tests Sources page functionality
2. Verify query performance with production data
3. Potential future enhancements:
   - Click source row to see all claim cards using that source
   - Export sources list (CSV/JSON)
   - Search/filter by citation text
   - Sort by other columns (type, verification status)

---

## Session Complete

Sources page successfully implemented with:
- Backend endpoint with filtering and pagination
- Frontend table UI with verification badges
- Navigation integration
- Consistent styling with existing pages
