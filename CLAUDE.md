# TheReceipts Context for Claude

**Last Updated:** 2026-01-16
**Current Phase:** Phase 3 Complete (Auto-Blog), Phase 4 Defined (Admin Enhancements)

---

## Quick Reference

**Project:** TheReceipts - Religion claim analysis platform (Christianity focus)
**Architecture:** Python/FastAPI + React + PostgreSQL/pgvector
**Key Docs:**
- `/docs/decisions/001-core-architecture-and-system-design.md` - Core decisions
- `/docs/decisions/002-intelligent-routing.md` - Router Agent (Phase 2)
- `/docs/decisions/003-auto-blog-system.md` - Auto-Blog (Phase 3)
- `/docs/decisions/004-multi-source-verification.md` - Source verification (Phase 4)
- `/README.md` - Project overview
- `/DESCRIPTION.md` - Detailed project requirements

---

## User Preferences (Apply Always)

- Never be verbose - clear, concise responses
- Small, incremental changes - don't build everything at once
- Ask before expanding scope - stay within defined task
- Document as you go - ADRs for decisions, session notes for progress
- Show, don't just talk about it

---

## Current Status

### Initial Setup (COMPLETE ✓)
- [x] Project directory created
- [x] Documentation structure established
- [x] Workflow documentation copied
- [x] Project description and goals defined
- [x] Core architecture decisions (ADR 001)

### Phase 1: Foundation (COMPLETE ✓)
- [x] 1.1: Database setup (thereceipts_dev, schema, pgvector, migrations)
- [x] 1.2: FastAPI scaffold (main.py, session, repositories, category_tags, agent seed)
- [x] 1.3: React frontend scaffold (Vite, Router, TopNav, 3 pages, theme toggle, API client)
- [x] 1.4: Agent pipeline structure (5 agent classes, orchestrator)
- [x] 1.5: WebSocket infrastructure (real-time progress updates)

### Phase 2: Conversational Chat (COMPLETE ✓)
- [x] 2.1: Context Analyzer + Semantic Search (embeddings, pgvector, reformulation)
- [x] 2.2: Chat backend integration (conversation context, response formatting)
- [x] 2.3: Chat UI (message thread, claim cards in chat, expandable sections)
- [x] 2.4: Integration & polish (end-to-end flow, error handling)
- [x] 2.5: Testing & bug fixes (2026-01-13 to 2026-01-14):
  - Show Your Work UI behavior (subsections hidden by default)
  - Source URL hallucination (removed coercive prompt language)
  - Pipeline progress visibility (WebSocket event handling)
  - Claim card header clarity (added "Claim:" label)
  - Writing agent phantom quotes (prompt fix)
  - Semantic search threshold tuning (0.85 → 0.92)
  - Context analyzer alternative explanation handling
- [x] 2.6: Intelligent Routing (2026-01-14 to 2026-01-16):
  - Router Agent foundation (tool calling, router_decisions table, ADR 002)
  - Tool implementation (search_existing_claims, get_claim_details, generate_new_claim)
  - API integration (POST /api/chat/ask, mode-specific handlers, WebSocket events)
  - Frontend updates (contextual response UI, source cards, markdown rendering)
  - Bug fixes: Router Agent system prompt loading, context preservation, mode detection

### Phase 3: Auto-Blog (COMPLETE ✓)
- [x] 3.1: Database & Topic Queue (topic_queue, blog_posts tables, admin API)
- [x] 3.2: Decomposer & Blog Composer agents (2 new agents, prompts)
- [x] 3.3: Scheduler & Auto-Suggest (APScheduler, full generation flow, topic discovery)
- [x] 3.4: Review Workflow Backend (approve/reject/revision logic, selective re-run)
- [x] 3.5: Read & Audits Backend (public endpoints for published blog posts and visible claim cards)
- [x] 3.6: Admin UI (standalone application on port 5174, topic queue, review interface, settings)
- [x] 3.7: Read & Audits UI (public-facing blog articles and claim card repository)

### Phase 4: Source Verification & Admin Enhancements (NOT STARTED)
- [ ] 4.1: Multi-Source Verification (6-tier API integration for verified citations/quotes - ADR 004)
  - [ ] 4.1a: Core API Integration + Library (Google Books, Semantic Scholar, Tavily, verified_sources table)
  - [ ] 4.1b: Adversarial Re-Verification
  - [ ] 4.1c: Ancient Texts Integration (CCEL, Perseus, Early Church Texts)
  - [ ] 4.1d: UI Transparency (verification status display)
- [ ] 4.2: Agent Prompt Editor (UI for editing system prompts, LLM config per agent)
- [ ] 4.3: Bulk Topic Import (CSV/JSON bulk upload for topic queue)
- [ ] 4.4: Database Reset Feature (admin UI to clear test data, preserve config + verified sources library)

---

## Key Decisions

