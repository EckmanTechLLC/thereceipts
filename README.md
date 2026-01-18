# TheReceipts

**Forensic Claim Analysis for Christianity**

A religion claim-analysis platform that helps users in deconversion or questioning stages evaluate Christian apologetics claims through a transparent, multi-agent verification pipeline.

The system audits claims, not beliefs.

---

## Status

**Version:** 0.5.0 - Phase 4 Complete (Multi-Source Verification + Admin Enhancements)
**Started:** 2026-01-12
**Current Phase:** Production-Ready, Deployment Planning

---

## What Makes This Project Different?

- **No shortcuts** - Every claim runs through a 5-agent verification pipeline
- **Transparent auditing** - Users see exactly what was checked and how
- **Pre-vetted library** - Common claims answered instantly from audited database
- **The Elevator** - Simple by default, depth on demand (no assumed knowledge)
- **Fail fast** - No hedging, no "both sides," no apologetics
- **Source rigor** - Primary historical sources + peer-reviewed scholarship required

---

## Core Capabilities

### Public Features
1. **Home Page** - System introduction with live metrics and disclaimers
2. **Chat Mode** - Ask any question, get audited answers with intelligent routing
3. **Blog Mode** - Curated feed of auto-generated claim analyses
4. **Audit Repository** - Browse all verified claim cards by category
5. **Sources Page** - Explore all sources sorted by reference count with verification status

### Pipeline Features
6. **Multi-Agent Pipeline** - 5 sequential agents verify every claim
7. **Source Verification** - 6-tier API system verifies citations against real sources (Google Books, Semantic Scholar, CCEL, Perseus, Tavily)
8. **Semantic Search** - Reuse audited claims for instant responses
9. **Intelligent Router** - 3 response modes (exact match, contextual, novel generation)

### Admin Features
10. **Auto-Blog** - Scheduled claim generation with admin review
11. **Auto-Suggest** - Automatic web discovery of new apologetics claims via Tavily
12. **Admin Portal** - Manage queue, review failures, approve content
13. **Database Reset** - Clear test data while preserving configuration and verified sources

---

## Architecture

**Technology Stack:**
- **Backend:** Python + FastAPI (async LLM orchestration)
- **Frontend:** React (interactive UI, real-time WebSocket updates)
- **Database:** PostgreSQL + pgvector (semantic search + audit trails)
- **AI:** Anthropic + OpenAI (different LLMs per agent strength)

**5-Agent Pipeline:**
1. Topic Finder - Identifies claim + claimant + context
2. Source Checker - Verifies sources via 6-tier API system (Google Books, Semantic Scholar, CCEL, Perseus, Tavily)
3. Adversarial Checker - Attempts to falsify, re-verifies quotes against actual sources
4. Writing Agent - Produces forensic, accessible prose
5. Publisher - Adds audit summary + limitations + what would change verdict

**Design Pattern:**
Sequential agent pipeline with transparent audit trails. Chat mode uses semantic search of pre-audited claim library for instant answers, falling back to full pipeline generation for novel claims.

---

## Project Structure

```
/thereceipts
├── docs/                    # All documentation
│   ├── decisions/           # Architecture Decision Records (ADRs)
│   ├── sessions/            # Session notes from development
│   └── workflow/            # Development workflow documentation
├── src/                     # Source code
│   ├── backend/             # Python FastAPI application
│   │   ├── agents/          # 5-agent pipeline implementation
│   │   ├── api/             # REST endpoints
│   │   ├── database/        # Models, migrations, repositories
│   │   └── services/        # Business logic
│   └── frontend/            # React application
│       ├── components/      # UI components
│       ├── pages/           # Chat, Blog, Admin views
│       └── services/        # API clients, WebSocket
└── tests/                   # Test suites
```

---

## Documentation

