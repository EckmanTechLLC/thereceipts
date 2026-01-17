# Phase 3 Planning Session

**Date:** 2026-01-16
**Type:** Planning/Architecture Discussion
**Participants:** User + Claude

---

## Context

Phase 1 (Foundation) and Phase 2 (Conversational Chat) complete. Phase 2 includes intelligent routing with Router Agent (ADR 002). System can generate claim cards on-demand via chat and reuse existing audited claims.

**Gap:** Claim library grows reactively (user questions only). Need proactive generation for comprehensive knowledge base.

---

## Planning Scope

Create ADR 003: Auto-Blog System covering:
1. Problem statement
2. Requirements (5 sub-features)
3. Database schema modifications
4. API design (admin + public endpoints)
5. Scheduler approach
6. Review workflow
7. Implementation breakdown (6 sessions)
8. Success criteria

---

## Key Decisions

### 1. Three Distinct Pages: Ask, Read, Audits

**Critical distinction:**
- **Ask** (Phase 2, complete) - Chat interface with claim cards
- **Read** - Blog articles (topics → decomposer → multiple claim cards → SYNTHESIZED PROSE ARTICLE)
- **Audits** - Claim card repository (browse ALL individual claim cards)

**Read ≠ Audits:**
- Read page shows blog articles (synthesized prose that tells cohesive story using claim card findings)
- Blog articles reference claim cards contextually (footnotes/links), not displayed as list
- Audits page shows individual claim cards (atomic unit, directly browsable)
- Example: Topic "Noah's Flood" → 5 component claims → 1 synthesized article (Read) + 5 claim cards (Audits)

### 2. Decomposer Agent: Topic → Component Claims

**New agent (6th agent, runs BEFORE 5-agent pipeline):**

**Purpose:** Break topics into component factual claims for comprehensive analysis

**Example:**
- Topic: "Noah's Flood"
- Decomposer output (5 claims in this case):
  1. "A global flood covered the entire Earth ~4,000 years ago"
  2. "Noah's Ark could fit all animal species"
  3. "Geological evidence supports a worldwide flood"
  4. "Ancient flood myths prove the biblical account"
  5. "The flood explains fossil distribution"

**Number of claims: Variable (3-12 depending on topic complexity)**
- Decomposer agent decides based on topic
- Not hardcoded to 5 claims
- Simple topics might yield 3 claims, complex topics might yield 12

Each component claim runs through 5-agent pipeline → claim cards

**Deduplication:** Semantic search before generating (>0.92 similarity = reuse existing)

### 3. Blog Post Entity: Synthesized Article

**New database table: blog_posts**

**Fields:**
- title (e.g., "Noah's Flood: Examining the Claims Behind a Global Deluge")
- article_body (FULL synthesized prose article, 500-1500 words)
- claim_card_ids (array of UUIDs from component claims, referenced within article)
- published_at (NULL = not published, NOW() = published to Read page)

**Generation:** Blog Composer agent writes FULL ARTICLE (title + prose body) after claim cards are generated

**Article structure:** Synthesized narrative prose, NOT list of claim cards. References claim cards contextually (footnotes/links).

### 4. Blog Composer Agent: Article Synthesis

**New agent (runs AFTER decomposer + 5-agent pipeline):**

**Input:**
- Topic text
- Generated claim_card_ids with full claim card content (verdicts, evidence, sources)

**Output:**
- Article title (engaging, accurate, not clickbait)
- Article body (FULL synthesized prose that tells cohesive story)

**Article synthesis:**
- Narrative prose synthesizing findings from claim cards
- References claim cards contextually: "[1]", "[see ark capacity analysis]"
- Flows naturally as readable blog article
- Length: 500-1500 words depending on topic complexity

**LLM:** Claude Sonnet 3.5 or GPT-4o (needs strong writing + synthesis)

### 5. Scheduler Flow: Decomposer → Pipeline → Composer

**Full generation flow:**
1. Pick highest priority topic from queue
2. Run Decomposer → list of component claims (variable count: 3-12 depending on topic)
3. For each component claim:
   - Semantic search for existing claim card (>0.92 similarity)
   - If found: Reuse existing claim_card_id
   - If not found: Run 5-agent pipeline → new claim card