**ADR 001 - Core Architecture:**
1. Tech stack: Python/FastAPI + React + PostgreSQL/pgvector
2. 5-agent sequential pipeline (Topic Finder → Source Checker → Adversarial → Writer → Publisher)
3. LLMs: Different providers per agent (Anthropic + OpenAI), DB-stored prompts
4. Chat: Question decomposer → semantic search → compose from existing or generate new
5. Blog: Auto-generated claim library with review queue
6. Auto-suggest: LLM + web search for new topics (configurable toggle)
7. Admin portal: Topic queue, settings, review interface, failure monitor
8. Fail fast: No retries, no placeholders, full transparency
9. Dual categorization: claim_type (technical) + category_tags (broad UI nav: Genesis, Canon, Doctrine, Ethics, Institutions)

**Phase 2 Planning - Conversational Chat:**
1. Intelligent routing: Context Analyzer → Semantic Search → Pipeline (if needed)
2. Context Analyzer: Lightweight LLM reformulates questions with conversation history
3. Session-based: Frontend sessionStorage, no long-term persistence
4. UI: Full-width message thread (desktop only), expandable claim cards in chat
5. All follow-ups treated uniformly: System reasons about context and decides response
6. Semantic search: pgvector cosine similarity (>0.92 threshold) on contextualized questions

**ADR 002 - Intelligent Routing (Phase 2):**
1. Router Agent: LLM-based routing with tool calling (search, get details, generate new)
2. Three response modes:
   - Mode 1 (EXACT_MATCH): Return existing claim card (~2s, similarity >= 0.92)
   - Mode 2 (CONTEXTUAL): Synthesize from existing cards (~5-10s, similarity 0.80-0.92)
   - Mode 3 (NOVEL_CLAIM): Full 5-agent pipeline (~45-60s, similarity < 0.80)
3. Two-layer architecture: Data integrity (audited claims) + Conversational (fast synthesis)
4. Router decisions logged for analytics and prompt tuning
5. Context Analyzer includes both user questions AND assistant responses for follow-ups

**ADR 003 - Auto-Blog System (Phase 3):**
1. Three distinct pages: Ask (chat), Read (blog articles), Audits (claim card repository)
2. Decomposer agent breaks topics into 3-12 component claims
3. Blog Composer generates synthesized prose articles (500-1500 words)
4. Two-layer deduplication: Scheduler (0.92), Auto-suggest (0.85)
5. Review workflow with selective re-run (decomposer/pipeline/composer)
6. Admin UI as standalone application (port 5174)

**ADR 004 - Multi-Source Verification (Phase 4):**
1. Six-tier API verification: Library reuse (Tier 0) → Books (Google Books) → Papers (Semantic Scholar/arXiv/PubMed) → Ancient texts (CCEL/Perseus) → Web (Tavily) → Fallback (LLM with transparency)
2. Verified Source Library (Tier 0): Reuse book metadata, semantic search + LLM relevance check, fresh quotes per claim
3. Source Checker uses APIs to access real source content (not LLM memory)
4. Adversarial Checker re-verifies quotes against actual sources
5. Verification metadata stored: method, status, content_type, url_verified
6. Prefer exact quotes from sources, paraphrase as fallback
7. Transparent about verification status in UI (not prominent but visible)
8. Allow unverified sources with clear disclaimer (transparency over failure)

---

## What NOT to Do

- Don't build features not explicitly requested
- Don't jump ahead to future phases
- Don't add "nice to have" features without asking
- Don't create files without discussing first
- Don't be verbose
- Don't auto-start services (no `&`, no `nohup`, no systemd in dev)

---

## Development Workflow

**Services (Dev Environment):**
- Python backend: `cd src/backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8008`
- React frontend: `cd src/frontend && npm run dev -- --host 0.0.0.0`
- **IMPORTANT:** Only the USER runs services manually in separate terminals
- Claude sessions develop/modify code only - NEVER start services
- User controls startup/shutdown
- All services bind to 0.0.0.0 (accessible on internal network)

**Database:**
- PostgreSQL on 192.168.50.10:5432 (same as Odin)
- New database: `thereceipts_dev`
- New user: `thereceipts` (password TBD during setup)
- Extensions: pgvector for semantic search

**Python Environment:**
- Use venv for dependency isolation (shared dev server)
- Python 3.12+

---

## Session Start

1. User tells you to read this file
2. User specifies exact task for session
3. Confirm scope before starting
4. Work incrementally
5. Update session file in `/docs/sessions/` as you go

---

## Known Issues

### None Currently

All critical bugs from Phase 2 have been resolved (as of 2026-01-16):
- ✓ Router Agent now loads system prompt and routes correctly
- ✓ Context Analyzer preserves assistant responses for follow-up questions
- ✓ Mode 1 (EXACT_MATCH) triggers for similar questions (similarity >= 0.92)
- ✓ Mode 2 (CONTEXTUAL) renders markdown and displays full source cards
- ✓ Semantic search limitations addressed via LLM-based Router Agent with tool calling (Phase 2.6)

See `/docs/sessions/2026-01-15-routing-bugs-fix.md` for details.
