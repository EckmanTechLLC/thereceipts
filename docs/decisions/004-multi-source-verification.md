# ADR 004: Multi-Source Verification for Citations and Quotes

**Status:** Accepted
**Date:** 2026-01-16
**Deciders:** User + Claude
**Supersedes:** Extends ADR 001 (Source Checker and Adversarial Checker agents)

---

## Context

Phase 1-3 implementation revealed critical issues with source quality:

**Current Problems:**
- URLs are LLM-generated (often broken or point to wrong sources)
- Citations are from training data (may be incorrect or outdated)
- Quotes are paraphrased from memory (not from actual source text)
- Page numbers are unverified (often inaccurate)
- No way to verify claim against actual source content

**Impact on Mission:**
- Users can't trust sources (broken links damage credibility)
- Adversarial Checker can't verify quotes (no access to actual source text)
- Violates ADR 001 principle: "Every factual assertion must be sourced"
- System appears to hallucinate sources despite claim analysis rigor

**Current Workflow:**
1. Source Checker asks LLM: "Find sources for this claim"
2. LLM generates citations + quotes from training memory
3. URLs are guessed or hallucinated
4. Adversarial Checker attempts to verify but has no source access
5. Result: Unverifiable sources with broken links

**Gap:** No mechanism to access actual source content for verification.

---

## Decision: Multi-Tier Source Verification

Integrate external APIs to access real source content and verify citations before storing.

### Six-Tier Verification Strategy

Agents attempt each tier in order until source is found/verified:

**Tier 0 - Verified Source Library (Reuse):**
- Check internal library of previously verified sources
- Semantic search on claim keywords with 0.85 similarity threshold
- Returns 3-5 candidate sources from library
- LLM evaluates relevance: "Does this source address this specific claim context?"
- If relevant: Use verified book metadata + URL, but search within book for fresh quote
- If not relevant: Skip to Tier 1
- **Key:** Reuses book metadata (title, author, URL), NOT quotes or page numbers
- **Benefit:** Avoids redundant "does this book exist?" API calls
- **Safety:** LLM relevance check prevents forced matches
- **Result:** Fast source discovery, claim-specific quotes

**Library Contents:**
- Book metadata (title, author, publisher, date, ISBN)
- Verified URL (Google Books, Internet Archive, publisher site)
- Topic embeddings (for semantic search)
- Source type (book, paper, ancient text)
- NOT stored: Specific quotes or page numbers (those are claim-specific)

**Tier 1 - Books (Google Books API):**
- Search by title + author
- Retrieve book metadata (verified publisher, date, ISBN)
- Search within book for relevant keywords
- Extract actual snippets with page numbers
- Return: Verified citation + working link + actual quote text + page numbers

**Tier 2 - Academic Papers:**
- **Semantic Scholar API:** 200M+ papers with abstracts/full-text
- **arXiv API:** Preprints (math, physics, computer science)
- **PubMed Central API:** Open-access medical/biology papers
- Search by title + author or DOI
- Extract: Verified citation + abstract/full-text + working link

**Tier 3 - Ancient/Religious Texts:**
- **CCEL (Christian Classics Ethereal Library):** Early church fathers, theologians
- **Perseus Digital Library:** Ancient Greek/Latin texts
- **Early Church Texts:** Patristic writings, councils
- Search by work title + author/attribution
- Extract: Verified text + chapter/verse + working link

**Tier 4 - Web Sources (Tavily API):**
- General web search for citations
- Verify URL exists and matches citation
- Extract metadata (title, author, date)
- Return: Working link + content snippet

**Tier 5 - Fallback (LLM with transparency):**
- If all APIs fail to find source
- LLM generates from training memory
- Mark as "unverified" in database
- Display clear disclaimer in UI

---

## Integration Points

### Source Checker Agent (Modified)

**New Workflow:**
1. Identify required source types (book, paper, ancient text)
2. For each source:
   - Try Tier 0: Check verified source library (semantic search + LLM relevance check)
   - If library match: Use verified metadata, search within source for fresh quote
   - If no library match: Try Tier 1-4 APIs in order
   - If API returns verified source: Use actual content + add to library for future reuse
   - If all APIs fail: Fall back to LLM with "unverified" flag
3. Store sources with verification metadata

**Key Changes:**
- Checks verified source library first (Tier 0) before API calls
- Calls external APIs before generating sources
- Uses actual source text when available
- Adds verified sources to library for reuse
- Marks verification status for each source
- Prefers exact quotes from API results over paraphrases