- **[ADR 001: Core Architecture](docs/decisions/001-core-architecture-and-system-design.md)** - Foundation decisions
- **[ADR 002: Intelligent Routing](docs/decisions/002-intelligent-routing.md)** - Router Agent with tool calling
- **[ADR 003: Auto-Blog System](docs/decisions/003-auto-blog-system.md)** - Scheduled blog generation
- **[ADR 004: Multi-Source Verification](docs/decisions/004-multi-source-verification.md)** - API-based source verification
- **[Multi-Session Workflow](docs/workflow/multi-session-workflow.md)** - Development workflow guide
- **[DESCRIPTION.md](DESCRIPTION.md)** - Detailed project requirements
- **[CLAUDE.md](CLAUDE.md)** - Context file for Claude sessions

---

## Development Phases

### Planning (COMPLETE ✓)
- [x] Project structure
- [x] Initial documentation
- [x] Requirements definition (DESCRIPTION.md)
- [x] Architecture decisions (ADR 001)
- [x] Technology stack selection

### Phase 1: Foundation (COMPLETE ✓)
- [x] Database setup (schema, migrations, pgvector)
- [x] Python backend scaffold (FastAPI, venv, basic agents)
- [x] React frontend scaffold (routing, basic layout)
- [x] Agent pipeline orchestration
- [x] WebSocket real-time updates

### Phase 2: Conversational Chat (COMPLETE ✓)
- [x] Context analyzer with conversation history
- [x] Semantic search implementation (pgvector)
- [x] Full 5-agent pipeline integration
- [x] Chat interface with message thread
- [x] Claim card rendering with expandable sections
- [x] Real-time pipeline progress via WebSocket
- [x] Session-based conversation persistence
- [x] Error handling and validation
- [x] Intelligent routing with Router Agent (ADR 002)
- [x] Three response modes (exact match, contextual, novel claim)
- [x] Context preservation for follow-up questions

### Phase 3: Auto-Blog (COMPLETE ✓)
- [x] Topic queue system with priority and status tracking
- [x] Scheduled generation with APScheduler
- [x] Auto-suggest (LLM-based topic discovery)
- [x] Review interface with approve/reject/revision workflow
- [x] Read page (blog articles) and Audits page (claim card repository)
- [x] Decomposer and Blog Composer agents
- [x] Admin UI (standalone application on port 5174)

### Phase 4.1: Multi-Source Verification (COMPLETE ✓)
- [x] 4.1a: Core API Integration + Verified Source Library
  - [x] Tier 0: Verified source library (semantic search + LLM relevance check)
  - [x] Tier 1: Google Books API integration
  - [x] Tier 2: Semantic Scholar API integration
  - [x] Tier 4: Tavily API integration (web sources)
  - [x] Tier 5: LLM fallback with transparency
  - [x] Database migration (verified_sources table + source verification columns)
  - [x] SourceVerificationService with 6-tier system
- [x] 4.1b: Adversarial Re-Verification
  - [x] Integrated verification service into Adversarial Checker
  - [x] Quote comparison against actual API content
  - [x] URL validation and discrepancy flagging
  - [x] Reverification notes in agent_audit
- [x] 4.1c: Ancient Texts Integration (Tier 3)
  - [x] Perseus Digital Library integration
  - [x] CCEL (Christian Classics Ethereal Library) integration
  - [x] Ancient text sources added to verified source library
- [x] 4.1d: UI Transparency
  - [x] Verification badges in ClaimCard (✓/ⓘ/⚠)
  - [x] Verification method labels for each source
  - [x] Color-coded confidence indicators

### Phase 4.2: UI Enhancements (COMPLETE ✓)
- [x] Home page with metrics, disclaimers, and system introduction
- [x] Sources page (all sources sorted by reference count with filters)
- [x] Sticky navigation header (always visible during scroll)
- [x] Knowledge graph visualization (ReactFlow-based, currently hidden)

### Phase 4.3: Admin Enhancements (COMPLETE ✓)
- [x] Database reset feature (clear test data, preserve config + verified sources)
- [x] Auto-suggest web discovery (Tavily-based automatic topic discovery)
- [x] Intra-blog deduplication fix (prevents claims within same blog from being skipped)

