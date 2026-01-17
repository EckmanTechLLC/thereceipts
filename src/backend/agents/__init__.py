"""
Multi-agent pipeline for TheReceipts claim verification.

Five agents run sequentially to audit Christianity-related claims:
1. TopicFinderAgent - Identifies claim, claimant, why it matters
2. SourceCheckerAgent - Collects primary and scholarly sources
3. AdversarialCheckerAgent - Attempts to falsify, verifies quotes
4. WritingAgent - Produces final prose (short + deep answers)
5. PublisherAgent - Creates audit summary, states limitations

Additional agents for auto-blog system (Phase 3):
- DecomposerAgent - Breaks topics into component claims (runs before 5-agent pipeline)
- BlogComposerAgent - Synthesizes claim cards into prose articles (runs after pipeline)
- RouterAgent - Intelligent routing for conversational chat (Phase 2)
"""

from agents.topic_finder import TopicFinderAgent
from agents.source_checker import SourceCheckerAgent
from agents.adversarial_checker import AdversarialCheckerAgent
from agents.writing_agent import WritingAgent
from agents.publisher import PublisherAgent
from agents.router_agent import RouterAgent
from agents.decomposer import DecomposerAgent
from agents.blog_composer import BlogComposerAgent

__all__ = [
    "TopicFinderAgent",
    "SourceCheckerAgent",
    "AdversarialCheckerAgent",
    "WritingAgent",
    "PublisherAgent",
    "RouterAgent",
    "DecomposerAgent",
    "BlogComposerAgent",
]
