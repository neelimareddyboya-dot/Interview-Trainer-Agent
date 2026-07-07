"""
Career Guidance Agent
Provides personalized career advice, learning resources,
skill gap analysis, and interview readiness assessment.
"""

import logging
import json
import re

logger = logging.getLogger(__name__)


class CareerGuidanceAgent:
    """Provides AI-powered career guidance and learning recommendations."""

    def __init__(self, watsonx_client, knowledge_agent, agent_instructions: dict):
        self.client = watsonx_client
        self.knowledge_agent = knowledge_agent
        self.instructions = agent_instructions
        self.model_id = agent_instructions.get("model_id", "ibm/granite-13b-chat-v2")

    def generate_career_advice(
        self,
        domain: str,
        job_role: str,
        skills: list[str],
        experience_years: int,
        session_score: dict,
        weak_areas: list[str],
    ) -> dict:
        """Generate comprehensive career guidance based on interview performance."""

        knowledge_ctx = self.knowledge_agent.retrieve_domain_knowledge(
            f"{job_role} career path learning resources {domain}",
            domain="career guidance",
            top_k=4,
        )

        tone = self.instructions.get("communication_tone", "encouraging")
        skills_str = ", ".join(skills[:6]) if skills else "general programming"
        weak_str = ", ".join(weak_areas[:5]) if weak_areas else "none identified"

        prompt = f"""You are a supportive career coach with expertise in {domain}.

Candidate profile:
- Target role: {job_role}
- Domain: {domain}
- Skills: {skills_str}
- Experience: {experience_years} years
- Interview score: {session_score.get('overall', 0)}/100 (Grade: {session_score.get('grade', 'N/A')})
- Areas needing improvement: {weak_str}

KNOWLEDGE CONTEXT:
{knowledge_ctx[:1500]}

Communication tone: {tone}

Provide comprehensive career guidance. Return ONLY valid JSON:

{{
  "readiness_score": <integer 0-100>,
  "readiness_label": "Not Ready / Needs Work / Almost Ready / Ready / Highly Ready",
  "skill_gap_analysis": [
    {{"skill": "skill name", "current_level": "beginner/intermediate/advanced", "required_level": "intermediate/advanced/expert", "priority": "high/medium/low"}}
  ],
  "learning_roadmap": [
    {{"week": 1, "focus": "topic", "resources": ["resource 1", "resource 2"], "action": "what to do"}}
  ],
  "top_resources": [
    {{"title": "resource name", "type": "book/course/platform/tool", "url": "url or 'search online'", "description": "why this helps"}}
  ],
  "quick_wins": ["actionable tip 1", "actionable tip 2", "actionable tip 3"],
  "long_term_goals": ["goal 1", "goal 2", "goal 3"],
  "motivational_message": "A personalized, encouraging message"
}}"""

        raw_response = self.client.generate(prompt)
        return self._parse_guidance(raw_response)

    def analyze_skill_gaps(
        self, domain: str, job_role: str, skills: list[str], job_description: str = ""
    ) -> dict:
        """Analyze gaps between current skills and job requirements."""
        knowledge_ctx = self.knowledge_agent.retrieve_domain_knowledge(
            f"{job_role} required skills qualifications {domain}",
            domain=domain,
            top_k=3,
        )
        skills_str = ", ".join(skills) if skills else "not provided"
        jd_part = f"\nJob Description:\n{job_description[:600]}" if job_description else ""

        prompt = f"""Analyze skill gaps for a {job_role} position in {domain}.

Current skills: {skills_str}{jd_part}

Reference knowledge:
{knowledge_ctx[:1200]}

Return ONLY valid JSON:
{{
  "required_skills": ["skill 1", "skill 2"],
  "missing_skills": ["skill 1", "skill 2"],
  "strong_skills": ["skill 1", "skill 2"],
  "gap_severity": "low/medium/high",
  "estimated_prep_time_weeks": <integer>,
  "priority_actions": ["action 1", "action 2", "action 3"]
}}"""

        raw = self.client.generate(prompt)
        return self._parse_json_safe(raw, {
            "required_skills": [],
            "missing_skills": [],
            "strong_skills": skills[:3] if skills else [],
            "gap_severity": "medium",
            "estimated_prep_time_weeks": 4,
            "priority_actions": ["Review core concepts", "Practice coding problems", "Mock interviews"],
        })

    def get_interview_tips(self, domain: str, question_type: str) -> list[str]:
        """Return quick interview tips for a given domain and question type."""
        knowledge_ctx = self.knowledge_agent.retrieve_domain_knowledge(
            f"{question_type} interview tips strategies {domain}",
            domain="career guidance",
            top_k=2,
        )
        prompt = f"""Based on this knowledge:
{knowledge_ctx[:800]}

List 5 actionable interview tips for {question_type} questions in {domain}.
Return ONLY a JSON array of strings: ["tip 1", "tip 2", "tip 3", "tip 4", "tip 5"]"""

        raw = self.client.generate(prompt)
        try:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                tips = json.loads(match.group())
                if isinstance(tips, list):
                    return [str(t) for t in tips[:5]]
        except (json.JSONDecodeError, AttributeError):
            pass
        return [
            f"Understand core {domain} concepts deeply before the interview",
            "Practice explaining your solutions out loud",
            "Use the STAR method for behavioral questions",
            "Prepare 3-5 strong examples from past experience",
            "Research the company's tech stack and culture",
        ]

    def _parse_guidance(self, raw: str) -> dict:
        default = {
            "readiness_score": 60,
            "readiness_label": "Needs Work",
            "skill_gap_analysis": [],
            "learning_roadmap": [],
            "top_resources": [
                {"title": "IBM watsonx.ai Documentation", "type": "platform",
                 "url": "https://www.ibm.com/watsonx", "description": "Official IBM AI platform docs"},
                {"title": "LeetCode", "type": "platform",
                 "url": "https://leetcode.com", "description": "Coding practice platform"},
            ],
            "quick_wins": [
                "Review your weakest topics today",
                "Do 2-3 practice problems daily",
                "Schedule a mock interview this week",
            ],
            "long_term_goals": [
                "Build a strong project portfolio",
                "Contribute to open-source projects",
                "Earn a relevant certification",
            ],
            "motivational_message": "Keep going! Consistent practice leads to interview success.",
        }
        return self._parse_json_safe(raw, default)

    def _parse_json_safe(self, raw: str, default: dict) -> dict:
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    for key, val in default.items():
                        if key not in parsed:
                            parsed[key] = val
                    return parsed
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("JSON parsing failed: %s", e)
        return default
