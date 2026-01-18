"""
Source Verification Service for Phase 4.1: Multi-Tier Source Verification.

Implements 6-tier verification system (Tier 0-5):
- Tier 0: Verified Source Library (semantic search + LLM relevance check)
- Tier 1: Google Books API
- Tier 2: Semantic Scholar API (academic papers)
- Tier 3: Ancient Texts (Perseus CTS API, CCEL)
- Tier 4: Tavily API (web sources)
- Tier 5: LLM fallback (unverified)
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import httpx
from openai import AsyncOpenAI
from googleapiclient.discovery import build
from tavily import TavilyClient

from database.models import VerifiedSource
from database.repositories import VerifiedSourceRepository


class SourceVerificationResult:
    """Result of source verification attempt."""

    def __init__(
        self,
        success: bool,
        tier: int,
        verification_method: str,
        verification_status: str,
        citation: str,
        url: str,
        quote_text: Optional[str] = None,
        content_type: str = "unverified_content",
        url_verified: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.tier = tier
        self.verification_method = verification_method
        self.verification_status = verification_status
        self.citation = citation
        self.url = url
        self.quote_text = quote_text
        self.content_type = content_type
        self.url_verified = url_verified
        self.metadata = metadata or {}


class SourceVerificationService:
    """
    Multi-tier source verification service.

    Attempts each tier in order until source is verified:
    1. Tier 0: Check verified source library (semantic search + LLM relevance)
    2. Tier 1: Google Books API
    3. Tier 2: Semantic Scholar API
    4. Tier 3: Ancient Texts (Perseus CTS API, CCEL)
    5. Tier 4: Tavily API (web sources)
    6. Tier 5: LLM fallback (unverified)
    """

    def __init__(
        self,
        verified_source_repo: VerifiedSourceRepository,
        openai_api_key: Optional[str] = None,
        google_books_api_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        semantic_scholar_api_key: Optional[str] = None
    ):
        self.verified_source_repo = verified_source_repo

        # Store API keys
        self.google_books_api_key = google_books_api_key
        self.tavily_api_key = tavily_api_key
        self.semantic_scholar_api_key = semantic_scholar_api_key

        # Initialize OpenAI client for embeddings and LLM relevance checks
        self.openai_client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None

        # Initialize Tavily client
        if self.tavily_api_key:
            self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
        else:
            self.tavily_client = None

    async def verify_source(
        self,
        claim_text: str,
        source_query: str,
        source_type: str = "scholarly peer-reviewed"
    ) -> SourceVerificationResult:
        """
        Verify a source through multi-tier system.

        Args:
            claim_text: The claim being sourced
            source_query: Search query for source (title, author, topic keywords)
            source_type: Type of source needed (book, paper, etc.)

        Returns:
            SourceVerificationResult with verification details
        """
        # Tier 0: Check verified source library
        library_result = await self._check_library(claim_text, source_query)
        if library_result:
            return library_result

        # Tier 1: Google Books API (if source_type suggests book)
        if "book" in source_type.lower() or "historical" in source_type.lower():
            books_result = await self._check_google_books(source_query)
            if books_result:
                # Add to library for future reuse
                await self._add_to_library(books_result)
                return books_result

        # Tier 2: Semantic Scholar API (academic papers)
        if "scholarly" in source_type.lower() or "peer-reviewed" in source_type.lower():
            scholar_result = await self._check_semantic_scholar(source_query)
            if scholar_result:
                # Add to library for future reuse
                await self._add_to_library(scholar_result)
                return scholar_result

        # Tier 3: Ancient/Religious Texts (Perseus, CCEL)
        if "ancient" in source_type.lower() or "religious" in source_type.lower() or "patristic" in source_type.lower():
            ancient_result = await self._check_ancient_texts(source_query)
            if ancient_result:
                # Add to library for future reuse
                await self._add_to_library(ancient_result)
                return ancient_result

        # Tier 4: Tavily API (web sources)
        tavily_result = await self._check_tavily(source_query)
        if tavily_result:
            return tavily_result

        # Tier 5: LLM fallback (unverified)
        return await self._llm_fallback(claim_text, source_query, source_type)

    async def _check_library(
        self,
        claim_text: str,
        source_query: str
    ) -> Optional[SourceVerificationResult]:
        """
        Tier 0: Check verified source library with semantic search + LLM relevance check.

        Args:
            claim_text: The claim being sourced
            source_query: Search query for source

        Returns:
            SourceVerificationResult if relevant library source found, None otherwise
        """
        if not self.openai_client:
            return None

        # Generate embedding for claim + source query
        query_text = f"{claim_text} {source_query}"
        embedding_response = await self.openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=query_text
        )
        embedding = embedding_response.data[0].embedding

        # Semantic search in library (0.85 threshold per ADR 004)
        candidates = await self.verified_source_repo.search_by_similarity(
            embedding=embedding,
            similarity_threshold=0.85,
            limit=3
        )

        if not candidates:
            return None

        # LLM relevance check: Does this source address this specific claim?
        for verified_source, similarity in candidates:
            is_relevant = await self._llm_relevance_check(
                claim_text=claim_text,
                source_title=verified_source.title,
                source_author=verified_source.author,
                source_snippet=verified_source.content_snippet or ""
            )

            if is_relevant:
                # Library hit! Reuse verified metadata, but quote must be claim-specific
                return SourceVerificationResult(
                    success=True,
                    tier=0,
                    verification_method=f"library_reuse_{verified_source.verification_method}",
                    verification_status="verified",
                    citation=f"{verified_source.author}, {verified_source.title}",
                    url=verified_source.url,
                    quote_text=None,  # Quote will be generated by Source Checker
                    content_type="exact_quote",  # Assumes Source Checker will extract quote
                    url_verified=True,
                    metadata={
                        "library_source_id": str(verified_source.id),
                        "similarity": similarity,
                        "publisher": verified_source.publisher,
                        "publication_date": verified_source.publication_date,
                        "isbn": verified_source.isbn,
                        "doi": verified_source.doi
                    }
                )

        return None

    async def _llm_relevance_check(
        self,
        claim_text: str,
        source_title: str,
        source_author: str,
        source_snippet: str
    ) -> bool:
        """
        Use LLM to check if library source is relevant to specific claim.

        Args:
            claim_text: The claim being sourced
            source_title: Title of candidate source
            source_author: Author of candidate source
            source_snippet: Sample content from source

        Returns:
            True if source is relevant, False otherwise
        """
        if not self.openai_client:
            return False

        prompt = f"""You are evaluating whether a source from our verified library is relevant to a specific claim.

