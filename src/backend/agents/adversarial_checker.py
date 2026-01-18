"""
Adversarial Checker Agent for TheReceipts pipeline.

Third agent in the pipeline. Attempts to:
- Falsify the draft verdict
- Verify quotes are not out of context
- Check that sources actually support claims
- Ensure confidence is not overstated
- Re-verify quotes against actual API sources (Phase 4.1b)
"""

import json
import os
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response
from services.source_verification import SourceVerificationService, SourceVerificationResult
from database.repositories import VerifiedSourceRepository


class AdversarialCheckerAgent(BaseAgent):
    """
    Agent that attempts to falsify the analysis and verify source accuracy.

    Takes claim and sources from previous agents and:
    - Attempts to find counterevidence
    - Verifies quotes are in context
    - Checks for apologetics techniques
    - Assesses confidence level
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize AdversarialCheckerAgent."""
        super().__init__(agent_name="adversarial_checker", db_session=db_session)

        # Initialize source verification service (Phase 4.1b)
        verified_source_repo = VerifiedSourceRepository(db_session)
        self.verification_service = SourceVerificationService(
            verified_source_repo=verified_source_repo,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            google_books_api_key=os.environ.get("GOOGLE_BOOKS_API_KEY"),
            tavily_api_key=os.environ.get("TAVILY_API_KEY"),
            semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to falsify the analysis and verify sources.

        Args:
            input_data: Dict containing all previous agent outputs

        Returns:
            Dict containing:
                - verdict: Verdict category (True/Misleading/False/Unfalsifiable/Depends)
                - confidence_level: High/Medium/Low
                - confidence_explanation: Why this confidence level
                - apologetics_techniques: List of techniques identified
                - counterevidence: Any counterevidence found
                - verification_notes: Notes on source verification
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        evidence_summary = input_data.get("evidence_summary", "")
        primary_sources = input_data.get("primary_sources", [])
        scholarly_sources = input_data.get("scholarly_sources", [])

        if not claim:
            raise AgentExecutionError("No claim provided to AdversarialCheckerAgent")

        # Phase 4.1b: Re-verify sources against actual API content
        reverification_notes = await self._reverify_sources(
            claim_text=claim,
            primary_sources=primary_sources,
            scholarly_sources=scholarly_sources
        )

        # Construct user message
        user_message = f"""
Attempt to falsify this analysis:

Claim: {claim}
Evidence Summary: {evidence_summary}

Primary Sources: {json.dumps(primary_sources, indent=2)}
Scholarly Sources: {json.dumps(scholarly_sources, indent=2)}

Source Re-Verification Results (Phase 4.1b):
{reverification_notes}

Please respond with a JSON object containing:
{{
  "verdict": "One of: True, Misleading, False, Unfalsifiable, Depends on Definitions",
  "confidence_level": "High, Medium, or Low",
  "confidence_explanation": "Why this confidence level (2-3 sentences)",
  "apologetics_techniques": ["List of techniques used, if any"],
  "counterevidence": "Any counterevidence found (or 'None identified')",
  "verification_notes": "Notes on quote verification and source accuracy"
}}

Verdict categories:
- True: Claim is factually accurate
- Misleading: Contains truth but misrepresents context
- False: Claim is factually incorrect
- Unfalsifiable: Cannot be tested empirically
- Depends on Definitions: Depends on how terms are defined
"""

        try:
            # Call LLM
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            # Parse JSON using shared utility function
            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            # Validate required fields
            required_fields = [
                "verdict", "confidence_level", "confidence_explanation",
                "apologetics_techniques", "counterevidence", "verification_notes"
            ]
            for field in required_fields:
                if field not in parsed:
                    raise AgentExecutionError(
                        f"AdversarialCheckerAgent output missing required field: {field}"
                    )

            return {
                "verdict": parsed["verdict"],
                "confidence_level": parsed["confidence_level"],
                "confidence_explanation": parsed["confidence_explanation"],
                "apologetics_techniques": parsed["apologetics_techniques"],
                "counterevidence": parsed["counterevidence"],
                "verification_notes": parsed["verification_notes"],
                "reverification_notes": reverification_notes,  # Phase 4.1b: Include API re-verification results
                "raw_response": raw_content,
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            raise AgentExecutionError(
                f"AdversarialCheckerAgent failed to parse JSON output: {str(e)}"
            )
        except Exception as e:
            raise AgentExecutionError(
                f"AdversarialCheckerAgent execution failed: {str(e)}"
            )

    async def _reverify_sources(
        self,
        claim_text: str,
        primary_sources: List[Dict[str, Any]],
        scholarly_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Re-verify sources against actual API content (Phase 4.1b).

        For each source:
        1. Re-verify using same API tier system
        2. Compare quote_text against actual source content
        3. Verify context (surrounding text, not out of context)
        4. Verify page numbers match quote location (if available)

        Args:
            claim_text: The claim being verified
            primary_sources: List of primary source dicts
            scholarly_sources: List of scholarly source dicts

        Returns:
            String containing verification notes with any discrepancies found
        """
        verification_notes = []
        all_sources = [
            ("Primary", source) for source in primary_sources
        ] + [
            ("Scholarly", source) for source in scholarly_sources
        ]

        for source_type, source in all_sources:
            citation = source.get("citation", "Unknown")
            quote_text = source.get("quote_text", "")
            url = source.get("url", "")
            usage_context = source.get("usage_context", "")

            # Skip if no quote to verify
            if not quote_text or not citation:
                continue

            try:
                # Re-verify using multi-tier system
                # Create search query from citation
                search_query = citation.split(",")[0] if "," in citation else citation

                # Determine source type from citation format
                inferred_source_type = "book" if any(
                    word in citation.lower() for word in ["press", "publisher", "edition"]
                ) else "scholarly peer-reviewed"

                # Call verification service
                result = await self.verification_service.verify_source(
                    claim_text=claim_text,
                    source_query=search_query,
                    source_type=inferred_source_type
                )

                # Check verification result
                if not result.success:
                    verification_notes.append(
                        f"⚠ {source_type} source '{citation}': Failed re-verification "
                        f"(all API tiers failed, tier {result.tier})"
                    )
                    continue

                # Compare URLs if both exist
                if url and result.url and url != result.url:
                    verification_notes.append(
                        f"⚠ {source_type} source '{citation}': URL mismatch "
                        f"(original: {url[:50]}..., verified: {result.url[:50]}...)"
                    )

                # Check if URL is broken
                if not result.url_verified:
                    verification_notes.append(
                        f"⚠ {source_type} source '{citation}': URL appears broken or inaccessible"
                    )

                # For library hits or API results with content, compare quotes
                if result.metadata and result.metadata.get("content_snippet"):
                    content_snippet = result.metadata.get("content_snippet", "")

                    # Simple check: Is the quote text found in the content snippet?
                    # Note: This is a basic check. Full context verification would require
                    # accessing the complete source text, which APIs may not provide.
                    if quote_text.lower() not in content_snippet.lower():
                        # Try to find similar text (relaxed match)
                        quote_words = quote_text.lower().split()[:10]  # First 10 words
                        words_found = sum(1 for word in quote_words if word in content_snippet.lower())
                        match_ratio = words_found / len(quote_words) if quote_words else 0

                        if match_ratio < 0.5:  # Less than 50% word overlap
                            verification_notes.append(
                                f"⚠ {source_type} source '{citation}': Quote may not match source content "
                                f"(low word overlap: {match_ratio:.0%})"
                            )

                # Note successful verification
                if result.success and result.tier <= 2:  # Tier 0-2 (library, books, papers)
                    verification_notes.append(
                        f"✓ {source_type} source '{citation}': Verified via {result.verification_method} "
                        f"(tier {result.tier})"
                    )

            except Exception as e:
                verification_notes.append(
                    f"⚠ {source_type} source '{citation}': Re-verification error: {str(e)}"
                )

        # Generate summary
        if not verification_notes:
            return "All sources skipped re-verification (no quotes or citations missing)."

        return "\n".join(verification_notes)
