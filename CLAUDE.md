# TheReceipts Context for Claude

**Purpose:** Development guide and rules for Claude implementation sessions.

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
