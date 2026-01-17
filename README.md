# TheReceipts

**Forensic Claim Analysis for Christianity**

A religion claim-analysis platform that helps users in deconversion or questioning stages evaluate Christian apologetics claims through a transparent, multi-agent verification pipeline.

The system audits claims, not beliefs.

---

## Status

**Version:** 0.3.0 - Phase 3 (Auto-Blog) Complete
**Started:** 2026-01-12
**Current Phase:** Testing Phase 3, Planning Phase 4 (Admin Enhancements)

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

1. **Chat Mode** - Ask any question, get audited answers
2. **Blog Mode** - Curated feed of auto-generated claim analyses
3. **Multi-Agent Pipeline** - 5 sequential agents verify every claim
4. **Semantic Search** - Reuse audited claims for instant responses
5. **Auto-Blog** - Scheduled claim generation with admin review
6. **Auto-Suggest** - LLM + web search discovers new apologetics claims
7. **Admin Portal** - Manage queue, edit prompts, review failures

---

## Architecture

**Technology Stack:**
- **Backend:** Python + FastAPI (async LLM orchestration)
- **Frontend:** React (interactive UI, real-time WebSocket updates)
- **Database:** PostgreSQL + pgvector (semantic search + audit trails)
- **AI:** Anthropic + OpenAI (different LLMs per agent strength)

**5-Agent Pipeline:**
1. Topic Finder - Identifies claim + claimant + context
2. Source Checker - Gathers primary historical + scholarly sources
3. Adversarial Checker - Attempts to falsify, verifies quotes
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

### Phase 4: Source Verification & Admin Enhancements (NOT STARTED)
- [ ] Multi-source verification (6-tier API integration)
  - [ ] Verified source library (Tier 0: reuse verified book metadata with fresh quotes)
  - [ ] Google Books API (books with page-verified snippets)
  - [ ] Semantic Scholar/arXiv/PubMed APIs (academic papers)
  - [ ] CCEL/Perseus/Early Church Texts (ancient texts)
  - [ ] Tavily API (web sources, URL verification)
  - [ ] Adversarial Checker re-verification with actual sources
  - [ ] UI transparency for verification status
- [ ] Agent prompt editor (edit system prompts and LLM config per agent)
- [ ] Bulk topic import (CSV/JSON upload)
- [ ] Database reset feature (clear test data, preserve config + verified sources)

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
- Anthropic API key
- OpenAI API key

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

### Using the Application

1. **Open browser:** Navigate to `http://localhost:5173` (or your network IP)

2. **Ask page (Chat):**
   - Enter any question about Christian apologetics claims
   - Example: "Did Matthew write the Gospel of Matthew?"
   - System will search existing claim cards or generate new analysis via 5-agent pipeline
   - Watch real-time progress as agents work
   - Expand "Show Your Work" to see detailed evidence and sources

3. **Keyboard shortcuts:**
   - `Enter` - Send message
   - `Esc` - Clear input or dismiss error

4. **Features:**
   - Conversation context preserved across page refresh (until tab closes)
   - Error handling with user-friendly messages
   - Character count when approaching limit (2000 chars)
   - Clear conversation button

---

## Contributing

[To be determined]

---

## License

[To be determined]

---

**Last Updated:** 2026-01-13
