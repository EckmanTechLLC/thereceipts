# ADR 003: Auto-Blog System

**Status:** Accepted
**Date:** 2026-01-16
**Deciders:** User + Claude
**Supersedes:** Extends ADR 001 (Auto-Blog section)

---

## Context

Phase 1 (Foundation) and Phase 2 (Conversational Chat) are complete. The system can generate claim cards on-demand through chat, with intelligent routing that leverages existing audited claims.

**Gap:** The claim library grows reactively (user-driven). To build a comprehensive knowledge base proactively, we need auto-blog: scheduled generation of claim analyses for publication as curated content.

**Core principle:** All content must pass through the 5-agent pipeline. No shortcuts.

---

## Problem Statement

Users benefit from a pre-built library of audited claim cards, but waiting for every question to be asked first is inefficient. We need:

1. **Proactive generation** - Build claim library ahead of user questions
2. **Quality control** - Admin review before publishing
3. **Discovery** - Automated topic suggestion from apologetics ecosystem
4. **Transparency** - Blog feed showcases audited claims
5. **Scheduling** - Consistent content generation without manual intervention

---

## Three Distinct Pages

**Critical distinction:**

1. **Ask** (Phase 2, complete) - Chat interface with claim cards
2. **Read** - Blog articles (one topic → decomposer → multiple claim cards → article wrapper)
3. **Audits** - Claim card repository (browse ALL individual claim cards)

**Read ≠ Audits:**
- Read page shows **blog articles** (topics with multiple claim cards wrapped in article metadata)
- Audits page shows **individual claim cards** (atomic unit, directly browsable)

## Requirements

Phase 3 must deliver 5 sub-features:

1. **Topic Queue System** - Database of topics awaiting analysis
2. **Scheduled Generation** - Automated blog article creation at configurable rate
3. **Auto-Suggest** - LLM + web search discovers new apologetics topics
4. **Review Interface** - Admin approval workflow for generated articles
5. **Read & Audits Pages** - Blog articles (Read) + claim card repository (Audits)

---

## Database Schema

### New Table: blog_posts

**Blog articles synthesize claim card findings into prose:**

```sql
CREATE TABLE blog_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_queue_id UUID REFERENCES topic_queue(id),

    -- Article content
    title VARCHAR(500) NOT NULL,
    article_body TEXT NOT NULL,  -- Full synthesized prose article

    -- Component claim cards (array of UUIDs, referenced within article)
    claim_card_ids UUID[] NOT NULL,

    -- Publication status
    published_at TIMESTAMP NULL,
    reviewed_by VARCHAR(200) NULL,
    review_notes TEXT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX ix_blog_posts_published_at ON blog_posts(published_at);
CREATE INDEX ix_blog_posts_topic_queue_id ON blog_posts(topic_queue_id);
```

**Example:**
- Topic: "Noah's Flood"
- Decomposer identifies 5 component claims (global flood, ark capacity, geological evidence, ancient myths, fossil distribution)
- 5 claim cards generated via 5-agent pipeline
- Blog Composer writes FULL ARTICLE synthesizing findings into narrative prose
- Article references claim cards contextually (footnotes/links), doesn't display them as list
- Read page shows the synthesized article
- Audits page shows all 5 claim cards individually

### Modifications to Existing Tables

**claim_cards table** - Add Audits page visibility:
```sql
ALTER TABLE claim_cards ADD COLUMN visible_in_audits BOOLEAN DEFAULT TRUE;
```

**Rationale:**
- All claim cards visible in Audits page by default
- Admin can hide low-quality cards from Audits (but still usable in chat)
- Blog articles (Read page) visibility controlled via blog_posts.published_at

**topic_queue table** - Add review-specific fields:
```sql
ALTER TABLE topic_queue ADD COLUMN review_status VARCHAR(50) DEFAULT 'pending_review';
ALTER TABLE topic_queue ADD COLUMN reviewed_at TIMESTAMP NULL;
ALTER TABLE topic_queue ADD COLUMN admin_feedback TEXT NULL;
ALTER TABLE topic_queue ADD COLUMN blog_post_id UUID NULL;
```

**review_status values:**
- `pending_review` - Generated, awaiting admin review
- `approved` - Admin approved, blog post published
- `rejected` - Admin rejected, not published
- `needs_revision` - Admin requested changes, requires re-run

---

## Auto-Suggest: Topic Discovery

### How It Works

**Auto-suggest agent** discovers new apologetics claims from web sources:

