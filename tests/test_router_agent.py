"""
Unit tests for Router Agent.

Tests initialization, configuration loading, and tool definitions.
Phase 3.1 - Foundation tests only (tool execution tested in later phases).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.agents.router_agent import RouterAgent
from src.backend.agents.base import AgentConfigurationError


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration from database."""
    config = MagicMock()
    config.llm_provider = "anthropic"
    config.model_name = "claude-3-sonnet-20240229"
    config.system_prompt = "You are a routing agent."
    config.temperature = 0.1
    config.max_tokens = 4000
    return config


class TestRouterAgentInitialization:
    """Test Router Agent initialization."""

    def test_router_agent_creates_with_correct_name(self, mock_db_session):
        """Router Agent should initialize with agent_name='router'."""
        agent = RouterAgent(db_session=mock_db_session)
        assert agent.agent_name == "router"

    def test_router_agent_has_tool_definitions(self, mock_db_session):
        """Router Agent should define 3 tools."""
        agent = RouterAgent(db_session=mock_db_session)
        assert hasattr(agent, "tools")
        assert len(agent.tools) == 3

        tool_names = [tool["name"] for tool in agent.tools]
        assert "search_existing_claims" in tool_names
        assert "get_claim_details" in tool_names
        assert "generate_new_claim" in tool_names

    def test_search_existing_claims_tool_schema(self, mock_db_session):
        """search_existing_claims tool should have correct schema."""
        agent = RouterAgent(db_session=mock_db_session)
        search_tool = next(t for t in agent.tools if t["name"] == "search_existing_claims")

        assert "input_schema" in search_tool
        schema = search_tool["input_schema"]
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "threshold" in schema["properties"]
        assert "query" in schema["required"]

    def test_get_claim_details_tool_schema(self, mock_db_session):
        """get_claim_details tool should have correct schema."""
        agent = RouterAgent(db_session=mock_db_session)
        details_tool = next(t for t in agent.tools if t["name"] == "get_claim_details")

        assert "input_schema" in details_tool
        schema = details_tool["input_schema"]
        assert schema["type"] == "object"
        assert "claim_id" in schema["properties"]
        assert "claim_id" in schema["required"]

    def test_generate_new_claim_tool_schema(self, mock_db_session):
        """generate_new_claim tool should have correct schema."""
        agent = RouterAgent(db_session=mock_db_session)
        generate_tool = next(t for t in agent.tools if t["name"] == "generate_new_claim")

        assert "input_schema" in generate_tool
        schema = generate_tool["input_schema"]
        assert schema["type"] == "object"
        assert "question" in schema["properties"]
        assert "reasoning" in schema["properties"]
        assert "question" in schema["required"]
        assert "reasoning" in schema["required"]


class TestRouterAgentConfiguration:
    """Test Router Agent configuration loading."""

    @pytest.mark.asyncio
    async def test_load_config_sets_anthropic_provider(self, mock_db_session, mock_agent_config):
        """Router Agent should load Anthropic configuration."""
        agent = RouterAgent(db_session=mock_db_session)

        # Mock repository
        with patch("src.backend.agents.base.AgentPromptRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_agent_name = AsyncMock(return_value=mock_agent_config)

            await agent.load_config()

            assert agent.llm_provider == "anthropic"
            assert agent.model_name == "claude-3-sonnet-20240229"
            assert agent.temperature == 0.1
            assert agent.max_tokens == 4000

    @pytest.mark.asyncio
    async def test_load_config_raises_if_no_config_found(self, mock_db_session):
        """Router Agent should raise AgentConfigurationError if config not found."""
        agent = RouterAgent(db_session=mock_db_session)

        with patch("src.backend.agents.base.AgentPromptRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_agent_name = AsyncMock(return_value=None)

            with pytest.raises(AgentConfigurationError) as exc_info:
                await agent.load_config()

            assert "No configuration found for agent 'router'" in str(exc_info.value)


class TestRouterAgentExecution:
    """Test Router Agent execution (basic validation only)."""

    @pytest.mark.asyncio
    async def test_execute_requires_reformulated_question(self, mock_db_session):
        """execute() should raise error if reformulated_question missing."""
        agent = RouterAgent(db_session=mock_db_session)

        input_data = {
            "original_question": "Did the flood happen?"
            # Missing reformulated_question
        }

        with pytest.raises(Exception) as exc_info:
            await agent.execute(input_data)

        assert "reformulated_question" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_requires_original_question(self, mock_db_session):
        """execute() should raise error if original_question missing."""
        agent = RouterAgent(db_session=mock_db_session)

        input_data = {
            "reformulated_question": "Was there a global flood?"
            # Missing original_question
        }

        with pytest.raises(Exception) as exc_info:
            await agent.execute(input_data)

        assert "original_question" in str(exc_info.value)

    def test_build_user_message_includes_questions(self, mock_db_session):
        """_build_user_message should include both question forms."""
        agent = RouterAgent(db_session=mock_db_session)

        message = agent._build_user_message(
            reformulated_question="Was there a global flood in history?",
            original_question="Did the flood happen?",
            conversation_history=[]
        )

        assert "Did the flood happen?" in message
        assert "Was there a global flood in history?" in message

    def test_build_user_message_includes_conversation_history(self, mock_db_session):
        """_build_user_message should include recent conversation context."""
        agent = RouterAgent(db_session=mock_db_session)

        history = [
            {"role": "user", "content": "Tell me about Noah's flood"},
            {"role": "assistant", "content": "Here's information about the flood claim..."}
        ]

        message = agent._build_user_message(
            reformulated_question="What evidence exists for the flood?",
            original_question="What about flood evidence?",
            conversation_history=history
        )

        assert "Conversation History" in message
        assert "Noah's flood" in message


class TestRouterAgentModeDetection:
    """Test mode determination logic."""

    def test_determine_mode_novel_claim_when_generate_new_claim_called(self, mock_db_session):
        """Mode should be 'novel_claim' if generate_new_claim tool was used."""
        agent = RouterAgent(db_session=mock_db_session)

        tool_results = [
            {"tool_name": "search_existing_claims", "tool_result": {}},
            {"tool_name": "generate_new_claim", "tool_result": {}}
        ]

        mode = agent._determine_mode(tool_results, "Final answer text")
        assert mode == "novel_claim"

    def test_determine_mode_contextual_when_get_claim_details_called(self, mock_db_session):
        """Mode should be 'contextual' if get_claim_details tool was used."""
        agent = RouterAgent(db_session=mock_db_session)

        tool_results = [
            {"tool_name": "search_existing_claims", "tool_result": {}},
            {"tool_name": "get_claim_details", "tool_result": {}}
        ]

        mode = agent._determine_mode(tool_results, "Final answer text")
        assert mode == "contextual"

    def test_determine_mode_defaults_to_contextual(self, mock_db_session):
        """Mode should default to 'contextual' for ambiguous cases."""
        agent = RouterAgent(db_session=mock_db_session)

        tool_results = [
            {"tool_name": "search_existing_claims", "tool_result": {}}
        ]

        mode = agent._determine_mode(tool_results, "Final answer text")
        assert mode == "contextual"
