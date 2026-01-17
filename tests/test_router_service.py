"""
Integration tests for Router Service.

Tests actual tool implementations with database interactions:
- search_existing_claims (semantic search via pgvector)
- get_claim_details (DB lookup)
- generate_new_claim (pipeline trigger placeholder)
- log_routing_decision (router_decisions table)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.services.router_service import RouterService
from src.backend.database.models import ClaimCard, VerdictEnum, ConfidenceLevelEnum


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_claim_card():
    """Create a mock claim card for testing."""
    claim_id = uuid4()
    claim = MagicMock(spec=ClaimCard)
    claim.id = claim_id
    claim.claim_text = "The global flood is supported by geological evidence"
    claim.claimant = "Ken Ham"
    claim.claim_type = "history"
    claim.claim_type_category = "historical"
    claim.verdict = VerdictEnum.FALSE
    claim.short_answer = "No geological evidence supports a global flood"
    claim.deep_answer = "Detailed explanation of why flood geology is incorrect..."
    claim.confidence_level = ConfidenceLevelEnum.HIGH
    claim.confidence_explanation = "Overwhelming geological evidence contradicts flood geology"
    claim.why_persists = ["institutional", "confirmation_bias"]
    claim.created_at = None
    claim.similarity = 0.95  # For semantic search results
    return claim


class TestSearchExistingClaims:
    """Test search_existing_claims tool implementation."""

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self, mock_db_session, mock_claim_card):
        """search_existing_claims should return formatted claim results."""
        # Mock embedding service
        with patch('src.backend.services.router_service.EmbeddingService') as mock_embedding_class:
            mock_embedding_service = AsyncMock()
            mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
            mock_embedding_class.return_value = mock_embedding_service

            # Mock claim repository
            with patch('src.backend.services.router_service.ClaimCardRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.semantic_search.return_value = [mock_claim_card]
                mock_repo_class.return_value = mock_repo

                # Execute search
                service = RouterService(mock_db_session)
                results = await service.search_existing_claims(
                    query="Did the flood happen?",
                    threshold=0.92
                )

                # Verify embedding was generated
                mock_embedding_service.generate_embedding.assert_called_once_with("Did the flood happen?")

                # Verify semantic search was called
                mock_repo.semantic_search.assert_called_once_with(
                    query_embedding=[0.1] * 1536,
                    threshold=0.92,
                    limit=5
                )

                # Verify results format
                assert len(results) == 1
                result = results[0]
                assert result["claim_id"] == str(mock_claim_card.id)
                assert result["claim_text"] == mock_claim_card.claim_text
                assert result["short_answer"] == mock_claim_card.short_answer
                assert result["similarity"] == 0.95
                assert result["claim_type"] == "history"
                assert result["verdict"] == "False"

    @pytest.mark.asyncio
    async def test_search_with_custom_threshold(self, mock_db_session, mock_claim_card):
        """search_existing_claims should respect custom threshold."""
        with patch('src.backend.services.router_service.EmbeddingService') as mock_embedding_class:
            mock_embedding_service = AsyncMock()
            mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
            mock_embedding_class.return_value = mock_embedding_service

            with patch('src.backend.services.router_service.ClaimCardRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.semantic_search.return_value = []
                mock_repo_class.return_value = mock_repo

                service = RouterService(mock_db_session)
                results = await service.search_existing_claims(
                    query="Some question",
                    threshold=0.95
                )

                # Verify custom threshold was used
                mock_repo.semantic_search.assert_called_once()
                call_args = mock_repo.semantic_search.call_args
                assert call_args.kwargs["threshold"] == 0.95

                assert len(results) == 0


class TestGetClaimDetails:
    """Test get_claim_details tool implementation."""

    @pytest.mark.asyncio
    async def test_get_claim_details_returns_full_data(self, mock_db_session, mock_claim_card):
        """get_claim_details should return comprehensive claim data."""
        with patch('src.backend.services.router_service.ClaimCardRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = mock_claim_card
            mock_repo_class.return_value = mock_repo

            service = RouterService(mock_db_session)
            result = await service.get_claim_details(str(mock_claim_card.id))

            # Verify repository was called
            mock_repo.get_by_id.assert_called_once()

            # Verify result structure
            assert result is not None
            assert result["claim_id"] == str(mock_claim_card.id)
            assert result["claim_text"] == mock_claim_card.claim_text
            assert result["claimant"] == "Ken Ham"
            assert result["claim_type"] == "history"
            assert result["verdict"] == "False"
            assert result["short_answer"] == mock_claim_card.short_answer
            assert result["deep_answer"] == mock_claim_card.deep_answer
            assert result["confidence_level"] == "High"
            assert "confidence_explanation" in result
            assert "why_persists" in result

    @pytest.mark.asyncio
    async def test_get_claim_details_not_found(self, mock_db_session):
        """get_claim_details should return None for missing claim."""
        with patch('src.backend.services.router_service.ClaimCardRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = None
            mock_repo_class.return_value = mock_repo

            service = RouterService(mock_db_session)
            result = await service.get_claim_details(str(uuid4()))

            assert result is None

    @pytest.mark.asyncio
    async def test_get_claim_details_invalid_uuid(self, mock_db_session):
        """get_claim_details should handle invalid UUID strings."""
        service = RouterService(mock_db_session)
        result = await service.get_claim_details("not-a-valid-uuid")

        assert result is None


class TestGenerateNewClaim:
    """Test generate_new_claim tool implementation."""

    @pytest.mark.asyncio
    async def test_generate_new_claim_returns_trigger_confirmation(self, mock_db_session):
        """generate_new_claim should return pipeline trigger confirmation."""
        service = RouterService(mock_db_session)
        result = await service.generate_new_claim(
            question="Is there evidence for the resurrection?",
            reasoning="Different claim type than existing cards"
        )

        assert result["status"] == "triggered"
        assert result["question"] == "Is there evidence for the resurrection?"
        assert result["reasoning"] == "Different claim type than existing cards"
        assert "message" in result


class TestLogRoutingDecision:
    """Test log_routing_decision implementation."""

    @pytest.mark.asyncio
    async def test_log_routing_decision_creates_record(self, mock_db_session):
        """log_routing_decision should create router_decisions record."""
        # Mock RouterDecision model
        with patch('src.backend.services.router_service.RouterDecision') as mock_decision_class:
            mock_decision = MagicMock()
            mock_decision.id = uuid4()
            mock_decision_class.return_value = mock_decision

            service = RouterService(mock_db_session)
            decision_id = await service.log_routing_decision(
                question_text="Did the flood happen?",
                reformulated_question="Is there geological evidence for a global flood?",
                conversation_context=[],
                mode_selected="contextual",
                claim_cards_referenced=[str(uuid4())],
                search_candidates=[{"claim_id": str(uuid4()), "similarity": 0.93}],
                reasoning="Multiple relevant cards found, synthesizing answer",
                response_time_ms=1500
            )

            # Verify record was created
            assert decision_id == mock_decision.id
            mock_db_session.add.assert_called_once_with(mock_decision)
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(mock_decision)


class TestRouterServiceIntegration:
    """Integration tests combining multiple tool calls."""

    @pytest.mark.asyncio
    async def test_search_then_get_details_workflow(self, mock_db_session, mock_claim_card):
        """Test typical workflow: search then get details."""
        with patch('src.backend.services.router_service.EmbeddingService') as mock_embedding_class:
            mock_embedding_service = AsyncMock()
            mock_embedding_service.generate_embedding.return_value = [0.1] * 1536
            mock_embedding_class.return_value = mock_embedding_service

            with patch('src.backend.services.router_service.ClaimCardRepository') as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.semantic_search.return_value = [mock_claim_card]
                mock_repo.get_by_id.return_value = mock_claim_card
                mock_repo_class.return_value = mock_repo

                service = RouterService(mock_db_session)

                # Step 1: Search
                search_results = await service.search_existing_claims("flood evidence")
                assert len(search_results) == 1
                claim_id = search_results[0]["claim_id"]

                # Step 2: Get details
                claim_details = await service.get_claim_details(claim_id)
                assert claim_details is not None
                assert claim_details["claim_id"] == claim_id
                assert "deep_answer" in claim_details