1. **Source targets** (configurable in admin):
   - Apologetics websites (AiG, WLC, Reasonable Faith, CARM, etc.)
   - RSS feeds from Christian blogs/podcasts
   - Twitter/X accounts of prominent apologists
   - YouTube channels (via transcripts)
   - Recent apologetics books (via Google Books API)

2. **LLM extraction:**
   - Crawl configured sources
   - Feed content to LLM (lightweight model: Claude Haiku or GPT-4o-mini)
   - Prompt: "Identify factual claims about Christianity that can be fact-checked"
   - Extract: claim text, claimant, source URL

3. **Deduplication:**
   - Semantic search against existing claim_cards (>0.85 similarity)
   - Skip if similar claim already exists
   - Add to topic_queue if novel

4. **Priority scoring:**
   - LLM assigns priority (1-10) based on:
     - Claim prevalence (how often it appears)
     - Source prominence (well-known apologist = higher)
     - Controversy level (debated claims = higher)

### Configuration

Admin portal settings:
- **Toggle:** Enable/disable auto-suggest
- **Frequency:** Daily, weekly, or manual trigger
- **Source list:** URLs/accounts to monitor
- **Quota:** Max new topics per run (default: 10)

### Implementation

```python
# Pseudo-code
async def run_auto_suggest():
    sources = get_configured_sources()
    for source in sources:
        content = await fetch_source(source)
        claims = await llm_extract_claims(content)
        for claim in claims:
            if not await is_duplicate(claim):
                priority = await llm_score_priority(claim)
                await topic_queue.add(
                    topic_text=claim.text,
                    source=source.url,
                    priority=priority,
                    status="queued"
                )
```

---

## Scheduled Generation

### Scheduler Architecture

**Approach:** APScheduler (Python background scheduler)

**Why not Celery?**
- Too heavy for single-server deployment
- APScheduler sufficient for predictable cron-style tasks
- Simpler dependency graph

**Why not FastAPI BackgroundTasks?**
- BackgroundTasks tie to request lifecycle (not persistent)
- Need scheduler that survives server restart

### Configuration

Admin-configurable settings:
- **Generation rate:** X posts per day/week (default: 1 per day)
- **Time window:** e.g., "Run between 2am-4am UTC"
- **Max concurrent:** Limit parallel pipeline runs (default: 2)

### Decomposer Agent

**New agent (runs BEFORE 5-agent pipeline):**

**Purpose:** Break topics into component claims for comprehensive analysis

**Input:** Topic from queue (e.g., "Noah's Flood")

**Output:** Variable number of component claims to fact-check (typically 3-12 depending on topic complexity)

