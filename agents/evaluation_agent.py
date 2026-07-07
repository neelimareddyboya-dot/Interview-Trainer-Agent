"""
Answer Evaluation Agent
Evaluates user responses, assigns scores, provides AI-powered feedback,
identifies strengths and weaknesses, and suggests improvements.
"""

import logging
import json
import re

logger = logging.getLogger(__name__)


class AnswerEvaluationAgent:
    """Evaluates candidate answers using IBM Granite and provides structured feedback."""

    SCORE_WEIGHTS = {
        "technical_accuracy": 0.35,
        "depth_completeness": 0.25,
        "clarity_communication": 0.20,
        "practical_examples": 0.15,
        "problem_solving": 0.05,
    }

    def __init__(self, watsonx_client, knowledge_agent, agent_instructions: dict):
        self.client = watsonx_client
        self.knowledge_agent = knowledge_agent
        self.instructions = agent_instructions
        self.model_id = agent_instructions.get("model_id", "ibm/granite-13b-chat-v2")

    def evaluate_answer(
        self,
        question: str,
        user_answer: str,
        expected_outline: str,
        domain: str,
        difficulty: str,
        question_type: str,
    ) -> dict:
        """Evaluate a single answer and return structured feedback."""

        # Retrieve relevant context for better evaluation
        knowledge_ctx = self.knowledge_agent.retrieve_domain_knowledge(
            question, domain, top_k=3
        )

        feedback_format = self.instructions.get("feedback_format", "detailed")
        eval_criteria = self.instructions.get(
            "evaluation_criteria",
            "technical accuracy, completeness, clarity, examples"
        )

        prompt = self._build_eval_prompt(
            question=question,
            user_answer=user_answer,
            expected_outline=expected_outline,
            knowledge_ctx=knowledge_ctx,
            domain=domain,
            difficulty=difficulty,
            question_type=question_type,
            feedback_format=feedback_format,
            eval_criteria=eval_criteria,
        )

        raw_response = self.client.generate(prompt)
        evaluation = self._parse_evaluation(raw_response)
        evaluation["question"] = question
        evaluation["user_answer"] = user_answer
        evaluation["domain"] = domain
        return evaluation

    def _build_eval_prompt(self, **kwargs) -> str:
        knowledge_part = (
            f"\nRELEVANT KNOWLEDGE:\n{kwargs['knowledge_ctx'][:1200]}\n"
            if kwargs["knowledge_ctx"]
            else ""
        )
        expected_part = (
            f"\nEXPECTED ANSWER OUTLINE:\n{kwargs['expected_outline']}\n"
            if kwargs["expected_outline"]
            else ""
        )

        return f"""You are an expert {kwargs['domain']} interviewer evaluating a candidate's answer.

QUESTION: {kwargs['question']}

CANDIDATE'S ANSWER: {kwargs['user_answer']}
{expected_part}{knowledge_part}
Evaluation criteria: {kwargs['eval_criteria']}
Difficulty level: {kwargs['difficulty']}
Question type: {kwargs['question_type']}
Feedback format: {kwargs['feedback_format']}

Evaluate the answer thoroughly and return ONLY a valid JSON object:

{{
  "overall_score": <integer 0-100>,
  "technical_accuracy": <integer 0-100>,
  "depth_completeness": <integer 0-100>,
  "clarity_communication": <integer 0-100>,
  "practical_examples": <integer 0-100>,
  "problem_solving": <integer 0-100>,
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "improvements": ["improvement 1", "improvement 2", "improvement 3"],
  "ideal_answer_summary": "A concise summary of what an ideal answer would include",
  "detailed_feedback": "Detailed paragraph feedback on the answer quality",
  "follow_up_question": "A relevant follow-up question to probe deeper",
  "grade": "A/B/C/D/F",
  "recommendation": "hire/consider/pass"
}}"""

    def _parse_evaluation(self, raw: str) -> dict:
        """Parse evaluation JSON from model output with robust fallback."""
        default = {
            "overall_score": 50,
            "technical_accuracy": 50,
            "depth_completeness": 50,
            "clarity_communication": 50,
            "practical_examples": 50,
            "problem_solving": 50,
            "strengths": ["Attempted to answer the question"],
            "improvements": ["Provide more specific details", "Add concrete examples"],
            "ideal_answer_summary": "A comprehensive answer covering core concepts with examples.",
            "detailed_feedback": "The answer shows some understanding but needs more depth.",
            "follow_up_question": "Can you elaborate on your approach?",
            "grade": "C",
            "recommendation": "consider",
        }
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                # Merge with defaults for any missing keys
                for key, val in default.items():
                    if key not in parsed:
                        parsed[key] = val
                # Clamp scores
                for score_key in ["overall_score", "technical_accuracy",
                                   "depth_completeness", "clarity_communication",
                                   "practical_examples", "problem_solving"]:
                    if isinstance(parsed.get(score_key), (int, float)):
                        parsed[score_key] = max(0, min(100, int(parsed[score_key])))
                return parsed
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Evaluation parsing failed: %s", e)
        return default

    def calculate_session_score(self, evaluations: list[dict]) -> dict:
        """Calculate aggregate score for an entire interview session."""
        if not evaluations:
            return {"overall": 0, "breakdown": {}, "grade": "N/A"}

        totals = {
            "technical_accuracy": 0,
            "depth_completeness": 0,
            "clarity_communication": 0,
            "practical_examples": 0,
            "problem_solving": 0,
        }
        overall_total = 0
        count = len(evaluations)

        for ev in evaluations:
            overall_total += ev.get("overall_score", 0)
            for k in totals:
                totals[k] += ev.get(k, 0)

        avg_overall = round(overall_total / count)
        avg_breakdown = {k: round(v / count) for k, v in totals.items()}

        grade_map = [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D"), (0, "F")]
        grade = next(g for threshold, g in grade_map if avg_overall >= threshold)

        all_strengths = []
        all_improvements = []
        for ev in evaluations:
            all_strengths.extend(ev.get("strengths", []))
            all_improvements.extend(ev.get("improvements", []))

        return {
            "overall": avg_overall,
            "breakdown": avg_breakdown,
            "grade": grade,
            "top_strengths": list(dict.fromkeys(all_strengths))[:5],
            "top_improvements": list(dict.fromkeys(all_improvements))[:5],
            "questions_answered": count,
        }