### Future Enhancements (PLANNED)
- [ ] Agent prompt editor (edit system prompts and LLM config per agent via UI)
- [ ] Bulk topic import (CSV/JSON upload for topic queue)
- [ ] Knowledge graph public access (enable graph navigation link)

---

## Design Principles

1. **Claim-centric, not belief-centric** - Audit factual assertions, not theology
2. **The Elevator** - Simple by default, depth on demand
3. **Transparency over everything** - Show the audit process, not just results
4. **Fail fast** - No retries, no placeholders, no silent failures
5. **Source rigor** - Primary historical + peer-reviewed scholarship required
6. **Accessible language** - No assumed biblical/academic knowledge
7. **No shortcuts** - Every claim runs full 5-agent pipeline (or uses pre-audited cache)

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Python 3.12 + FastAPI | Async LLM orchestration, agent pipeline |
| Frontend | React + TypeScript | Interactive UI, real-time updates |
| Database | PostgreSQL + pgvector | Claim storage, semantic search, audit trails |
| AI | Anthropic + OpenAI | Multi-LLM agent pipeline |
| Deployment | venv, 0.0.0.0 binding | Isolated deps, network access |

---

## Getting Started

**Prerequisites:**
- Python 3.12+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension
- Anthropic API key (agent pipeline)
- OpenAI API key (embeddings + source verification)
- Google Books API key (source verification, optional)
- Tavily API key (source verification, optional)
- Semantic Scholar API key (source verification, optional)

### Backend Setup

1. **Create Python virtual environment:**
   ```bash
   cd src/backend
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   Create `.env` file in `src/backend/`:
   ```env
   POSTGRES_PASSWORD=your_db_password
   ANTHROPIC_API_KEY=your_anthropic_key
   OPENAI_API_KEY=your_openai_key
   GOOGLE_BOOKS_API_KEY=your_google_books_key  # Optional
   TAVILY_API_KEY=your_tavily_key              # Optional
   SEMANTIC_SCHOLAR_API_KEY=your_s2_key        # Optional
   ```

4. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Seed agent prompts:**
   ```bash
   python database/seeds/seed_agent_prompts.py
   ```

6. **Start backend server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8008
   ```

### Frontend Setup

1. **Install dependencies:**
   ```bash
   cd src/frontend
   npm install
   ```

2. **Start development server:**
   ```bash
   npm run dev -- --host 0.0.0.0
   ```

### Admin UI Setup

1. **Install dependencies:**
   ```bash
   cd src/admin
   npm install
   ```

2. **Start admin development server:**
   ```bash
   npm run dev -- --host 0.0.0.0 --port 5174
   ```

### Using the Application

**Public Frontend** (`http://localhost:5173`):

1. **Home Page:**
   - System overview and introduction
   - Live metrics (claims, blogs, questions answered)
   - AI disclaimer and terms of service

2. **Ask (Chat):**
   - Enter any question about Christian apologetics claims
   - Example: "Did Matthew write the Gospel of Matthew?"
   - System routes intelligently (instant, contextual, or full pipeline)
   - Watch real-time progress as agents work
   - Expand "Show Your Work" to see evidence and sources with verification badges

3. **Read (Blog):**
   - Browse published blog posts
   - Synthesized articles covering multiple related claims
   - Full source citations with verification status

4. **Audits (Repository):**
   - Browse all verified claim cards
   - Filter by category, verdict, confidence
   - Direct links to sources

5. **Sources:**
   - Explore all sources used across claims
   - Sorted by reference count
   - Filter by verification status and source type

**Admin UI** (`http://localhost:5174`):

1. **Topic Queue:**
   - View queued topics with priority
   - Trigger manual generation
   - Clear queue

2. **Review:**
   - Approve/reject generated blog posts
   - Request revisions (regenerate decomposer/pipeline/composer)
   - Preview before publishing

3. **Settings:**
   - Configure auto-suggest and scheduler
   - Trigger web discovery (finds new claims via Tavily)
   - Extract topics from text manually
   - Database reset (danger zone)

---

## Contributing

[To be determined]

---

## License

[To be determined]

---

**Last Updated:** 2026-01-18