**Example (Noah's Flood → 5 claims):**
- "A global flood covered the entire Earth ~4,000 years ago"
- "Noah's Ark could fit all animal species"
- "Geological evidence supports a worldwide flood"
- "Ancient flood myths prove the biblical account"
- "The flood explains fossil distribution"

**Implementation:**
- LLM: Claude Sonnet or GPT-4o (needs reasoning ability)
- Prompt: "Identify distinct factual claims within this apologetics topic that can be independently fact-checked"
- Number of claims varies by topic complexity (agent decides, not hardcoded)
- Deduplication: Check each component claim against existing claim_cards (semantic search >0.92 similarity)
- Only generate new claim cards for novel component claims
- Reuse existing claim cards where appropriate

### Scheduling Logic

```python
# Cron job runs at configured time
@scheduler.scheduled_job('cron', hour=2, minute=0)
async def scheduled_generation():
    settings = await get_admin_settings()

    # Pick highest priority queued topics
    topics = await topic_queue.get_top_priority(
        status="queued",
        limit=settings.posts_per_day
    )

    for topic in topics:
        await topic_queue.update_status(topic.id, "processing")
        try:
            # Step 1: Decomposer identifies component claims
            component_claims = await run_decomposer(topic.topic_text)

            # Step 2: Run 5-agent pipeline for each component claim
            claim_card_ids = []
            for claim in component_claims:
                # Check if claim already exists
                existing = await semantic_search(claim, threshold=0.92)
                if existing:
                    claim_card_ids.append(existing.id)
                else:
                    # Generate new claim card
                    claim_card = await run_5_agent_pipeline(claim)
                    claim_card_ids.append(claim_card.id)

            # Step 3: Generate blog post wrapper
            blog_post = await generate_blog_post(
                topic_text=topic.topic_text,
                claim_card_ids=claim_card_ids
            )

            # Update topic queue
            await topic_queue.update(
                topic.id,
                status="pending_review",
                blog_post_id=blog_post.id
            )
        except Exception as e:
            await topic_queue.update(
                topic.id,
                status="failed",
                error_message=str(e)
            )
```

### Fail Fast Behavior

**No retries:** Failed topics remain in queue with status="failed"
- Admin reviews error in failure monitor
- Admin can manually retry with adjustments

---

## Blog Post Composition

**How is the article generated?**

After decomposer + 5-agent pipeline creates claim cards, we need a synthesized prose article.

### Blog Composer Agent

**New agent:** Blog Composer (runs AFTER claim cards are generated)

**Input:**
- Topic text (e.g., "Noah's Flood")
- Array of generated claim_card_ids with full claim card content (verdict, short_answer, deep_answer, sources, etc.)

**Output:**
- Article title (engaging, accurate, not clickbait)
- Article body (FULL synthesized prose article)

**Article body structure:**
- Narrative prose that synthesizes findings from claim cards
- Tells cohesive story about the topic and what evidence reveals
- References claim cards contextually (footnotes/links: "[1]", "[see analysis of ark capacity]")
- Does NOT display claim cards as list
- Flows naturally as readable article

**Example article body (excerpt):**
```
The Genesis flood account makes several testable claims about Earth's history. Our analysis of geological evidence reveals no worldwide flood layer from the proposed timeframe (~4,000 years ago). The sedimentary record shows gradual deposition over millions of years, not catastrophic single-event layering [1].

Apologists argue Noah's ark could accommodate all animal species, but the mathematics show a vessel approximately one-tenth the necessary size [2]. Even accounting for "kinds" rather than species, the space requirements exceed biblical specifications by orders of magnitude.

While ancient flood myths exist globally, comparative mythology demonstrates they differ significantly from the biblical account in key details [3]. These variations suggest independent origin stories rather than corrupted memories of a single event...
```

**LLM:** Claude Sonnet 3.5 or GPT-4o (needs strong writing + synthesis ability)

**System prompt guidance:**
- Synthesize claim card findings into cohesive narrative
- Write engaging prose (not academic paper, not clickbait)
- Reference claim cards contextually (numbered references, contextual links)
- Tone: Calm, direct, forensic (matching claim card tone)
- Tell story: What does the evidence actually show?
- No misrepresentation, no sensationalism
- Length: 500-1500 words depending on topic complexity

### Fallback: Template-Based (If Composer Fails)

Simple template if Blog Composer agent fails:
```
Title: "Examining Claims About {topic}"
Body: "This article analyzes {N} factual claims commonly made about {topic}. [Brief summary of each claim verdict]"
```

---

## Review Workflow

### Admin Interface (Phase 3 UI)

**Review Queue View:**
```
╔════════════════════════════════════════════════════════════╗
║ Pending Review (3)                                         ║
╠════════════════════════════════════════════════════════════╣
║ [Blog Post Preview]                                        ║
║ Topic: "Noah's Flood"                                      ║
║ Title: "Noah's Flood: Examining the Claims..."            ║
║ Generated: 2026-01-16 02:15 UTC                            ║
║ Priority: 8                                                 ║
║ Component Claims: 5                                         ║
║                                                             ║
║ [Show Full Article (title + synthesized prose)]           ║
║ [Show Component Claim Cards (5)]                           ║
║ [Show Agent Audit Trails (decomposer + 5-agent + composer)]║
║                                                             ║
║ [Approve & Publish]  [Request Revision]  [Reject]          ║
║                                                             ║
║ Revision scope: [ ] Decomposer  [ ] Claim pipelines  [ ] Composer ║
║ Admin Feedback: _________________________________          ║
╚════════════════════════════════════════════════════════════╝
```

### Review Actions

**Approve & Publish:**
- Sets blog_posts.published_at = NOW()
- Sets topic_queue.review_status = "approved"
- Blog article appears in Read page
- Claim cards remain visible in Audits page (already were)
- All claim cards still usable in chat (were already)

**Request Revision:**
- Admin provides feedback (stored in topic_queue.admin_feedback)
- Topic status → "needs_revision"
- Options:
  - Re-run decomposer (if topic breakdown was wrong)
  - Re-run specific claim card pipeline (if individual claim was wrong)
  - Re-run blog composer (if title/intro was wrong)
- Admin specifies which component to re-run
- New blog post generated, awaits re-review

**Reject:**
- Topic status → "rejected"
- Blog post NOT published (won't appear in Read page)
- Claim cards remain in database (still in Audits, still usable in chat)
- Admin can provide reason (archived for learning)

---

## Read Page vs Audits Page

### Read Page: Blog Articles

**Shows:** Published blog articles (blog_posts where published_at NOT NULL)

**Content:** Synthesized prose articles that tell cohesive stories using claim card findings

**Example article:**
```
Title: "Noah's Flood: Examining the Claims Behind a Global Deluge"

Article body:
The Genesis flood account makes several testable claims about Earth's history. Our analysis of geological evidence reveals no worldwide flood layer from the proposed timeframe (~4,000 years ago). The sedimentary record shows gradual deposition over millions of years, not catastrophic single-event layering [1].

Apologists argue Noah's ark could accommodate all animal species, but the mathematics show a vessel approximately one-tenth the necessary size [2]...

[References]
[1] Analysis: Global flood timing
[2] Analysis: Ark capacity
...
```

**Endpoint:**
```
GET /api/blog/posts
Query params:
  - limit (default: 20)
  - offset (default: 0)
  - category (optional filter: Genesis, Canon, etc.)

Response:
{
  "posts": [
    {
      "id": "uuid",
      "title": "Noah's Flood: Examining the Claims...",
      "article_body": "The Genesis flood account...",
      "claim_card_ids": ["uuid1", "uuid2", "uuid3"],
      "published_at": "2026-01-16T12:00:00Z",
      ...
    }
  ],
  "total": 42,
  "has_more": true
}
```

### Audits Page: Claim Card Repository

**Shows:** All individual claim cards (where visible_in_audits = TRUE)

**Content:** Atomic claim cards, browsable independently

**Use case:**
- User wants to find specific claim without reading full article
- User wants to browse all claims about "authorship" or "Genesis"
- Direct linking to individual claim cards

**Endpoint:**
```
GET /api/audits/cards
Query params:
  - limit (default: 50)
  - offset (default: 0)
  - category (optional filter: Genesis, Canon, etc.)
  - verdict (optional filter: True, False, Misleading, etc.)
  - search (optional text search on claim_text)

Response:
{
  "claim_cards": [
    {
      "id": "uuid",
      "claim_text": "...",
      "verdict": "Misleading",
      "short_answer": "...",
      "category_tags": ["Canon", "History"],
      ...
    }
  ],
  "total": 387,
  "has_more": true
}
```

### UI Layouts

**Read Page:**
- List/grid of article cards (title + article_body preview/excerpt)
- Click article → Full article page showing synthesized prose
- Article includes contextual references to claim cards (clickable footnotes/links)
- Clicking reference opens claim card in modal/sidebar
- Filters: Category, Sort (newest, most component claims)

**Audits Page:**
- Grid of claim card summaries (3-4 columns desktop)
- Each card: claim_text, verdict badge, short_answer preview
- Click card → Full claim card modal/page
- Filters: Category, Verdict, Search
- Sort: Newest, Relevance (if search)

---

## API Design

### Admin Endpoints

```
Topic Queue Management:
POST   /api/admin/topics                 # Add topic manually
GET    /api/admin/topics                 # List all topics (with filters)
PUT    /api/admin/topics/{id}            # Update topic (priority, status)
DELETE /api/admin/topics/{id}            # Remove topic

Review Workflow:
GET    /api/admin/review/pending         # Get topics pending review
POST   /api/admin/review/{id}/approve    # Approve & publish
POST   /api/admin/review/{id}/revision   # Request revision
POST   /api/admin/review/{id}/reject     # Reject

Auto-Suggest:
POST   /api/admin/autosuggest/trigger    # Manual trigger
GET    /api/admin/autosuggest/settings   # Get config
PUT    /api/admin/autosuggest/settings   # Update config

Scheduler:
GET    /api/admin/scheduler/settings     # Get generation rate config
PUT    /api/admin/scheduler/settings     # Update schedule
POST   /api/admin/scheduler/run-now      # Manual generation trigger
```

### Public Endpoints

```
Read Page (Blog Articles):
GET    /api/blog/posts                   # List published blog articles
GET    /api/blog/posts/{id}              # Get specific article with claim cards

Audits Page (Claim Cards):
GET    /api/audits/cards                 # List all claim cards (visible_in_audits=TRUE)
GET    /api/audits/cards/{id}            # Get specific claim card
```

---

## Implementation Breakdown

### Phase 3.1: Database & Topic Queue (Session 1)
- Migration: Create blog_posts table
- Migration: Add visible_in_audits to claim_cards
- Migration: Add review_status, reviewed_at, admin_feedback, blog_post_id to topic_queue
- Repository methods: topic_queue CRUD operations
- API endpoints: POST/GET/PUT/DELETE /api/admin/topics

### Phase 3.2: Decomposer & Blog Composer (Session 2)
- Decomposer agent: Break topics into component claims
- Blog Composer agent: Generate article title + intro
- Agent prompts (seed database)
- Deduplication logic (semantic search for component claims)

### Phase 3.3: Scheduler & Auto-Suggest (Session 3)
- Install APScheduler
- Scheduler service: Decomposer → 5-agent pipeline → Blog composer flow
- Auto-suggest service: LLM-based topic discovery
- API endpoints: /api/admin/scheduler/*, /api/admin/autosuggest/*

### Phase 3.4: Review Workflow Backend (Session 4)
- Review service: Approve/reject/revision logic (blog posts, not individual cards)
- Selective re-run: Decomposer vs specific claim card vs composer
- API endpoints: /api/admin/review/*

### Phase 3.5: Read & Audits Backend (Session 5)
- Blog posts service: Query published articles
- Audits service: Query all claim cards with filters
- API endpoints: GET /api/blog/posts/*, GET /api/audits/cards/*
- Pagination/filtering logic

### Phase 3.6: Admin UI (Session 6)
- Topic queue management page
- Review interface (blog post preview + component claim cards)
- Settings page (scheduler, auto-suggest config)

### Phase 3.7: Read & Audits UI (Session 7)
- Read page: Blog article list + full article view
- Audits page: Claim card grid + full card modal
- Filters and sorting for both pages

---

## Success Criteria

Phase 3 succeeds when:

1. **Topic queue works:**
   - Admin can add topics manually
   - Topics have priority and status tracking
   - Failed topics visible in admin portal

2. **Scheduled generation works:**
   - Scheduler runs at configured time
   - Picks highest priority topics
   - Decomposer breaks topics into component claims (variable count: 3-12)
   - 5-agent pipeline runs for each novel component claim
   - Blog Composer generates FULL ARTICLE (title + synthesized prose body, 500-1500 words)
   - Blog post created and queued for review
   - Fails fast on errors (no silent failures)

3. **Auto-suggest works:**
   - Discovers new topics from configured sources
   - LLM extracts apologetics topics
   - Deduplicates against existing topics
   - Adds novel topics to queue with priority

4. **Review workflow works:**
   - Admin sees pending blog posts with component claim cards
   - Can approve/reject/request revision
   - Revision allows selective re-run (decomposer/pipeline/composer)
   - Approved blog posts published to Read page
   - Claim cards remain in Audits regardless of blog post status

5. **Read page works:**
   - Shows only published blog articles
   - Article view displays synthesized prose article with contextual claim card references
   - Supports filtering by category
   - Pagination or infinite scroll

6. **Audits page works:**
   - Shows all individual claim cards (visible_in_audits=TRUE)
   - Supports filtering by category/verdict
   - Supports text search on claim_text
   - Grid layout with full card modal/page
   - Independent of blog post publication status

---

## Consequences

### Benefits
- **Proactive library building** - Claim cards generated ahead of user questions
- **Quality control** - Human review before publication
- **Discovery** - Automated monitoring of apologetics ecosystem
- **Transparency** - Blog showcases audited content
- **Scalability** - Scheduler handles high-volume generation

### Trade-offs
- **Admin overhead** - Requires human review (acceptable for quality)
- **Scheduler complexity** - APScheduler adds dependency (mitigated: simple setup)
- **Auto-suggest cost** - LLM calls for discovery (acceptable: batch processing)

### Constraints
- **No shortcuts** - All content through 5-agent pipeline (enforced)
- **Fail fast** - No automatic retries (enforced)
- **Admin required** - No auto-publishing without review (enforced)

---

## Non-Goals

**Deferred to Phase 4+:**
- User-submitted topics (admin-only for now)
- Social features (comments, likes)
- Email/RSS subscriptions to blog feed
- Automated fact-checking of specific authors/organizations
- SEO optimization (accuracy over discoverability)

---

## Open Questions

**Resolved during planning:**

1. **How does auto-suggest work?**
   - LLM + web crawling of configured apologetics sources
   - Extracts factual claims, deduplicates, adds to queue

2. **When do claims become published?**
   - After admin approval (sets published_at timestamp)
   - All claims usable in chat immediately after pipeline

3. **Blog feed scope?**
   - Only admin-approved claims (published_at NOT NULL)
   - Chat uses all audited claims

4. **Scheduling approach?**
   - APScheduler (cron-style, configurable rate)
   - Admin sets posts per day/week

5. **Review interface?**
   - Pending queue page in admin portal
   - Actions: Approve, Reject, Request Revision
   - Revision re-runs pipeline with admin feedback

---

**Status:** Planning complete, ready for implementation.
