# Multi-Session Development Workflow

**Purpose:** Coordinate multiple Claude sessions for complex projects with proper context management and incremental delivery.

---

## Core Concept

**One foundation session** coordinates multiple **focused implementation sessions** that report back for verification before proceeding.

---

## Session Types

### 1. Foundation Session (Coordinator)
- Long-lived session that persists throughout project
- Reviews work from implementation sessions
- Verifies correctness and completeness
- Provides prompts for next sessions
- Maintains project context across phases

### 2. Implementation Sessions (Workers)
- Short-lived, focused on specific tasks
- Complete 1-3 related tasks per session
- Report results back to foundation session
- Session notes document what was done (~200-300 lines)

### 3. Planning Sessions (Architects)
- Create ADRs for major decisions
- Break phases into tasks with priorities
- Define database schemas, APIs, architectures
- Keep plans concise (~300 lines, not 2000)

---

## Project Structure

```
/docs/
  CLAUDE.md              # Persistent context (read by all sessions)
  /decisions/            # ADRs (001, 002, 003...)
  /sessions/             # Session notes (one per implementation session)
  /workflow/             # This doc
```

---

## CLAUDE.md Format

```markdown
# Project Context for Claude

## User Preferences (Apply Always)
- Never verbose - clear, concise responses
- Small incremental changes
- Ask before expanding scope
- Document as you go

## Current Status
[Phase completion status, active work]

## Key Decisions
[Link to ADRs]

## What NOT to Do
[Clear boundaries]

## Development Workflow
[Service management, testing approach]

## Known Issues
[Track blockers]
```

---

## Workflow Steps

### Phase Planning
1. Foundation session creates planning session
2. Planning session reads full docs, creates ADR with task breakdown
3. Foundation verifies plan alignment with vision
4. Break into 4-6 implementation sessions

### Implementation Loop
1. **Foundation:** Provides session name and detailed prompt
2. **User:** Starts implementation session with prompt
3. **Implementation:** Completes tasks, updates session notes, updates CLAUDE.md
4. **Implementation:** Reports summary back to user
5. **User:** Pastes summary to foundation session
6. **Foundation:** Verifies work (reads key files)
7. **Foundation:** Provides next session prompt
8. **Repeat** until phase complete

---

## Prompt Template

```
Read /home/path/to/project/CLAUDE.md first.

IMPORTANT: Be concise. Session notes ~200-300 lines max.

Implement [Phase X Task Y]: [Task Name]

Reference:
- /docs/sessions/planning-session.md
- /docs/sessions/previous-task.md

Scope:
[Specific files and what to implement]

Update session note in /docs/sessions/
```

---

## Benefits

✓ **Context management:** Foundation maintains big picture, workers focus on tasks
✓ **Quality gates:** Foundation verifies before proceeding
✓ **Incremental delivery:** Small sessions = quick iterations
✓ **Documentation:** Session notes create audit trail
✓ **Recovery:** Can resume at any session boundary
✓ **Conciseness:** Explicit limits prevent over-documentation

---

## Anti-Patterns (Avoid)

✗ Single mega-session trying to do everything
✗ No verification between tasks
✗ Verbose documentation (2000+ line planning docs)
✗ Implementation sessions that start planning from scratch
✗ Skipping CLAUDE.md updates
✗ Vague prompts without specific file paths

---

## Example Session Flow

```
foundation: Creates planning session for Phase 4B
  ↓
planning: Creates ADR 004 with 9 tasks
  ↓
foundation: Verifies, provides session prompt for 4B.1
  ↓
implementation-4B1: Database + entities + events
  ↓
foundation: Verifies, provides prompt for 4B.2
  ↓
implementation-4B2: Task decomposition service
  ↓
foundation: Verifies, provides prompt for 4B.3
  ↓
... continue through all tasks
```

---

## Key Success Factors

1. **Foundation session longevity:** Keep it alive across entire phase/project
2. **Clear boundaries:** One session = one clear scope
3. **Explicit verification:** Foundation reads actual files, not just summaries
4. **Concise prompts:** Specific files, clear scope, no ambiguity
5. **Regular updates:** Keep CLAUDE.md current after each session
6. **Session notes discipline:** ~200-300 lines, template-based

---

**Use this workflow when:**
- Project spans multiple phases (4+ weeks)
- Complex architecture needs coordination
- Multiple components must integrate cleanly
- Quality gates are important
- Context management is critical
