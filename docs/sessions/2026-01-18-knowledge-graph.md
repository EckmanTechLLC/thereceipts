# Session: Knowledge Graph Visualization

**Date:** 2026-01-18
**Status:** Complete
**Phase:** Post-Phase 4 Enhancement

---

## Objective

Implement interactive knowledge graph visualization showing relationships between blog posts, claims, and sources using ReactFlow v11.

---

## Reference

Used reference implementation from `/home/etl/projects/aimee/ui/src/components/graph/KnowledgeGraph.tsx` as template for ReactFlow integration.

---

## Implementation

### Backend Changes

**File:** `src/backend/main.py`

Added new public endpoint:
- `GET /api/public/graph` - Returns nodes and edges for knowledge graph
- Queries published blog posts with claim relationships
- Builds graph structure: Blogs → Claims → Sources
- Returns JSON with nodes (type, label, metadata) and edges (source, target, type)

**Data Structure:**
```json
{
  "nodes": [
    {
      "id": "blog-{uuid}",
      "label": "Blog title...",
      "type": "blog",
      "metadata": { "title": "...", "published_at": "..." }
    },
    {
      "id": "claim-{uuid}",
      "label": "Claim text...",
      "type": "claim",
      "metadata": { "claim_text": "...", "verdict": "..." }
    },
    {
      "id": "source-{uuid}",
      "label": "Citation...",
      "type": "source",
      "metadata": { "citation": "...", "source_type": "...", "url": "..." }
    }
  ],
  "edges": [
    {
      "id": "blog-{uuid}-claim-{uuid}",
      "source": "blog-{uuid}",
      "target": "claim-{uuid}",
      "type": "HAS_CLAIM"
    },
    {
      "id": "claim-{uuid}-source-{uuid}",
      "source": "claim-{uuid}",
      "target": "source-{uuid}",
      "type": "USES_SOURCE"
    }
  ]
}
```

### Frontend Changes

**Dependencies:**
- Added `reactflow: ^11.11.0` to `package.json`

**Types:** `src/frontend/src/types/index.ts`
- Added `GraphNodeType`, `GraphEdgeType`
- Added `GraphNode`, `GraphEdge`, `GraphResponse` interfaces

**API Client:** `src/frontend/src/services/api.ts`
- Added `getGraph()` method calling `/api/public/graph`

**New Component:** `src/frontend/src/pages/GraphPage.tsx`
- Fetches graph data from backend API
- Converts to ReactFlow format
- Hierarchical layout: Blogs (top) → Claims (middle) → Sources (bottom)
- Node colors: Purple (blog), Blue (claim), Green (source)
- Click handlers: Navigate to blog/claim detail pages
- Includes Controls (zoom/pan), MiniMap, Background
- Loading/error/empty states

**Styling:** `src/frontend/src/pages/GraphPage.css`
- Full-height layout
- Header with legend
- Graph container for ReactFlow
- Node hover effects

**Routing:** `src/frontend/src/App.tsx`
- Added `/graph` route to GraphPage component

**Navigation:** `src/frontend/src/components/TopNav.tsx`
- Added "Graph" link after "Sources"

---

## Features

1. **Interactive Visualization**
   - Pan and zoom with ReactFlow controls
   - MiniMap for navigation
   - Smooth edges between nodes

2. **Node Types**
   - Blog posts (purple)
   - Claims (blue)
   - Sources (green)

3. **Click Navigation**
   - Click blog nodes → navigate to `/read/{id}`
   - Click claim nodes → navigate to `/audits/{id}`
   - Sources not clickable (no detail page yet)

4. **Layout**
   - Hierarchical arrangement by type
   - Horizontal spacing between nodes
   - Vertical spacing between layers

5. **Legend**
   - Visual guide showing node type colors

---

## Implementation Notes

**Simplicity First:**
- Basic hierarchical layout (blogs top, claims middle, sources bottom)
- Fixed horizontal spacing (250px) and vertical spacing (200px)
- No complex force-directed layout algorithms initially
- ReactFlow handles interactive positioning after initial layout

**Data Handling:**
- Backend limits to 100 published blogs
- Sources deduplicated by ID (same source can link to multiple claims)
- Empty state when no published content exists

**Performance:**
- ReactFlow v11 handles rendering efficiently
- Graph updates on page load only (no real-time updates)
- Suitable for moderate-sized graphs (hundreds of nodes)

---

## Files Modified

**Backend:**
- `src/backend/main.py` (added `/api/public/graph` endpoint)

**Frontend:**
- `src/frontend/package.json` (added reactflow dependency)
- `src/frontend/src/types/index.ts` (added graph types)
- `src/frontend/src/services/api.ts` (added getGraph method)
- `src/frontend/src/pages/GraphPage.tsx` (new)
- `src/frontend/src/pages/GraphPage.css` (new)
- `src/frontend/src/App.tsx` (added route)
- `src/frontend/src/components/TopNav.tsx` (added nav link)

---

## Testing Steps

1. User should run `npm install` in frontend to install ReactFlow
2. Start backend and frontend services
3. Navigate to `/graph` via TopNav link
4. Verify graph displays with published blogs, claims, sources
5. Test clicking blog nodes (should navigate to read page)
6. Test clicking claim nodes (should navigate to audits page)
7. Test zoom, pan, minimap controls

---

## Future Enhancements (Not Implemented)

1. **Advanced Layout Algorithms**
   - Force-directed layout for organic positioning
   - Dagre/Elk for automatic hierarchical layout

2. **Filtering**
   - Filter by verdict, category, source type
   - Search/highlight specific nodes

3. **Details Panel**
   - Show node details in sidebar on hover/click
   - Preview claim text, source citations

4. **Edge Information**
   - Show relationship metadata
   - Edge thickness based on importance

5. **Performance**
   - Virtual scrolling for large graphs
   - Progressive loading
   - Clustering for dense areas

6. **Export**
   - Export graph as PNG/SVG
   - Export data as JSON/CSV

---

## Bugfixes

### Issue 1: Graph showing empty even with 3 published blogs

**Root Cause:** `BlogPost.claim_card_ids` is `ARRAY(UUID)` without `as_uuid=True`, so SQLAlchemy returns UUID strings. The code was passing these strings directly to `claim_repo.get_by_id()` which expects UUID objects.

**Fix:** Added UUID type conversion in `get_knowledge_graph()` endpoint:
- Check if claim_id is string or UUID object
- Convert strings to UUID objects before calling `get_by_id()`
- Store in claims_dict with string key for consistent lookups

**File:** `src/backend/main.py` lines 1967-1976

### Issue 2: Frontend not displaying nodes/edges from API

**Root Cause:** `useNodesState` and `useEdgesState` only use initial values on mount. When API data loaded asynchronously, the hooks didn't update.

**Fix:** Changed GraphPage to initialize with empty arrays and use `useEffect` to call `setNodes()` and `setEdges()` when `graphData` changes.

**File:** `src/frontend/src/pages/GraphPage.tsx` lines 167-178

### Issue 3: Poor layout - all nodes in single horizontal rows

**Root Cause:** Initial layout placed all nodes of each type in single horizontal rows, creating very wide, unusable graph.

**Fix:** Implemented grid layout:
- 6 nodes per row maximum
- 280px horizontal spacing, 150px vertical spacing
- 250px gap between node type layers
- Much more compact and viewable

**File:** `src/frontend/src/pages/GraphPage.tsx` lines 28-110

---

## Status

✅ Complete - Basic knowledge graph visualization implemented and integrated.

User can now visualize the relationships between published blog posts, analyzed claims, and their supporting sources in an interactive graph interface.
