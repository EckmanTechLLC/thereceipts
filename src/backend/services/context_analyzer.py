"""
Context Analyzer Service for TheReceipts conversational chat.

Reformulates user messages with conversation history to create contextualized questions.
Uses lightweight LLM calls (Claude Haiku or GPT-3.5-turbo) for speed and cost efficiency.
"""

from typing import List, Dict, Any
from services.llm_client import LLMClient, LLMClientError


class ContextAnalyzerError(Exception):
    """Base exception for context analyzer errors."""
    pass


class ContextAnalyzer:
    """
    Analyzes conversation context to reformulate user questions.

    Example:
        Conversation: ["Did Matthew copy Mark?", "What about Luke?"]
        Output: "Did Luke copy Mark?"
    """

    # System prompt for context reformulation
    SYSTEM_PROMPT = """You are a context analyzer for a conversational Q&A system about Christianity claims.

Your task: Given a conversation history and a new user message, reformulate the new message into a standalone, contextualized question.

Rules:
1. If the new message is already standalone, return it as-is
2. If it references previous context ("what about...", "and...", "also...", etc.), reformulate it to include that context
3. If the message proposes an ALTERNATIVE EXPLANATION or counter-claim ("couldn't X explain this instead?", "what if...", "but couldn't it be..."), treat it as a NEW CLAIM about that alternative - do NOT tie it back to the previous claim's verdict
4. Preserve the user's intent and specific focus
5. Output ONLY the reformulated question, no explanation
6. Keep it concise and clear

Examples:

History: ["Did Matthew copy Mark?"]
New: "What about Luke?"
Output: Did Luke copy Mark?

History: ["Was the Council of Nicaea created by Constantine to control Christians?"]
New: "What evidence supports this?"
Output: What evidence supports the claim that the Council of Nicaea was created by Constantine to control Christians?

History: ["Did Moses write the Pentateuch?"]
New: "Can you explain that more?"
Output: Did Moses write the Pentateuch?

History: ["Did Matthew copy Mark?"]
New: "How do we know Matthew was copying? Couldn't they have determined the exact same messaging through divine inspiration?"
Output: Could divine inspiration explain the similarities between Matthew and Mark's gospels?

History: ["Did Jesus resurrect physically?"]
New: "What if the disciples just hallucinated?"
Output: Could the resurrection appearances be explained by hallucinations?

History: []
New: "Did Jesus exist?"
Output: Did Jesus exist?"""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize Context Analyzer.

        Args:
            llm_client: LLM client instance for making API calls
        """
        self.llm_client = llm_client

    async def analyze_context(
        self,
        conversation_history: List[Dict[str, str]],
        new_message: str
    ) -> str:
        """
        Reformulate a user message with conversation context.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
                                 Example: [{"role": "user", "content": "..."},
                                          {"role": "assistant", "content": "..."}]
            new_message: The new user message to contextualize

        Returns:
            Contextualized question string

        Raises:
            ContextAnalyzerError: If reformulation fails
        """
        # If no conversation history, return message as-is
        if not conversation_history:
            return new_message

        # Build user message for LLM
        user_message = self._build_user_message(conversation_history, new_message)

        try:
            # Use Claude Haiku for speed and cost efficiency
            # Alternative: use GPT-3.5-turbo if Anthropic unavailable
            response = await self.llm_client.call(
                provider="anthropic",
                model_name="claude-sonnet-4-5-20250929",
                system_prompt=self.SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.3,  # Low temperature for consistency
                max_tokens=200,   # Short output expected
                timeout=10        # Fast timeout (10 seconds)
            )

            contextualized_question = response["content"].strip()
            return contextualized_question

        except LLMClientError as e:
            # If Anthropic fails, try OpenAI as fallback
            try:
                response = await self.llm_client.call(
                    provider="openai",
                    model_name="gpt-3.5-turbo",
                    system_prompt=self.SYSTEM_PROMPT,
                    user_message=user_message,
                    temperature=0.3,
                    max_tokens=200,
                    timeout=10
                )

                contextualized_question = response["content"].strip()
                return contextualized_question

            except LLMClientError as fallback_error:
                raise ContextAnalyzerError(
                    f"Failed to analyze context with both providers. "
                    f"Anthropic: {str(e)}, OpenAI: {str(fallback_error)}"
                )

    def _build_user_message(
        self,
        conversation_history: List[Dict[str, str]],
        new_message: str
    ) -> str:
        """
        Build the user message for the LLM call.

        Args:
            conversation_history: List of previous messages
            new_message: New user message to contextualize

        Returns:
            Formatted user message string
        """
        # Include BOTH user questions AND assistant answers in history
        # This allows reformulation of follow-up questions that reference previous answers
        # Limit to last 3 exchanges (6 messages) to keep context focused
        recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history

        # Format as conversation flow
        if recent_history:
            history_parts = []
            for msg in recent_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                # For assistant messages, truncate to first 500 chars to keep context concise
                if role == "assistant" and len(content) > 500:
                    content = content[:500] + "..."

                history_parts.append(f"{role.upper()}: {content}")

            history_str = "\n".join(history_parts)
            return f"=== Conversation History ===\n{history_str}\n\n=== New Message ===\n{new_message}\n\nReformulated question:"
        else:
            return f"History: []\nNew: \"{new_message}\"\nOutput:"
