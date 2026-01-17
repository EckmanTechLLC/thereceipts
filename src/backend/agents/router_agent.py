"""
Router Agent for TheReceipts intelligent routing system.

Routes user questions to appropriate response modes using LLM tool calling:
- Mode 1 (Exact Match): Existing claim card answers the question
- Mode 2 (Contextual): Synthesize answer from existing cards
- Mode 3 (Novel Claim): Generate new claim via full pipeline

Implements tool calling for 3 tools:
1. search_existing_claims - Find candidate claim cards
2. get_claim_details - Retrieve specific card details
3. generate_new_claim - Trigger pipeline for novel claims
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from anthropic import AsyncAnthropic
import asyncio

from agents.base import BaseAgent, AgentError, AgentConfigurationError, AgentExecutionError
from config import settings
from services.router_service import RouterService


class RouterAgent(BaseAgent):
    """
    Router Agent using LLM tool calling to intelligently route questions.

    Differs from other agents in the pipeline:
    - Uses Anthropic tool calling (not simple text completion)
    - Executes tools based on LLM decisions
    - Returns routing decision + tool results
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize Router Agent with database session."""
        super().__init__(agent_name="router", db_session=db_session)

        # Tool definitions for Anthropic API
        self.tools = [
            {
                "name": "search_existing_claims",
                "description": (
                    "Search for existing claim cards that might answer the user's question. "
                    "Returns a list of candidate cards with similarity scores. Use this FIRST "
                    "to check if existing content can answer the question."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (use reformulated question from context analyzer)"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Similarity threshold (0-1). Default 0.92. Higher = stricter matching.",
                            "default": 0.92
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_claim_details",
                "description": (
                    "Retrieve full details of a specific claim card by ID. Use this when you "
                    "need more context about a claim found via search, or to compare multiple "
                    "existing claims for a contextual response."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "claim_id": {
                            "type": "string",
                            "description": "UUID of the claim card to retrieve"
                        }
                    },
                    "required": ["claim_id"]
                }
            },
            {
                "name": "generate_new_claim",
                "description": (
                    "Trigger the full 5-agent pipeline to generate a new claim card. Use this "
                    "when the user's question represents a NOVEL claim not answered by existing "
                    "cards. Be conservative: only use when genuinely new."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The user's question that requires a new claim card"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of why this is a novel claim"
                        }
                    },
                    "required": ["question", "reasoning"]
                }
            }
        ]

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Router Agent logic with tool calling.

        Args:
            input_data: Dict containing:
                - reformulated_question: From Context Analyzer
                - original_question: User's original question
                - conversation_history: List of prior messages

        Returns:
            Dict containing:
                - mode: "exact_match" | "contextual" | "novel_claim"
                - tool_results: Results from tools executed
                - reasoning: LLM's routing decision reasoning
                - final_answer: LLM-generated response (for modes 1 & 2)
        """
        # Load configuration from database (system prompt, model, etc.)
        await self.load_config()

        reformulated_question = input_data.get("reformulated_question")
        original_question = input_data.get("original_question")
        conversation_history = input_data.get("conversation_history", [])

        if not reformulated_question or not original_question:
            raise AgentExecutionError("Missing required fields: reformulated_question, original_question")

        # Build user message with context
        user_message = self._build_user_message(
            reformulated_question=reformulated_question,
            original_question=original_question,
            conversation_history=conversation_history
        )

        # Call LLM with tool support
        result = await self._call_llm_with_tools(user_message)

        return result

    def _build_user_message(
        self,
        reformulated_question: str,
        original_question: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Build user message with conversation context."""
        message_parts = []

        # Add conversation history if present
        if conversation_history:
            message_parts.append("=== Conversation History ===")
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                message_parts.append(f"{role.upper()}: {content}")
            message_parts.append("")

        # Add current question
        message_parts.append("=== Current Question ===")
        message_parts.append(f"Original: {original_question}")
        message_parts.append(f"Reformulated: {reformulated_question}")
        message_parts.append("")
        message_parts.append("Use the tools available to route this question appropriately.")

        return "\n".join(message_parts)

    async def _call_llm_with_tools(self, user_message: str) -> Dict[str, Any]:
        """
        Call Anthropic LLM with tool support, handle tool execution loop.

        Returns routing decision with tool results.
        """
        if not self.llm_provider or self.llm_provider.lower() != "anthropic":
            raise AgentConfigurationError("Router Agent requires Anthropic provider for tool calling")

        if not settings.ANTHROPIC_API_KEY:
            raise AgentConfigurationError("Anthropic API key not configured")

        anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        messages = [{"role": "user", "content": user_message}]
        tool_results = []

        try:
            # Tool execution loop (Anthropic may request multiple tool calls)
            while True:
                response = await asyncio.wait_for(
                    anthropic_client.messages.create(
                        model=self.model_name,
                        system=self.system_prompt,
                        messages=messages,
                        tools=self.tools,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    ),
                    timeout=settings.PIPELINE_TIMEOUT
                )

                # Check if LLM wants to use tools
                if response.stop_reason == "tool_use":
                    # Extract tool calls and execute them
                    for content_block in response.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input
                            tool_use_id = content_block.id

                            # Execute the tool (placeholder - actual implementation in service layer)
                            tool_result = await self._execute_tool(tool_name, tool_input)
                            tool_results.append({
                                "tool_name": tool_name,
                                "tool_input": tool_input,
                                "tool_result": tool_result
                            })

                            # Add tool result to conversation
                            messages.append({"role": "assistant", "content": response.content})
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": str(tool_result)
                                }]
                            })
                else:
                    # LLM provided final answer
                    final_text = ""
                    for content_block in response.content:
                        if hasattr(content_block, "text"):
                            final_text += content_block.text

                    # Determine mode from tool usage
                    mode = self._determine_mode(tool_results, final_text)

                    return {
                        "mode": mode,
                        "tool_results": tool_results,
                        "final_answer": final_text,
                        "usage": {
                            "input_tokens": response.usage.input_tokens,
                            "output_tokens": response.usage.output_tokens
                        }
                    }

        except asyncio.TimeoutError:
            raise AgentExecutionError(f"Router Agent LLM call exceeded timeout")
        except Exception as e:
            raise AgentExecutionError(f"Router Agent tool calling failed: {str(e)}")

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool and return results.

        Routes tool calls to RouterService which has access to repositories and services.
        """
        router_service = RouterService(self.db_session)

        try:
            if tool_name == "search_existing_claims":
                query = tool_input.get("query")
                threshold = tool_input.get("threshold", 0.92)
                results = await router_service.search_existing_claims(query, threshold)
                return {
                    "status": "success",
                    "results": results,
                    "count": len(results)
                }

            elif tool_name == "get_claim_details":
                claim_id = tool_input.get("claim_id")
                result = await router_service.get_claim_details(claim_id)
                if result:
                    return {
                        "status": "success",
                        "claim": result
                    }
                else:
                    return {
                        "status": "not_found",
                        "message": f"Claim with ID {claim_id} not found"
                    }

            elif tool_name == "generate_new_claim":
                question = tool_input.get("question")
                reasoning = tool_input.get("reasoning")
                result = await router_service.generate_new_claim(question, reasoning)
                return result

            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Tool execution failed: {str(e)}"
            }

    def _determine_mode(self, tool_results: List[Dict[str, Any]], final_answer: str) -> str:
        """
        Determine routing mode from tool usage pattern and similarity scores.

        Logic:
        - generate_new_claim called -> "novel_claim"
        - get_claim_details called OR multiple searches -> "contextual"
        - Single search with similarity >= 0.92 -> "exact_match" (matches search threshold)
        - Single search with similarity >= 0.80 -> "contextual" (similar topic, different angle)
        - Single search with similarity < 0.80 or no results -> "novel_claim"
        - Default -> "contextual"
        """
        if not tool_results:
            return "CONTEXTUAL"

        tool_names = [t["tool_name"] for t in tool_results]

        if "generate_new_claim" in tool_names:
            return "NOVEL_CLAIM"

        if "get_claim_details" in tool_names:
            return "CONTEXTUAL"

        # Check if single search returned high-confidence result
        if len(tool_results) == 1 and tool_results[0]["tool_name"] == "search_existing_claims":
            tool_result = tool_results[0].get("tool_result", {})

            # Extract results array from tool result
            results = tool_result.get("results", [])

            # No results means novel claim
            if not results:
                return "NOVEL_CLAIM"

            # Get top result's similarity score
            top_result = results[0]
            similarity = top_result.get("similarity", 0.0)

            # Apply similarity thresholds
            # Lowered from 0.95 to 0.92 to match search threshold
            if similarity >= 0.92:
                return "EXACT_MATCH"
            elif similarity >= 0.80:
                return "CONTEXTUAL"
            else:
                return "NOVEL_CLAIM"

        return "CONTEXTUAL"
