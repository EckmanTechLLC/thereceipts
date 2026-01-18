## Project Description (for Claude Code)

### Goal
Build a religion claim–analysis platform focused on Christianity that helps users weed out false, misleading, or dishonest claims made by Christian authors, apologists, and organizations.

This system is not for courts, schools, or activism.
It is for individual users in deconversion or questioning stages who want fast, accurate, sourced answers.

---

## Core Concept
The system audits claims, not beliefs.

Users can:
- **Ask questions** (chat mode with intelligent routing)
- **Read blog posts** (curated multi-claim analyses)
- **Browse claim cards** (searchable audit repository)
- **Explore sources** (all citations with verification status)

All content is powered by Claim Cards generated and verified by a transparent 5-agent pipeline with 6-tier source verification.

---

## Core Principles (hard constraints)
- Claim-centric, not belief-centric
- Author-targeted audits are allowed (e.g., Ken Ham, AiG writers)
- Clickbait titles are allowed; misrepresentation is not
- Every factual assertion must be sourced
- Uncertainty must be stated explicitly
- Agent steps and checks must be transparent to users

No “both sides” framing. No apologetics. No advocacy.

---

## The Elevator (mandatory)
All content must be simple, clean, and easy to understand by default, with optional drill-down for details.

Each answer/post must be structured as:
1) Bottom Line (always visible): plain-language summary that stands alone as accurate
2) Expandable sections: deeper reasoning, evidence, sources, and audit details

Depth is opt-in. The default view must never assume prior biblical, academic, or theological knowledge.

---

## Output Structure (mandatory for all answers)
Every response (chat or blog) must follow this structure:

1. Claim
	- Exact quote or paraphrase
	- Source (author, work, date, link)

2. Verdict
	- One of: True / Misleading / False / Unfalsifiable / Depends on Definitions

3. Short Answer
	- Plain-language summary (≤150 words)

4. Why This Claim Persists
	- Psychological, social, or institutional reasons (bullet list)

5. Evidence Review
	- What primary sources say
	- What mainstream scholarship says
	- Clear distinction between evidence types

6. Sources
	- Primary sources (ancient texts, manuscripts, councils, original writings)
	- Scholarly sources (peer-reviewed or academic press)

7. Apologetics Techniques Used (if any)
	- e.g., quote-mining, category error, false dichotomy, moving goalposts

8. Confidence Level
	- High / Medium / Low
	- Explanation of why

---

## Multi-Agent Pipeline (implemented)
All content passes through these agents in sequential order:

### 1. Topic Finder Agent
- Identifies:
	- common apologetics claims
	- claims made by known Christian authors
	- frequent deconversion questions
- Outputs: claim + claimant + claim_type + category tags

### 2. Source Checker Agent
**6-Tier Source Verification System:**
- **Tier 0**: Verified Source Library (reuse previously verified book/paper metadata with fresh quotes)
- **Tier 1**: Google Books API (books with page-verified snippets)
- **Tier 2**: Semantic Scholar API (academic papers, arXiv, PubMed)
- **Tier 3**: Ancient Texts APIs (CCEL, Perseus Digital Library for patristic/classical sources)
- **Tier 4**: Tavily API (web sources with URL verification)
- **Tier 5**: LLM fallback (with explicit transparency about unverified status)

Verification metadata tracked: method, status, content_type, url_verified

### 3. Adversarial Checker Agent
- Attempts to falsify the draft
- **Re-verifies each source** using same 6-tier API system
- Verifies:
	- quotes match actual source content (word overlap check)
	- sources are not out of context
	- URLs are valid and lead to correct sources
	- confidence is not overstated
- Flags discrepancies but **does not fail pipeline** (transparency over failure)

### 4. Writing Agent
- Produces final prose:
	- calm, direct, forensic tone
	- no mocking, no rhetorical preaching
	- accessible to non-academics
	- structured output (short answer, deep answer, why persists, evidence, sources)

### 5. Publisher Agent
- Adds:
	- agent audit summary (what each agent checked)
	- known limitations
	- what evidence would change the verdict
	- confidence level with explanation
- Stores verification metadata for UI transparency

---

## Data Model (implemented)
**Claim Card Schema:**
- claim_text
- claimant (author / org)
- claim_type (technical categorization)
- category_tags[] (broad UI navigation: Genesis, Canon, Doctrine, Ethics, Institutions)
- verdict (True / Misleading / False / Unfalsifiable / Depends on Definitions)
- short_answer (≤150 words)
- deep_answer (detailed analysis)
- why_persists[] (psychological/social reasons as bullet list)
- sources[] with verification metadata:
  - citation, url, quote_text, usage_context
  - verification_method (library_reuse, google_books, semantic_scholar, ccel, perseus, tavily, llm_unverified)
  - verification_status (verified, partially_verified, unverified)
  - content_type (exact_quote, verified_paraphrase, unverified_content)
  - url_verified (boolean)
- apologetics_tags[] (techniques used: quote-mining, category error, etc.)
- confidence_level (High / Medium / Low) + explanation
- agent_audit (JSONB: what each agent checked, reverification results)

**Blog Posts:**
- Multiple related claim cards synthesized into prose articles (500-1500 words)
- Generated by Decomposer (breaks topic into component claims) + Blog Composer (synthesizes article)
- Admin review workflow (approve/reject/revision)

**Topic Queue:**
- Manually added or auto-discovered via web search (Tavily)
- Priority scoring, status tracking (queued, processing, completed, failed)

**Verified Sources Library:**
- Stores book/paper metadata from Tiers 1-2 for reuse
- Semantic search + LLM relevance check
- Fresh quotes generated per claim (metadata only, not quote storage)

