"""
Source Checker Agent for TheReceipts pipeline.

Second agent in the pipeline. Collects:
- Primary historical sources (ancient texts, manuscripts, councils)
- Scholarly peer-reviewed sources (academic consensus)

Phase 4.1: Enhanced with SourceVerificationService for API-verified sources.
"""

import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, AgentExecutionError, extract_json_from_response
from services.source_verification import SourceVerificationService, SourceVerificationResult
from database.repositories import VerifiedSourceRepository
from config import settings


class SourceCheckerAgent(BaseAgent):
    """
    Agent that researches and validates sources for the claim.

    Takes claim identification from TopicFinderAgent and collects:
    - Primary historical sources
    - Scholarly peer-reviewed sources
    - Relevant quotes and citations

    Phase 4.1: Uses SourceVerificationService to verify sources via APIs before storing.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize SourceCheckerAgent."""
        super().__init__(agent_name="source_checker", db_session=db_session)

        # Initialize verification service (Phase 4.1)
        verified_source_repo = VerifiedSourceRepository(db_session)
        self.verification_service = SourceVerificationService(
            verified_source_repo=verified_source_repo,
            openai_api_key=settings.OPENAI_API_KEY,
            google_books_api_key=settings.GOOGLE_BOOKS_API_KEY,
            tavily_api_key=settings.TAVILY_API_KEY,
            semantic_scholar_api_key=settings.SEMANTIC_SCHOLAR_API_KEY
        )

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Research and collect sources for the claim.

        Phase 4.1: Enhanced with multi-tier source verification.

        Args:
            input_data: Dict containing:
                - claim: The claim to research
                - claimant: Who made the claim
                - claim_type: Type of claim
                - context: Why it matters

        Returns:
            Dict containing:
                - primary_sources: List of primary historical sources (with verification metadata)
                - scholarly_sources: List of scholarly peer-reviewed sources (with verification metadata)
                - evidence_summary: Brief summary of what sources show
                - raw_response: Full LLM response

        Raises:
            AgentExecutionError: If execution fails or output cannot be parsed
        """
        claim = input_data.get("claim_text", "")
        claimant = input_data.get("claimant", "")
        claim_type = input_data.get("claim_type", "")

        if not claim:
            raise AgentExecutionError("No claim provided to SourceCheckerAgent")

        # Phase 4.1: Two-step process
        # Step 1: Identify required sources (what to look for)
        # Step 2: Verify each source via API tiers

        # Step 1: Ask LLM to identify source queries
        source_queries = await self._identify_source_queries(claim, claimant, claim_type)

        # Step 2: Verify sources via multi-tier system
        primary_sources = []
        scholarly_sources = []

        for query in source_queries.get("primary_source_queries", []):
            result = await self.verification_service.verify_source(
                claim_text=claim,
                source_query=query["search_query"],
                source_type="primary historical"
            )
            primary_sources.append(self._format_source_result(result, query))

        for query in source_queries.get("scholarly_source_queries", []):
            result = await self.verification_service.verify_source(
                claim_text=claim,
                source_query=query["search_query"],
                source_type="scholarly peer-reviewed"
            )
            scholarly_sources.append(self._format_source_result(result, query))

        # Generate evidence summary via LLM
        evidence_summary = await self._generate_evidence_summary(
            claim, primary_sources, scholarly_sources
        )

        return {
            "primary_sources": primary_sources,
            "scholarly_sources": scholarly_sources,
            "evidence_summary": evidence_summary,
            "raw_response": json.dumps(source_queries),
            "usage": {"phase": "4.1"},
        }

    async def _identify_source_queries(
        self,
        claim: str,
        claimant: str,
        claim_type: str
    ) -> Dict[str, Any]:
        """
        Ask LLM to identify what sources are needed for this claim.

        Args:
            claim: The claim text
            claimant: Who made the claim
            claim_type: Type of claim

        Returns:
            Dict with source queries to verify
        """
        user_message = f"""
Identify sources needed to evaluate this claim:

Claim: {claim}
Claimant: {claimant}
Claim Type: {claim_type}

For each source, provide a search query that could be used to find it.

Respond with valid JSON:
{{
  "primary_source_queries": [
    {{
      "search_query": "Title Author keywords",
      "usage_context": "How this source is used"
    }}
  ],
  "scholarly_source_queries": [
    {{
      "search_query": "Title Author keywords",
      "usage_context": "How this source supports analysis"
    }}
  ]
}}

Guidelines:
- Primary sources: Original texts, manuscripts, historical documents
- Scholarly sources: Peer-reviewed academic work, not apologetics
- Search queries should be specific (e.g., "Gospel of John Greek manuscripts" or "Bart Ehrman Misquoting Jesus")
- Provide 2-5 primary sources and 2-5 scholarly sources
"""

        try:
            response = await self.call_llm(user_message)
            raw_content = response["content"]

            content = extract_json_from_response(raw_content)
            parsed = json.loads(content)

            return parsed

        except Exception as e:
            # Fallback: Return empty queries
            print(f"Failed to identify source queries: {e}")
            return {
                "primary_source_queries": [],
                "scholarly_source_queries": []
            }

    def _format_source_result(
        self,
        result: SourceVerificationResult,
        query: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Format verification result for pipeline output.

        Args:
            result: SourceVerificationResult from verification service
            query: Original source query dict

        Returns:
            Formatted source dict with verification metadata
        """
        return {
            "citation": result.citation,
            "quote": result.quote_text or "",
            "url": result.url,
            "usage_context": query.get("usage_context", ""),
            # Phase 4.1: Verification metadata
            "verification_method": result.verification_method,
            "verification_status": result.verification_status,
            "content_type": result.content_type,
            "url_verified": result.url_verified,
        }

    async def _generate_evidence_summary(
        self,
        claim: str,
        primary_sources: List[Dict[str, Any]],
        scholarly_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Generate brief summary of what the evidence shows.

        Args:
            claim: The claim text
            primary_sources: List of primary source dicts
            scholarly_sources: List of scholarly source dicts

        Returns:
            Brief evidence summary (2-3 sentences)
        """
        sources_text = "Primary sources:\n"
        for src in primary_sources:
            sources_text += f"- {src['citation']}: {src['quote'][:200] if src['quote'] else 'N/A'}\n"

        sources_text += "\nScholarly sources:\n"
        for src in scholarly_sources:
            sources_text += f"- {src['citation']}: {src['quote'][:200] if src['quote'] else 'N/A'}\n"

        user_message = f"""
Based on these sources, provide a brief summary (2-3 sentences) of what the evidence shows about this claim:

Claim: {claim}

{sources_text}

Summary:"""

        try:
            response = await self.call_llm(user_message)
            return response["content"].strip()
        except Exception as e:
            return "Unable to generate evidence summary."
