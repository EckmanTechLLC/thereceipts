"""
Pipeline Orchestrator for TheReceipts multi-agent system.

Coordinates sequential execution of 5 agents:
1. TopicFinderAgent
2. SourceCheckerAgent
3. AdversarialCheckerAgent
4. WritingAgent
5. PublisherAgent

Implements fail-fast behavior: any agent failure stops pipeline immediately.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import AgentError
from agents.topic_finder import TopicFinderAgent
from agents.source_checker import SourceCheckerAgent
from agents.adversarial_checker import AdversarialCheckerAgent
from agents.writing_agent import WritingAgent
from agents.publisher import PublisherAgent


class PipelineError(Exception):
    """Raised when pipeline execution fails."""
    pass


class PipelineOrchestrator:
    """
    Orchestrates the 5-agent pipeline for claim verification.

    Each agent receives output from the previous agent and adds its own analysis.
    Pipeline fails fast on any agent error with full transparency.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize pipeline orchestrator.

        Args:
            db_session: Database session for agent configuration loading
        """
        self.db_session = db_session

    async def _emit_progress(
        self,
        event_type: str,
        data: Dict[str, Any],
        websocket_session_id: Optional[str],
        connection_manager: Optional[Any]
    ):
        """
        Emit progress event via WebSocket if connection is available.

        Args:
            event_type: Type of event (e.g., "pipeline_started", "agent_started")
            data: Event-specific data
            websocket_session_id: Session ID for WebSocket connection
            connection_manager: Connection manager instance with send_message method
        """
        if websocket_session_id and connection_manager:
            message = {
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                **data
            }
            await connection_manager.send_message(websocket_session_id, message)

    async def run_pipeline(
        self,
        question: str,
        websocket_session_id: Optional[str] = None,
        connection_manager: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Run the complete 5-agent pipeline on a question.

        Args:
            question: User's question or claim to analyze
            websocket_session_id: Optional session ID for WebSocket progress updates
            connection_manager: Optional connection manager for sending WebSocket messages

        Returns:
            Dict containing:
                - success: True if pipeline completed successfully
                - question: Original question
                - pipeline_start: ISO timestamp of pipeline start
                - pipeline_end: ISO timestamp of pipeline end
                - pipeline_duration_seconds: Total execution time
                - agents: List of agent results in execution order
                - claim_card_data: Aggregated data for creating ClaimCard
                - error: Error message if pipeline failed

        Raises:
            PipelineError: If any agent fails or pipeline encounters error
        """
        pipeline_start = datetime.utcnow()
        agent_results = []
        aggregated_data = {"question": question}

        # Emit pipeline started event
        await self._emit_progress(
            "pipeline_started",
            {"question": question},
            websocket_session_id,
            connection_manager
        )

        try:
            # Agent 1: TopicFinder
            agent_start = datetime.utcnow()
            await self._emit_progress(
                "agent_started",
                {"agent_name": "topic_finder"},
                websocket_session_id,
                connection_manager
            )

            topic_finder = TopicFinderAgent(self.db_session)
            topic_output = await topic_finder.run(aggregated_data)
            agent_results.append({
                "agent": "topic_finder",
                "result": topic_output,
                "timestamp": datetime.utcnow().isoformat()
            })

            agent_duration = (datetime.utcnow() - agent_start).total_seconds()
            await self._emit_progress(
                "agent_completed",
                {
                    "agent_name": "topic_finder",
                    "duration": agent_duration,
                    "success": topic_output["success"]
                },
                websocket_session_id,
                connection_manager
            )

            # Merge output into aggregated data for next agent
            aggregated_data.update(topic_output["output"])

            # Agent 2: SourceChecker
            agent_start = datetime.utcnow()
            await self._emit_progress(
                "agent_started",
                {"agent_name": "source_checker"},
                websocket_session_id,
                connection_manager
            )

            source_checker = SourceCheckerAgent(self.db_session)
            source_output = await source_checker.run(aggregated_data)
            agent_results.append({
                "agent": "source_checker",
                "result": source_output,
                "timestamp": datetime.utcnow().isoformat()
            })

            agent_duration = (datetime.utcnow() - agent_start).total_seconds()
            await self._emit_progress(
                "agent_completed",
                {
                    "agent_name": "source_checker",
                    "duration": agent_duration,
                    "success": source_output["success"]
                },
                websocket_session_id,
                connection_manager
            )

            aggregated_data.update(source_output["output"])

            # Agent 3: AdversarialChecker
            agent_start = datetime.utcnow()
            await self._emit_progress(
                "agent_started",
                {"agent_name": "adversarial_checker"},
                websocket_session_id,
                connection_manager
            )

            adversarial_checker = AdversarialCheckerAgent(self.db_session)
            adversarial_output = await adversarial_checker.run(aggregated_data)
            agent_results.append({
                "agent": "adversarial_checker",
                "result": adversarial_output,
                "timestamp": datetime.utcnow().isoformat()
            })

            agent_duration = (datetime.utcnow() - agent_start).total_seconds()
            await self._emit_progress(
                "agent_completed",
                {
                    "agent_name": "adversarial_checker",
                    "duration": agent_duration,
                    "success": adversarial_output["success"]
                },
                websocket_session_id,
                connection_manager
            )

            aggregated_data.update(adversarial_output["output"])

            # Agent 4: WritingAgent
            agent_start = datetime.utcnow()
            await self._emit_progress(
                "agent_started",
                {"agent_name": "writing_agent"},
                websocket_session_id,
                connection_manager
            )

            writing_agent = WritingAgent(self.db_session)
            writing_output = await writing_agent.run(aggregated_data)
            agent_results.append({
                "agent": "writing_agent",
                "result": writing_output,
                "timestamp": datetime.utcnow().isoformat()
            })

            agent_duration = (datetime.utcnow() - agent_start).total_seconds()
            await self._emit_progress(
                "agent_completed",
                {
                    "agent_name": "writing_agent",
                    "duration": agent_duration,
                    "success": writing_output["success"]
                },
                websocket_session_id,
                connection_manager
            )

            aggregated_data.update(writing_output["output"])

            # Agent 5: Publisher
            agent_start = datetime.utcnow()
            await self._emit_progress(
                "agent_started",
                {"agent_name": "publisher"},
                websocket_session_id,
                connection_manager
            )

            publisher = PublisherAgent(self.db_session)
            publisher_output = await publisher.run(aggregated_data)
            agent_results.append({
                "agent": "publisher",
                "result": publisher_output,
                "timestamp": datetime.utcnow().isoformat()
            })

            agent_duration = (datetime.utcnow() - agent_start).total_seconds()
            await self._emit_progress(
                "agent_completed",
                {
                    "agent_name": "publisher",
                    "duration": agent_duration,
                    "success": publisher_output["success"]
                },
                websocket_session_id,
                connection_manager
            )

            aggregated_data.update(publisher_output["output"])

            # Calculate duration
            pipeline_end = datetime.utcnow()
            duration = (pipeline_end - pipeline_start).total_seconds()

            # Emit pipeline completed event
            await self._emit_progress(
                "pipeline_completed",
                {"duration": duration},
                websocket_session_id,
                connection_manager
            )

            # Build claim card data structure
            claim_card_data = {
                "claim_text": aggregated_data.get("claim_text", ""),
                "claimant": aggregated_data.get("claimant", ""),
                "claim_type": aggregated_data.get("claim_type", ""),
                "verdict": aggregated_data.get("verdict", ""),
                "short_answer": aggregated_data.get("short_answer", ""),
                "deep_answer": aggregated_data.get("deep_answer", ""),
                "why_persists": aggregated_data.get("why_persists", []),
                "confidence_level": aggregated_data.get("confidence_level", ""),
                "confidence_explanation": aggregated_data.get("confidence_explanation", ""),
                "primary_sources": aggregated_data.get("primary_sources", []),
                "scholarly_sources": aggregated_data.get("scholarly_sources", []),
                "apologetics_techniques": aggregated_data.get("apologetics_techniques", []),
                "category_tags": aggregated_data.get("category_tags", []),
                "audit_summary": aggregated_data.get("audit_summary", ""),
                "limitations": aggregated_data.get("limitations", []),
                "change_verdict_if": aggregated_data.get("change_verdict_if", ""),
            }

            return {
                "success": True,
                "question": question,
                "pipeline_start": pipeline_start.isoformat(),
                "pipeline_end": pipeline_end.isoformat(),
                "pipeline_duration_seconds": duration,
                "agents": agent_results,
                "claim_card_data": claim_card_data,
                "error": None,
            }

        except AgentError as e:
            # Agent failed - fail fast with full transparency
            pipeline_end = datetime.utcnow()
            duration = (pipeline_end - pipeline_start).total_seconds()

            # Emit pipeline failed event
            await self._emit_progress(
                "pipeline_failed",
                {"error": str(e), "duration": duration},
                websocket_session_id,
                connection_manager
            )

            return {
                "success": False,
                "question": question,
                "pipeline_start": pipeline_start.isoformat(),
                "pipeline_end": pipeline_end.isoformat(),
                "pipeline_duration_seconds": duration,
                "agents": agent_results,
                "claim_card_data": None,
                "error": str(e),
            }

        except Exception as e:
            # Unexpected error
            pipeline_end = datetime.utcnow()
            duration = (pipeline_end - pipeline_start).total_seconds()

            raise PipelineError(
                f"Pipeline failed with unexpected error: {str(e)}"
            )
