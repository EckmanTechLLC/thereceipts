## Project Description (for Claude Code)

### Goal
Build a religion claim–analysis platform focused on Christianity that helps users weed out false, misleading, or dishonest claims made by Christian authors, apologists, and organizations.

This system is not for courts, schools, or activism.
It is for individual users in deconversion or questioning stages who want fast, accurate, sourced answers.

---

## Core Concept
The system audits claims, not beliefs.

Users can:
- ask direct questions (chat mode)
- read published analyses (blog mode)

Both are powered by the same backend: Claim Cards generated and verified by a transparent multi-agent pipeline.

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

## Multi-Agent Pipeline (required)
All content must pass through these agents in order:

1. Topic Finder Agent
- Identifies:
	- common apologetics claims
	- claims made by known Christian authors
	- frequent deconversion questions
- Outputs: claim + claimant + why it matters

2. Source Checker Agent
- Collects:
	- primary historical sources
	- strongest scholarly consensus
- Disallows:
	- single-source dependence
	- blog-only citations
	- quote fragments without context

3. Adversarial Checker Agent
- Attempts to falsify the draft
- Verifies:
	- quotes are not out of context
	- sources actually support claims
	- confidence is not overstated

4. Writing Agent
- Produces final prose:
	- calm, direct, forensic tone
	- no mocking
	- no rhetorical preaching
	- accessible to non-academics

5. Transparency / Publisher Agent
- Publishes:
	- final content
	- summary of what was checked
	- known limitations
	- what evidence would change the verdict

---

## Data Model (minimum)
Each Claim Card stores:
- claimText
- claimant (author / org)
- claimType (history, science, doctrine, translation, etc.)
- verdict
- shortAnswer
- deepAnswer
- primarySources[]
- scholarlySources[]
- apologeticsTags[]
- confidenceLevel
- agentAuditSummary

Blog posts = curated Claim Cards.
Chat answers = single Claim Card rendered conversationally.

---

## UI Expectations (high-level)
- Chat interface for questions
- Blog/archive view of Claim Cards
- Expandable “Show Your Work” sections
- Receipts panel for sources
- Confidence indicator
- No gamification, no social metrics

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