4. Run Blog Composer → generate title + full synthesized article body
5. Create blog_posts row with title, article_body, claim_card_ids
6. Queue for admin review

### 6. Auto-Suggest: LLM + Web Crawling

**How it works:**
1. Configure apologetics sources (AiG, WLC, CARM, Twitter accounts, YouTube channels)
2. Crawl sources periodically (daily/weekly)
3. LLM extracts factual claims from content
4. Deduplicate via semantic search (>0.85 similarity)
5. Add novel claims to topic_queue with priority score

**Priority scoring:** LLM judges based on prevalence, source prominence, controversy level

**Configuration:** Admin toggle + frequency + source list

### 7. Scheduler: APScheduler

**Choice:** APScheduler (not Celery, not BackgroundTasks)

**Why APScheduler:**
- Cron-style scheduling sufficient for predictable tasks
- Lighter than Celery (no message broker required)
- Persistent (survives server restart)

**Why not Celery:**
- Too heavy for single-server deployment
- Adds Redis/RabbitMQ dependency unnecessarily

**Why not BackgroundTasks:**
- Tied to request lifecycle (not persistent)
- No cron-style scheduling

**Configuration:** Admin sets posts per day/week + time window

### 8. Review Workflow: Blog Posts (Not Individual Cards)

**Admin reviews blog posts (not individual claim cards):**

**Approve & Publish:**
- Sets blog_posts.published_at = NOW()
- Blog article appears in Read page
- Component claim cards remain in Audits (were already there)

**Request Revision:**
- Admin provides feedback
- Options for re-run:
  - Re-run decomposer (if topic breakdown wrong)
  - Re-run specific claim card pipeline (if individual claim wrong)
  - Re-run blog composer (if title/intro wrong)
- Admin specifies which component needs re-work