### Adversarial Checker Agent (Modified)

**New Workflow:**
1. Receive claim card with sources
2. For each source:
   - Check library first (Tier 0) for verified metadata
   - Re-verify using same API tier system (if not in library)
   - Compare quote_text against actual source content
   - Verify context (surrounding text, not out of context)
   - Verify page numbers match quote location
3. Flag discrepancies or verification failures

**Key Changes:**
- Checks verified source library for fast lookups
- Actually reads source content (via APIs or library)
- Can verify quotes are accurate (not just plausible)
- Can verify quotes are not out of context
- Can verify page numbers are correct

---

## Verification Metadata

Each source stored with:
- **verification_method:** API used (google_books, semantic_scholar, ccel, tavily, llm_unverified)
- **verification_status:** verified, partially_verified, unverified
- **content_type:** exact_quote, verified_paraphrase, unverified_content
- **url_verified:** boolean (link tested and works)

**Preference Order:**
1. Exact quote from source (highest confidence)
2. Verified paraphrase (API access but no exact match)
3. Unverified content (LLM fallback, lowest confidence)

---

## API Selection Rationale

**Google Books API:**
- Best coverage for modern academic books
- Returns actual page snippets (not summaries)
- Free tier: 1,000 queries/day
- Paid tier available for scale

**Semantic Scholar API:**
- 200M+ papers indexed
- Open access abstracts + some full-text
- Free with generous rate limits
- Active maintenance by Allen Institute

**arXiv + PubMed:**
- Complements Semantic Scholar
- Full open-access content
- Free APIs with good documentation

**CCEL + Perseus:**
- Critical for Christianity claims (early church texts)
- Open access to ancient texts
- Free APIs

**Tavily API:**
- Backup for web-only sources
- URL verification when book/paper APIs fail
- Free tier: 1,000 queries/month
- Paid tier for scale

---

## Transparency and UI Display

**Verification status shown in claim card sources section:**

High confidence (verified):
```
📚 Bart D. Ehrman, Misquoting Jesus (HarperOne, 2005), pp. 10-11
   [View at Google Books] ✓ Quote verified from source
```

Medium confidence (partially verified):
```
📄 Raymond E. Brown, Introduction to the New Testament (1997)
   [View at Semantic Scholar] ✓ Citation verified, content paraphrased
```

Low confidence (unverified):
```
📖 William Lane Craig, Reasonable Faith (3rd ed., 2008)
   ⓘ Citation from AI training data (source not directly accessed)
```

**Principles:**
- Transparent about verification level
- Not hidden or buried in fine print
- But not alarmist or prominent warning
- Simple icons + brief explanation

---

## Performance Impact

**Current Pipeline:** ~45-60 seconds per claim card

**With Multi-Tier Verification:**
- Source Checker: +5-10s (API calls for 3-8 sources)
- Adversarial Checker: +5-10s (re-verification)
- **Total:** ~60-80 seconds per claim card

**Acceptable trade-off:** Higher confidence sources worth 15-20s additional time.

---

## Failure Handling

**If all API tiers fail for a source:**
- Do NOT fail the pipeline (contrary to strict "fail fast")
- Allow source with verification_status="unverified"
- Mark verification_method="llm_unverified"
- Display transparent disclaimer in UI

**Rationale:**
- Better to have claim card with some sources than no card
- Transparency about limitations aligns with project principles
- Users can evaluate confidence themselves
- Admin can manually verify later if needed

**Important:** System should genuinely attempt all tiers. Sources should NOT default to unverified without trying APIs first.

---

## Success Criteria

Phase 4.1 succeeds when:

1. **Source Checker integrated with APIs:**
   - Attempts all 5 tiers in order
   - Stores verification metadata
   - Uses actual source content when available
   - Prefers exact quotes over paraphrases

2. **Adversarial Checker verifies with APIs:**
   - Re-verifies quotes against actual source text
   - Checks context using surrounding content
   - Validates page numbers against source
   - Flags verification failures

3. **Verified source library functional:**
   - Library populated with verified sources after first use
   - Semantic search finds relevant library sources (0.85 threshold)
   - LLM relevance check prevents forced matches
   - Library reuse reduces API calls over time

4. **High verification rate:**
   - Target: >70% of sources verified via APIs/library (not unverified fallback)
   - Books: >80% verified via Google Books or library
   - Papers: >60% verified via Semantic Scholar/arXiv/PubMed
   - Ancient texts: >50% verified via CCEL/Perseus