**Chat Routing:**
- Router Agent decides response mode based on semantic similarity:
  - Mode 1 (≥0.92): Return existing claim card (~2s)
  - Mode 2 (0.80-0.92): Synthesize from multiple existing cards (~5-10s)
  - Mode 3 (<0.80): Full 5-agent pipeline (~45-60s)
- RouterDecision table tracks mode selection for analytics

---

## UI Implementation
**Public Frontend** (React + TypeScript, port 5173):

1. **Home Page**
   - System introduction and how it works
   - Live metrics (total claims, blogs, questions answered)
   - AI disclaimer and terms of service

2. **Ask (Chat)**
   - Question input with real-time WebSocket progress updates
   - Claim cards displayed inline with conversations
   - Expandable "Show Your Work" sections (default collapsed)
   - Source citations with verification badges (✓ verified, ⓘ partially verified, ⚠ unverified)
   - Router mode displayed (exact match, contextual, or novel generation)

3. **Read (Blog)**
   - Published blog posts (synthesized multi-claim articles)
   - Full-width prose with embedded claim cards
   - Category filtering

4. **Audits (Repository)**
   - Searchable claim card library
   - Filter by category, verdict, confidence
   - Paginated results
   - Direct links to sources

5. **Sources**
   - All sources sorted by reference count
   - Verification method labels (Google Books, CCEL, AI Training Data, etc.)
   - Filter by verification status and source type
   - Click through to source URLs

**Admin UI** (React + TypeScript, port 5174):

1. **Topic Queue**
   - View all queued topics with priority
   - Trigger generation manually
   - Clear queue

2. **Review**
   - Approve/reject/revision workflow
   - Preview blog posts before publishing
   - Selective re-run (decomposer/pipeline/composer)

3. **Settings**
   - Auto-suggest configuration (enable/disable, dedup threshold)
   - Scheduler configuration (interval, enabled status)
   - "Discover Topics" button (automatic web discovery via Tavily)
   - Manual text extraction form (paste content, extract claims)
   - Database reset (danger zone: clear test data, preserve config + verified sources)

**Design Features:**
- Dark/light theme toggle
- Sticky navigation header
- No gamification, no social metrics
- Verification transparency without alarmism

---

## Technical Implementation

**Backend Stack:**
- FastAPI (Python async, REST + WebSocket)
- PostgreSQL + pgvector extension (semantic search with embeddings)
- Alembic (database migrations)
- APScheduler (auto-blog generation on schedule)
- SQLAlchemy 2.0 (async ORM)

**Frontend Stack:**
- React 18 + TypeScript
- React Router (client-side routing)
- Vite (build tool)
- CSS modules (component styling)

**AI/ML Integration:**
- Anthropic Claude (agent pipeline - topic finding, source checking, adversarial review, writing)
- OpenAI GPT-4 (embeddings for semantic search, context analysis for routing)
- Provider selection per agent based on strengths (sequential pipeline, not parallel)

**Source Verification APIs:**
- Google Books API (Tier 1: books)
- Semantic Scholar API (Tier 2: academic papers)
- CCEL web scraping (Tier 3: Christian classics)
- Perseus Digital Library (Tier 3: ancient texts)
- Tavily API (Tier 4: web search, also used for auto-suggest topic discovery)

**Key Architecture Decisions:**
- Sequential agent pipeline (not parallel) - each agent sees previous agent's output
- Database-stored prompts (editable without code changes)
- Fail-fast design (no retries on LLM calls, transparent failures)
- Two-layer content: Data integrity layer (audited claim cards) + Conversational layer (fast synthesis)
- WebSocket for real-time progress (agent status, pipeline events)
- Session-based chat (frontend sessionStorage, no long-term conversation persistence)

---

## Explicit Non-Goals
- No debates with believers
- No religious accommodation
- No neutrality framing
- No legal or educational compliance targets
- No algorithm chasing (SEO secondary, accuracy primary)

---

## Success Criteria
The system succeeds if:
- a user can quickly determine whether a Christian claim is BS
- sources are clear and checkable
- confidence feels earned, not asserted
- the system explains why the claim feels convincing

---

## Implementation Status (as of 2026-01-18)

**Phase 1-3: Foundation & Core Features** ✅ COMPLETE
- Database schema with pgvector for semantic search
- 5-agent pipeline (Topic Finder, Source Checker, Adversarial, Writer, Publisher)
- WebSocket real-time progress updates
- Chat mode with intelligent routing (3 modes: exact/contextual/novel)
- Blog mode with Decomposer and Blog Composer agents
- Admin UI for topic queue, review workflow, and settings
- Auto-suggest with manual text extraction
- Scheduler for automated blog generation

**Phase 4.1: Multi-Source Verification** ✅ COMPLETE
- 6-tier API verification system implemented
- Verified Source Library (Tier 0) for metadata reuse
- Google Books API integration (Tier 1)
- Semantic Scholar API integration (Tier 2)
- CCEL + Perseus Digital Library integration (Tier 3)
- Tavily API integration (Tier 4)
- LLM fallback with transparency (Tier 5)
- Adversarial Checker re-verification with quote comparison
- UI verification badges and method labels

**Phase 4.2: UI Enhancements** ✅ COMPLETE
- Home page with live metrics and disclaimers
- Sources page with reference counts and filters
- Sticky navigation header
- Knowledge graph visualization (ReactFlow-based, currently hidden from nav)

**Phase 4.3: Admin Enhancements** ✅ COMPLETE
- Database reset feature (preserves config + verified sources library)
- Auto-suggest web discovery via Tavily (automatic claim discovery)
- Intra-blog deduplication fix (prevents premature claim skipping)

**Production Readiness:**
- All core features implemented and tested
- Source verification functional with real API integrations
- Admin tools for content management and system maintenance
- Ready for deployment planning
