"""
Base Agent class for TheReceipts multi-agent pipeline.

Provides common functionality for loading configuration from database,
calling LLMs, and executing agent logic with fail-fast error handling.
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import AgentPromptRepository
from services.llm_client import LLMClient, LLMClientError


def extract_json_from_response(raw_content: str) -> str:
    """
    Extract JSON object from LLM response, handling markdown code blocks and extra text.

    LLMs often wrap JSON in markdown code blocks or add explanatory text after the JSON.
    This function robustly extracts just the JSON object.

    Args:
        raw_content: Raw LLM response text

    Returns:
        Extracted JSON string ready for json.loads()

    Raises:
        ValueError: If no valid JSON object found in content
    """
    content = raw_content.strip()

    # Try to extract JSON from markdown code block
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        if end > start:
            content = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end > start:
            content = content[start:end].strip()

    # If content starts with {, extract just the JSON object (ignore trailing text)
    if content.startswith("{"):
        # Find the matching closing brace
        brace_count = 0
        json_end = -1
        for i, char in enumerate(content):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break

        if json_end > 0:
            content = content[:json_end]
        else:
            raise ValueError("No matching closing brace found for JSON object")

    return content


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class AgentConfigurationError(AgentError):
    """Raised when agent configuration is missing or invalid."""
    pass


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""
    pass


class BaseAgent(ABC):
    """
    Base class for all agents in the pipeline.

    Each agent:
    1. Loads its configuration from the database (agent_prompts table)
    2. Calls an LLM with the configured provider and parameters
    3. Executes agent-specific logic to process input and return output
    4. Implements fail-fast behavior (no retries, immediate error propagation)
    """

    def __init__(self, agent_name: str, db_session: AsyncSession):
        """
        Initialize the agent.

        Args:
            agent_name: Unique identifier for this agent (matches agent_prompts.agent_name)
            db_session: Database session for loading configuration
        """
        self.agent_name = agent_name
        self.db_session = db_session
        self.llm_client = LLMClient()

        # Configuration loaded from database
        self.llm_provider: Optional[str] = None
        self.model_name: Optional[str] = None
        self.system_prompt: Optional[str] = None
        self.temperature: float = 0.7
        self.max_tokens: int = 4096

    async def load_config(self) -> None:
        """
        Load agent configuration from database.

        Retrieves agent prompt configuration from agent_prompts table by agent_name.
        Raises AgentConfigurationError if configuration not found.
        """
        repo = AgentPromptRepository(self.db_session)
        config = await repo.get_by_agent_name(self.agent_name)

        if not config:
            raise AgentConfigurationError(
                f"No configuration found for agent '{self.agent_name}'. "
                f"Ensure agent_prompts table has entry for this agent."
            )

        self.llm_provider = config.llm_provider
        self.model_name = config.model_name
        self.system_prompt = config.system_prompt
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def call_llm(self, user_message: str) -> Dict[str, Any]:
        """
        Call LLM with configured provider and parameters.

        Args:
            user_message: User message to send to the LLM

        Returns:
            Dict containing:
                - content: Generated text
                - usage: Token usage stats
                - model: Model used

        Raises:
            AgentConfigurationError: If configuration not loaded
            AgentExecutionError: If LLM call fails
        """
        if not all([self.llm_provider, self.model_name, self.system_prompt]):
            raise AgentConfigurationError(
                f"Agent '{self.agent_name}' configuration not loaded. "
                f"Call load_config() before calling LLM."
            )

        try:
            response = await self.llm_client.call(
                provider=self.llm_provider,
                model_name=self.model_name,
                system_prompt=self.system_prompt,
                user_message=user_message,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response

        except LLMClientError as e:
            raise AgentExecutionError(
                f"Agent '{self.agent_name}' LLM call failed: {str(e)}"
            )

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent logic.

        Each agent implements this method to:
        1. Process input from previous agent (or initial question)
        2. Call LLM with appropriate prompt
        3. Parse and structure output for next agent
        4. Return structured JSON/dict for pipeline

        Args:
            input_data: Input from previous agent or initial question

        Returns:
            Structured output dict for next agent

        Raises:
            AgentExecutionError: If execution fails
        """
        pass

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point to run the agent.

        Loads configuration, executes agent logic, returns output.
        Implements fail-fast behavior - any error propagates immediately.

        Args:
            input_data: Input from previous agent or initial question

        Returns:
            Structured output dict containing:
                - agent_name: Name of this agent
                - success: True if execution succeeded
                - output: Agent-specific output data
                - error: Error message if execution failed
                - usage: Token usage stats from LLM call

        Raises:
            AgentError: If configuration loading or execution fails
        """
        try:
            # Load configuration from database
            await self.load_config()

            # Execute agent logic
            output = await self.execute(input_data)

            return {
                "agent_name": self.agent_name,
                "success": True,
                "output": output,
                "error": None,
            }

        except AgentError as e:
            # Fail fast: propagate error immediately
            raise
        except Exception as e:
            # Wrap unexpected errors in AgentExecutionError
            raise AgentExecutionError(
                f"Agent '{self.agent_name}' failed with unexpected error: {str(e)}"
            )
