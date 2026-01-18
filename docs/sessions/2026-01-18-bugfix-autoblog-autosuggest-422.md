# Session: Bug Fix & Feature - Auto-Blog and Auto-Suggest

**Date:** 2026-01-18
**Type:** Bug Fix + Feature Implementation
**Status:** Complete

---

## Problem

Admin UI "Trigger Now" buttons for scheduler and auto-suggest were returning 422 errors:
```
API request failed: 422 - {"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]}
```

After investigation, discovered auto-suggest endpoint expected `source_text` but the feature was supposed to do automatic web discovery (per ADR 003).

---

## Root Cause Analysis

### Initial 422 Error

**Scheduler endpoint (`/api/admin/scheduler/run-now`):**
- Defined as `async def admin_run_scheduler_now():` (no parameters)
- Admin UI calls with no body → **Works correctly**

**Auto-suggest endpoint (`/api/admin/autosuggest/trigger`):**
- Defined as `async def admin_trigger_autosuggest(request: AutoSuggestExtractRequest):`
- `AutoSuggestExtractRequest` requires `source_text: str` (not optional)
- Admin UI calls with no body → **422 error**

### Design Mismatch

Per **ADR 003 lines 129-180**, auto-suggest should:
1. Automatically crawl web sources (AiG, WLC, CARM, RSS feeds, etc.)
2. Use LLM to extract claims from crawled content
3. Deduplicate against existing claim cards
4. Add to queue with priority scoring

However, `autosuggest.py` only implemented **manual text extraction** (step 2), requiring user to provide the text. The web crawling part (step 1) was marked as "Future enhancements" in code comments.

**Result:** Admin UI "Trigger Now" button expected automatic discovery that didn't exist.

---

## Solution: Both Options Implemented

Implemented both automatic discovery AND manual text extraction:

### Option 1: Automatic Web Discovery

**New method in `autosuggest.py`:**
```python
async def discover_topics_from_web(self) -> Dict[str, Any]:
    """
    Automatically discover topics from web sources using Tavily search.

    Searches for recent Christian apologetics content:
    - "Christian apologetics recent claims 2026"
    - "answers in genesis recent articles"
    - "William Lane Craig recent apologetics"

    For each search result:
    - Extract text content
    - Pass to extract_topics_from_text()
    - Deduplicate and add to queue
    """
```

**New endpoint in `main.py`:**
```python
@app.post("/api/admin/autosuggest/discover")
async def admin_discover_topics():
    """
    Automatically discover topics from web sources (admin only).

    No request body required - performs automatic discovery.
    """
    result = await autosuggest_service.discover_topics_from_web()
    return result
```

### Option 2: Manual Text Extraction

**Fixed existing endpoint in `main.py`:**
```python
@app.post("/api/admin/autosuggest/trigger")
async def admin_trigger_autosuggest(request: Optional[AutoSuggestExtractRequest] = None):
    # Validate request body and source_text
    if not request or not request.source_text:
        raise HTTPException(
            status_code=400,
            detail="source_text is required. This endpoint extracts topics from provided text."
        )
    # ... rest of extraction logic
```

**Admin UI form added** (`SettingsPage.tsx`):
- Textarea for source text (required)
- Input fields for source URL and source name (optional)
- "Extract Topics" button

---

## Files Modified

### Backend

**`src/backend/services/autosuggest.py`:**
- Added `tavily` import and `TavilyClient` initialization
- Added `discover_topics_from_web()` method for automatic discovery
- Uses 3 search queries to find apologetics content
- Extracts topics from search results
- Returns: extracted, added, skipped_duplicates, failed, sources_searched

**`src/backend/main.py`:**
- Added `/api/admin/autosuggest/discover` endpoint (no body required)
- Modified `/api/admin/autosuggest/trigger` to accept optional request body with validation

### Admin UI

**`src/admin/src/api.ts`:**
- Updated `triggerAutoSuggest()` to accept source text parameters
- Added `discoverTopics()` method for automatic discovery

**`src/admin/src/pages/SettingsPage.tsx`:**
- Changed "Trigger Now" button to "Discover Topics" (calls discover endpoint)
- Added `handleDiscoverTopics()` function for automatic web discovery
- Added `handleExtractTopics()` function for manual text extraction
- Added "Extract Topics from Text" form section with:
  - Source text textarea (required)
  - Source URL input (optional)
  - Source name input (optional)
  - "Extract Topics" button

---

## How It Works Now

### Automatic Discovery Flow

1. Admin clicks "Discover Topics" button
2. Backend searches web using Tavily:
   - Query 1: "Christian apologetics recent claims 2026"
   - Query 2: "answers in genesis recent articles"
   - Query 3: "William Lane Craig recent apologetics"