5. **Working links:**
   - 100% of URLs tested and verified to exist
   - URLs point to correct sources (not wrong books/papers)

6. **Transparency in UI:**
   - Verification status displayed for each source
   - Icons/labels indicate confidence level
   - Clear but not alarmist

7. **Performance acceptable:**
   - Pipeline completes in 60-80s (was 45-60s)
   - Library hits reduce time (skip API calls)
   - No pipeline failures due to API rate limits

---

## Implementation Breakdown

### Phase 4.1a: Core API Integration + Library (Session 1-2)
- Create verified_sources table (library schema with embeddings)
- Install API client libraries (google-books, semantic-scholar, tavily)
- Create SourceVerificationService with 6-tier system (Tier 0 = library)
- Implement library semantic search and LLM relevance check
- Integrate into Source Checker agent
- Store verification metadata in sources table
- Add verified sources to library after API verification

### Phase 4.1b: Adversarial Re-Verification (Session 3)
- Integrate SourceVerificationService into Adversarial Checker
- Implement quote comparison logic
- Implement context verification
- Handle verification failures

### Phase 4.1c: Ancient Texts Integration (Session 4)
- Add CCEL API integration (Tier 3)
- Add Perseus Digital Library integration (Tier 3)
- Add Early Church Texts integration (Tier 3)

### Phase 4.1d: UI Transparency (Session 5)
- Add verification status to ClaimCard display
- Add icons/badges for confidence levels
- Test with verified vs unverified sources

---

## Consequences

### Benefits

- **Higher source credibility:** Working links to real sources
- **Verifiable quotes:** Adversarial Checker can actually read sources
- **Better citations:** Metadata verified via APIs
- **Transparent limitations:** Clear about what's verified vs unverified
- **Aligns with mission:** Rigorous sourcing matches rigorous claim analysis

### Trade-offs

- **Slower pipeline:** +15-20s per claim card (acceptable)
- **API dependencies:** External services can fail (fallback mitigates)
- **API costs:** Mostly free tiers, some paid at scale (acceptable)
- **Complexity:** More moving parts in agent pipeline (worthwhile)

### Risks

- **API rate limits:** Mitigated by free tier quotas (sufficient for current volume)
- **API downtime:** Mitigated by tier fallback system
- **Paywalled sources:** Some sources still inaccessible (accept limitation, be transparent)

---

## Non-Goals (Deferred)

**Manual verification workflow:**
- Admin flags sources for physical book verification
- Deferred to Phase 5 or later
- Not needed for Phase 4.1

**Automatic re-verification of existing claim cards:**
- Existing cards left as-is until DB cleared for production
- Not part of Phase 4.1 scope

**Full-text book access:**
- Google Books provides snippets, not full books
- Physical book access out of scope
- Accept limitation with transparency

---

## Related Enhancement: Database Reset Feature

**Problem:** During testing and development, need to clear out test data without destroying system configuration.

**Solution:** Admin "Clear Database" function (Phase 4.4 or later)

**What Gets Deleted:**
- All claim cards
- All blog posts
- All topics in queue
- All router decisions
- All sources (per-claim references)

**What Gets Preserved:**
- Agent prompts (system configuration)
- Category tags (system configuration)
- Apologetics tags (system configuration)
- **Verified sources library** (hard-won verified sources for future reuse)

**Admin UI:**
- Large prominent button in admin settings page
- Confirmation modal with warning text
- Requires typing "DELETE" to confirm (prevent accidents)
- Shows count of items to be deleted before confirmation

**Rationale for keeping verified sources library:**
- Library represents verified metadata that's reusable
- No claim-specific data (quotes/pages are in sources table, which gets deleted)
- Saves re-verification API calls when rebuilding claim cards
- Can be manually cleared if needed via direct database access

**Implementation:** Deferred to Phase 4.4 or 4.5 (after source verification complete)

---

## Open Questions (Resolved)

**Q: Should pipeline fail if all APIs fail?**
A: No - allow unverified sources with clear flag (transparency over failure)

**Q: Should Adversarial Checker re-verify?**
A: Yes - that's the entire point of the agent

**Q: Include ancient texts in Phase 4.1?**
A: Yes - critical for Christianity focus (CCEL, Perseus, Early Church Texts)

**Q: Performance impact acceptable?**
A: Yes - 60-80s total (was 45-60s) acceptable for quality improvement

---

**Status:** Ready for implementation (Phase 4.1).