**Reject:**
- Blog post NOT published (won't appear in Read page)
- Claim cards remain in database (Audits page + chat)

### 9. Fail Fast: No Automatic Retries

**Failed topics:**
- Status = "failed"
- Error message stored in topic_queue.error_message
- Visible in admin failure monitor
- Admin manually retries after adjustments

**Rationale:** Consistent with ADR 001 principle (fail fast, no silent failures)

---

## Database Schema Changes

### New table: blog_posts
```sql
CREATE TABLE blog_posts (
    id UUID PRIMARY KEY,
    topic_queue_id UUID REFERENCES topic_queue(id),
    title VARCHAR(500) NOT NULL,
    article_body TEXT NOT NULL,  -- Full synthesized prose article
    claim_card_ids UUID[] NOT NULL,
    published_at TIMESTAMP NULL,
    reviewed_by VARCHAR(200) NULL,
    review_notes TEXT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### claim_cards table additions:
```sql
ALTER TABLE claim_cards ADD COLUMN visible_in_audits BOOLEAN DEFAULT TRUE;
```

### topic_queue table additions:
```sql
ALTER TABLE topic_queue ADD COLUMN review_status VARCHAR(50) DEFAULT 'pending_review';
ALTER TABLE topic_queue ADD COLUMN reviewed_at TIMESTAMP NULL;
ALTER TABLE topic_queue ADD COLUMN admin_feedback TEXT NULL;
ALTER TABLE topic_queue ADD COLUMN blog_post_id UUID NULL;
```

---

## API Design Summary

### Admin Endpoints
- Topic queue: POST/GET/PUT/DELETE /api/admin/topics
- Review: GET /api/admin/review/pending, POST /api/admin/review/{id}/{action}
- Auto-suggest: POST /api/admin/autosuggest/trigger, GET/PUT /api/admin/autosuggest/settings
- Scheduler: GET/PUT /api/admin/scheduler/settings, POST /api/admin/scheduler/run-now

### Public Endpoints
- Read page: GET /api/blog/posts (list articles), GET /api/blog/posts/{id} (article with claim cards)
- Audits page: GET /api/audits/cards (list all claim cards), GET /api/audits/cards/{id} (single card)

---

## Implementation Plan (7 Sessions)

### Phase 3.1: Database & Topic Queue
- Migration: Create blog_posts table
- Migration: Add visible_in_audits to claim_cards
- Migration: Add review fields to topic_queue
- Repository methods (topic_queue CRUD)
- API endpoints (admin topic management)

### Phase 3.2: Decomposer & Blog Composer
- Decomposer agent (break topics into component claims)
- Blog Composer agent (generate title + intro)
- Agent prompts (seed database)
- Deduplication logic (semantic search)

### Phase 3.3: Scheduler & Auto-Suggest
- APScheduler setup
- Full scheduler flow (decomposer → pipeline → composer)
- Auto-suggest service (LLM topic discovery)
- API endpoints (scheduler/autosuggest config)

### Phase 3.4: Review Workflow Backend
- Review service (blog posts, not individual cards)
- Selective re-run (decomposer/pipeline/composer)
- API endpoints (review actions)

### Phase 3.5: Read & Audits Backend
- Blog posts service (query published articles)
- Audits service (query all claim cards)
- API endpoints (separate for blog/audits)
- Pagination/filtering

### Phase 3.6: Admin UI
- Topic queue management
- Review interface (blog post + component cards)
- Settings page (scheduler, auto-suggest)

### Phase 3.7: Read & Audits UI
- Read page (article list + full article view)
- Audits page (claim card grid + full card modal)
- Filters/search for both pages

---

## Open Questions (Resolved)

**Q: What's the difference between Read and Audits pages?**
A: Read = synthesized prose articles that tell cohesive stories using claim card findings (500-1500 words). Audits = individual claim cards (all, browsable independently).

**Q: How does decomposer work?**
A: LLM breaks topics into component factual claims (3-12 claims depending on complexity). Each runs through 5-agent pipeline (or reuses existing via semantic search >0.92).

**Q: How are blog articles generated?**
A: Blog Composer agent writes FULL ARTICLE (title + synthesized prose body) after claim cards are generated. Article references claim cards contextually, doesn't display them as list.

**Q: What does admin review?**
A: Blog posts (full articles with synthesized prose), not individual claim cards. Can selectively re-run decomposer/pipeline/composer if needed.

**Q: When are claim cards visible in Audits?**
A: Always (visible_in_audits=TRUE by default). Independent of blog post publication status.

**Q: How does auto-suggest work?**
A: LLM + web crawling discovers topics (not individual claims). Topics added to queue for decomposition.

---

## Success Criteria

Phase 3 succeeds when:

1. Topic queue functional (manual add, status tracking, failure visibility)
2. Decomposer breaks topics into component claims (variable count: 3-12)
3. Scheduler runs decomposer → pipeline → composer flow
4. Blog Composer generates FULL ARTICLE (title + synthesized prose body, 500-1500 words)
5. Auto-suggest discovers new topics, deduplicates, adds to queue
6. Review workflow allows approve/reject/revision (blog posts, not individual cards)
7. Read page shows published synthesized prose articles (references claim cards contextually)
8. Audits page shows all individual claim cards independently

---

## Next Steps

1. Create ADR 003 (COMPLETE)
2. Implement Phase 3.1 (Database & Topic Queue)
3. Implement Phase 3.2 (Decomposer & Blog Composer)
4. Implement Phase 3.3 (Scheduler & Auto-Suggest)
5. Implement Phase 3.4 (Review Workflow)
6. Implement Phase 3.5 (Read & Audits Backend)
7. Implement Phase 3.6 (Admin UI)
8. Implement Phase 3.7 (Read & Audits UI)

---

## Notes

**User preferences honored:**
- Concise ADR (~300 lines)
- Concise session notes (~200 lines)
- Small incremental changes (6 implementation sessions)
- Document as we go (ADR + session notes)
- Ask before expanding scope

**Core principles maintained:**
- All content through 5-agent pipeline (no shortcuts)
- Fail fast (no silent retries)
- Transparency (admin sees all decisions)
- Quality over speed (human review required)

---

**Status:** Planning complete, ADR 003 created, ready for Phase 3.1 implementation.
