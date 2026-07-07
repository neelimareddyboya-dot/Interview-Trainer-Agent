"""
Interview Knowledge Agent
Responsible for retrieving relevant interview knowledge from the RAG pipeline
and providing domain-specific context to other agents.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InterviewKnowledgeAgent:
    """Retrieves domain knowledge and interview context using RAG."""

    def __init__(self, watsonx_client, rag_pipeline, agent_instructions: dict):
        self.client = watsonx_client
        self.rag = rag_pipeline
        self.instructions = agent_instructions
        self.model_id = agent_instructions.get("model_id", "ibm/granite-13b-chat-v2")

    def retrieve_domain_knowledge(self, query: str, domain: str, top_k: int = 5) -> str:
        """Retrieve relevant knowledge chunks for the given domain and query."""
        try:
            enhanced_query = f"{domain} interview: {query}"
            chunks = self.rag.retrieve(enhanced_query, top_k=top_k)
            if not chunks:
                return f"No specific knowledge found for domain: {domain}"
            return "\n\n---\n\n".join(chunks)
        except Exception as e:
            logger.error("Knowledge retrieval failed: %s", e)
            return ""

    def get_company_patterns(self, company: str) -> str:
        """Retrieve company-specific interview patterns."""
        query = f"{company} interview process technical questions behavioral"
        return self.retrieve_domain_knowledge(query, domain="company patterns")

    def get_concept_explanation(self, concept: str, domain: str) -> str:
        """Get a deep explanation of a technical concept."""
        query = f"explain {concept} in detail with examples"
        return self.retrieve_domain_knowledge(query, domain=domain)

    def build_knowledge_context(
        self, domain: str, job_role: str, skills: list[str], level: str
    ) -> str:
        """Build comprehensive knowledge context for question generation."""
        queries = [
            f"{domain} {job_role} interview questions {level} level",
            f"{' '.join(skills[:3])} technical concepts interview",
            f"{job_role} system design best practices",
        ]
        all_chunks = []
        for q in queries:
            chunks = self.rag.retrieve(q, top_k=3)
            all_chunks.extend(chunks)
        # Deduplicate while preserving order
        seen = set()
        unique_chunks = []
        for c in all_chunks:
            h = hash(c[:100])
            if h not in seen:
                seen.add(h)
                unique_chunks.append(c)
        return "\n\n---\n\n".join(unique_chunks[:6])