Claim: {claim_text}

Library Source:
- Author: {source_author}
- Title: {source_title}
- Sample Content: {source_snippet[:500] if source_snippet else "N/A"}

Question: Does this source directly address or provide evidence for evaluating this specific claim?

Respond with ONLY "YES" or "NO".
"""

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )

        answer = response.choices[0].message.content.strip().upper()
        return "YES" in answer

    async def _check_google_books(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Tier 1: Check Google Books API for book sources.

        Args:
            source_query: Search query (title + author)

        Returns:
            SourceVerificationResult if book found, None otherwise
        """
        if not self.google_books_api_key:
            return None

        try:
            service = build('books', 'v1', developerKey=self.google_books_api_key)
            result = service.volumes().list(q=source_query, maxResults=1).execute()

            if 'items' not in result or len(result['items']) == 0:
                return None

            volume = result['items'][0]['volumeInfo']
            title = volume.get('title', 'Unknown Title')
            authors = volume.get('authors', ['Unknown Author'])
            publisher = volume.get('publisher', None)
            published_date = volume.get('publishedDate', None)

            # Get ISBN if available
            isbn = None
            if 'industryIdentifiers' in volume:
                for identifier in volume['industryIdentifiers']:
                    if identifier['type'] in ['ISBN_13', 'ISBN_10']:
                        isbn = identifier['identifier']
                        break

            # Get preview link or info link
            url = volume.get('previewLink') or volume.get('infoLink', '')

            # Get content snippet
            content_snippet = volume.get('description', '')

            # Verify URL exists
            url_verified = await self._verify_url(url)

            return SourceVerificationResult(
                success=True,
                tier=1,
                verification_method="google_books",
                verification_status="verified",
                citation=f"{', '.join(authors)}, {title} ({publisher}, {published_date})" if publisher else f"{', '.join(authors)}, {title}",
                url=url,
                quote_text=None,  # Will be extracted by Source Checker from book content
                content_type="exact_quote",
                url_verified=url_verified,
                metadata={
                    "title": title,
                    "author": ', '.join(authors),
                    "publisher": publisher,
                    "publication_date": published_date,
                    "isbn": isbn,
                    "content_snippet": content_snippet,
                    "source_type": "book"
                }
            )

        except Exception as e:
            print(f"Google Books API error: {e}")
            return None

    async def _check_semantic_scholar(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Tier 2: Check Semantic Scholar API for academic papers.

        Args:
            source_query: Search query (title + author or topic)

        Returns:
            SourceVerificationResult if paper found, None otherwise
        """
        try:
            # Semantic Scholar public API endpoint
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": source_query,
                "limit": 1,
                "fields": "title,authors,year,abstract,url,externalIds,venue,publicationTypes"
            }

            headers = {}
            if self.semantic_scholar_api_key:
                headers["x-api-key"] = self.semantic_scholar_api_key

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=10.0)

                if response.status_code != 200:
                    return None

                data = response.json()
                if 'data' not in data or len(data['data']) == 0:
                    return None

                paper = data['data'][0]
                title = paper.get('title', 'Unknown Title')
                authors = [author.get('name', 'Unknown') for author in paper.get('authors', [])]
                year = paper.get('year', '')
                abstract = paper.get('abstract', '')
                paper_url = paper.get('url', '')
                venue = paper.get('venue', '')

                # Get DOI if available
                doi = None
                external_ids = paper.get('externalIds', {})
                if external_ids:
                    doi = external_ids.get('DOI')

                # Verify URL exists
                url_verified = await self._verify_url(paper_url)

                citation = f"{', '.join(authors)}, \"{title}\", {venue} ({year})" if venue else f"{', '.join(authors)}, \"{title}\" ({year})"

                return SourceVerificationResult(
                    success=True,
                    tier=2,
                    verification_method="semantic_scholar",
                    verification_status="verified",
                    citation=citation,
                    url=paper_url,
                    quote_text=abstract[:500] if abstract else None,  # Use abstract as initial quote
                    content_type="verified_paraphrase" if abstract else "exact_quote",
                    url_verified=url_verified,
                    metadata={
                        "title": title,
                        "author": ', '.join(authors),
                        "publication_date": str(year),
                        "doi": doi,
                        "venue": venue,
                        "content_snippet": abstract,
                        "source_type": "paper"
                    }
                )

        except Exception as e:
            print(f"Semantic Scholar API error: {e}")
            return None

    async def _check_ancient_texts(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Tier 3: Check ancient/religious texts APIs (Perseus, CCEL).

        Tries multiple APIs in order:
        1. Perseus Digital Library (CTS API) - Ancient Greek/Latin texts
        2. CCEL (Christian Classics Ethereal Library) - Christian classics

        Args:
            source_query: Search query (work title + author/attribution)

        Returns:
            SourceVerificationResult if ancient text found, None otherwise
        """
        # Try Perseus CTS API first (ancient Greek/Latin)
        perseus_result = await self._check_perseus(source_query)
        if perseus_result:
            return perseus_result

        # Try CCEL (Christian classics)
        ccel_result = await self._check_ccel(source_query)
        if ccel_result:
            return ccel_result

        return None

    async def _check_perseus(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Check Perseus Digital Library CTS API for ancient Greek/Latin texts.

        Uses Canonical Text Services (CTS) protocol to search for and retrieve
        passages from ancient texts.

        Args:
            source_query: Search query (work title + author)

        Returns:
            SourceVerificationResult if text found, None otherwise
        """
        try:
            # Perseus CTS API endpoint
            base_url = "http://www.perseus.tufts.edu/hopper/CTS"

            # Try GetCapabilities to search for matching works
            # Note: Perseus CTS is limited - this is a basic search
            # In production, would need more sophisticated URN matching
            async with httpx.AsyncClient() as client:
                # Attempt a simple text search via Perseus Hopper
                search_url = f"http://www.perseus.tufts.edu/hopper/searchresults"
                params = {
                    "q": source_query,
                    "target": "text"
                }

                response = await client.get(search_url, params=params, timeout=10.0)

                if response.status_code != 200:
                    return None

                # Perseus doesn't have a clean JSON API for search results
                # This is a limitation - would need HTML parsing for full implementation
                # For now, check if we got results (non-empty response)
                if not response.text or len(response.text) < 1000:
                    return None

                # Basic success indicator - construct a result
                # Note: This is simplified; full implementation would parse HTML
                # or use CTS URN lookups with known work identifiers
                return SourceVerificationResult(
                    success=True,
                    tier=3,
                    verification_method="perseus_digital_library",
                    verification_status="partially_verified",
                    citation=f"Perseus Digital Library: {source_query}",
                    url=f"http://www.perseus.tufts.edu/hopper/searchresults?q={source_query.replace(' ', '+')}",
                    quote_text=None,
                    content_type="verified_paraphrase",
                    url_verified=True,
                    metadata={
                        "title": source_query,
                        "source_type": "ancient_text",
                        "note": "Perseus Digital Library search result"
                    }
                )

        except Exception as e:
            print(f"Perseus API error: {e}")
            return None

    async def _check_ccel(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Check CCEL (Christian Classics Ethereal Library) for Christian texts.

        Searches CCEL's collection of early church fathers, theologians, and
        Christian classics.

        Args:
            source_query: Search query (work title + author)

        Returns:
            SourceVerificationResult if text found, None otherwise
        """
        try:
            # CCEL search endpoint (using their site search)
            base_url = "https://www.ccel.org/search"

            async with httpx.AsyncClient() as client:
                # Search CCEL
                params = {"qu": source_query}
                response = await client.get(base_url, params=params, timeout=10.0, follow_redirects=True)

                if response.status_code != 200:
                    return None

                # Check if we got meaningful results
                # CCEL returns HTML search results - basic check for result content
                if not response.text or "No results found" in response.text:
                    return None

                # Extract first result link if present (basic HTML parsing)
                # Look for /ccel/ links in response
                import re
                ccel_links = re.findall(r'href="(/ccel/[^"]+)"', response.text)

                if not ccel_links:
                    return None

                # Get first result
                first_result = ccel_links[0]
                full_url = f"https://www.ccel.org{first_result}"

                # Verify URL exists
                url_verified = await self._verify_url(full_url)

                return SourceVerificationResult(
                    success=True,
                    tier=3,
                    verification_method="ccel",
                    verification_status="verified",
                    citation=f"CCEL: {source_query}",
                    url=full_url,
                    quote_text=None,
                    content_type="exact_quote",
                    url_verified=url_verified,
                    metadata={
                        "title": source_query,
                        "source_type": "ancient_text",
                        "note": "Christian Classics Ethereal Library"
                    }
                )

        except Exception as e:
            print(f"CCEL API error: {e}")
            return None

    async def _check_tavily(self, source_query: str) -> Optional[SourceVerificationResult]:
        """
        Tier 4: Check Tavily API for web sources.

        Args:
            source_query: Search query

        Returns:
            SourceVerificationResult if web source found, None otherwise
        """
        if not self.tavily_client:
            return None

        try:
            response = self.tavily_client.search(query=source_query, max_results=1)

            if not response or 'results' not in response or len(response['results']) == 0:
                return None

            result = response['results'][0]
            title = result.get('title', 'Unknown Title')
            url = result.get('url', '')
            content = result.get('content', '')

            # Verify URL exists
            url_verified = await self._verify_url(url)

            return SourceVerificationResult(
                success=True,
                tier=4,
                verification_method="tavily",
                verification_status="partially_verified",
                citation=f"{title} ({url})",
                url=url,
                quote_text=content[:500] if content else None,
                content_type="verified_paraphrase",
                url_verified=url_verified,
                metadata={
                    "title": title,
                    "content_snippet": content,
                    "source_type": "web"
                }
            )

        except Exception as e:
            print(f"Tavily API error: {e}")
            return None

    async def _llm_fallback(
        self,
        claim_text: str,
        source_query: str,
        source_type: str
    ) -> SourceVerificationResult:
        """
        Tier 5: LLM fallback when all API tiers fail.

        Args:
            claim_text: The claim being sourced
            source_query: Search query for source
            source_type: Type of source needed

        Returns:
            SourceVerificationResult marked as unverified
        """
        # Return unverified placeholder - Source Checker will generate from LLM training data
        return SourceVerificationResult(
            success=False,
            tier=5,
            verification_method="llm_unverified",
            verification_status="unverified",
            citation=f"Source for: {source_query}",
            url="",
            quote_text=None,
            content_type="unverified_content",
            url_verified=False,
            metadata={"note": "All API verification tiers failed, LLM fallback"}
        )

    async def _verify_url(self, url: str) -> bool:
        """
        Verify that URL exists and returns 200.

        Args:
            url: URL to verify

        Returns:
            True if URL is accessible, False otherwise
        """
        if not url:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, timeout=5.0, follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    async def _add_to_library(self, result: SourceVerificationResult) -> None:
        """
        Add verified source to library for future reuse.

        Args:
            result: Verification result from Tier 1, 2, or 3
        """
        if not result.success or result.tier >= 4:
            # Only add Tier 1-3 (books, papers, ancient texts) to library
            return

        if not self.openai_client:
            # Can't generate embeddings without OpenAI client
            return

        metadata = result.metadata
        if not metadata:
            return

        # Truncate fields to database limits
        title = (metadata.get('title', '') or '')[:1000]
        author = (metadata.get('author', '') or '')[:500]
        publisher = (metadata.get('publisher', '') or '')[:500] if metadata.get('publisher') else None

        # Generate embedding for source keywords
        keywords_text = f"{title} {author}"
        embedding_response = await self.openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=keywords_text
        )
        embedding = embedding_response.data[0].embedding

        # Create VerifiedSource entry
        verified_source = VerifiedSource(
            source_type=metadata.get('source_type', 'book'),
            title=title,
            author=author,
            publisher=publisher,
            publication_date=metadata.get('publication_date'),
            isbn=metadata.get('isbn'),
            doi=metadata.get('doi'),
            url=result.url,
            content_snippet=metadata.get('content_snippet'),
            topic_keywords=[title, author],
            embedding=embedding,
            verification_method=result.verification_method,
            verification_status=result.verification_status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        try:
            await self.verified_source_repo.create(verified_source)
        except Exception as e:
            print(f"Failed to add source to library: {e}")