3. For each search result (max 3 per query = ~9 sources):
   - Extract text content
   - Pass to LLM for topic extraction
   - LLM identifies factual claims with priority scores
4. Deduplicate against existing claim cards (>0.85 similarity)
5. Add novel topics to queue
6. Return summary: extracted, added, skipped, sources searched

### Manual Extraction Flow

1. Admin pastes apologetics content into textarea
2. Optionally provides source URL and name
3. Clicks "Extract Topics"
4. Backend passes text to LLM for topic extraction
5. Deduplicate against existing claim cards
6. Add novel topics to queue
7. Return summary: extracted, added, skipped, failed

---

## API Endpoints

```
GET  /api/admin/autosuggest/settings     # Get config
PUT  /api/admin/autosuggest/settings     # Update config

POST /api/admin/autosuggest/discover     # Automatic web discovery (no body)
POST /api/admin/autosuggest/trigger      # Manual text extraction (body required)
```

**Request body for `/trigger`:**
```json
{
  "source_text": "Apologetics content here...",
  "source_url": "https://example.com/article",    // optional
  "source_name": "Answers in Genesis",            // optional
  "skip_deduplication": false
}
```

**Response for both endpoints:**
```json
{
  "success": true,
  "message": "Discovered 5 topics from 9 sources, added 3 to queue",
  "extracted": 5,
  "added": 3,
  "skipped_duplicates": 2,
  "failed": 0,
  "sources_searched": 9  // only in /discover response
}
```

---

## Testing

### Test Automatic Discovery
```bash
curl -X POST http://localhost:8008/api/admin/autosuggest/discover
```

Expected: Searches web, extracts topics, returns summary

### Test Manual Extraction
```bash
curl -X POST http://localhost:8008/api/admin/autosuggest/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "source_text": "Christianity claims the Bible is historically accurate...",
    "source_name": "Test Source"
  }'
```

Expected: Extracts topics from text, returns summary

### Test Scheduler
```bash
curl -X POST http://localhost:8008/api/admin/scheduler/run-now
```

Expected: Generates blog post from highest priority queued topic

---

## Implementation Notes

### Tavily Integration

- Uses existing `TavilyClient` (already available from Phase 4.1 source verification)
- Searches with `search_depth="basic"` (faster, cheaper)
- Max 3 results per query to control costs
- Gracefully handles search failures (continues with other queries)

### Search Queries

Hardcoded 3 queries targeting major apologetics sources:
- General: "Christian apologetics recent claims 2026"
- Specific: "answers in genesis recent articles"
- Specific: "William Lane Craig recent apologetics"

**Future enhancement:** Make queries configurable in admin settings

### Deduplication

- Discovery uses 0.85 similarity threshold (from config)
- Lower than scheduler dedup (0.92) to catch broader duplicates
- Semantic search against existing claim cards
- Skips topics that are too similar to existing content

### Error Handling

- Tavily API errors: Skip failed queries, continue with others
- LLM extraction errors: Skip failed sources, continue processing
- Embedding errors: Fail-open (treat as not duplicate)
- Returns partial results even if some sources fail

---

## Success Criteria

✅ Scheduler "Run Now" works (generates blog posts)
✅ Auto-suggest "Discover Topics" works (automatic web discovery)
✅ Manual "Extract Topics from Text" form works (paste content)
✅ Both flows deduplicate correctly
✅ Clear error messages for missing TAVILY_API_KEY
✅ UI provides feedback on success/failure

---

## Future Enhancements

Per ADR 003, planned but not yet implemented:

1. **Configurable sources**: Admin can add/remove web sources to monitor
2. **RSS feed monitoring**: Subscribe to apologetics blogs/podcasts
3. **Twitter/X monitoring**: Track prominent apologists' accounts
4. **YouTube transcript analysis**: Extract claims from video content
5. **Scheduled discovery**: Run automatic discovery on cron (e.g., daily)

Current implementation provides foundation for these features.

---

## Consequences

### Benefits
- Admin can now discover topics automatically (one-click)
- Manual extraction available for specific sources
- Matches ADR 003 design intent
- Leverages existing Tavily integration (no new dependencies)
- Both flows share deduplication logic (consistent behavior)

### Trade-offs
- Tavily API costs per search (mitigated: 3 queries × 3 results = ~9 sources)
- Hardcoded search queries (acceptable: can be made configurable later)
- Basic search depth (faster, cheaper, sufficient for MVP)

### Constraints
- Requires TAVILY_API_KEY environment variable
- Discovery limited to web search results (no RSS/Twitter/YouTube yet)
- Manual extraction required for sources not discoverable via web search
