"""
Question Generation Agent
Generates personalized technical, HR, and behavioral interview questions
based on the user's profile, domain, and difficulty level.
"""

import logging
import json
import re

logger = logging.getLogger(__name__)


class QuestionGenerationAgent:
    """Generates tailored interview questions using IBM Granite via watsonx.ai."""

    def __init__(self, watsonx_client, knowledge_agent, agent_instructions: dict):
        self.client = watsonx_client
        self.knowledge_agent = knowledge_agent
        self.instructions = agent_instructions
        self.model_id = agent_instructions.get("model_id", "ibm/granite-3-8b-instruct")

    def generate_questions(
        self,
        domain: str,
        job_role: str,
        skills: list[str],
        experience_years: int,
        question_type: str,
        difficulty: str,
        num_questions: int = 5,
        resume_summary: str = "",
        candidate_name: str = "",
    ) -> list[dict]:
        """Generate a set of interview questions and return structured list."""

        knowledge_ctx = self.knowledge_agent.build_knowledge_context(
            domain, job_role, skills, difficulty
        )

        style      = self.instructions.get("interview_style", "conversational")
        tone       = self.instructions.get("communication_tone", "professional")
        domain_focus = self.instructions.get("domain_specialization", domain)

        prompt = self._build_prompt(
            domain=domain,
            job_role=job_role,
            skills=skills,
            experience_years=experience_years,
            question_type=question_type,
            difficulty=difficulty,
            num_questions=num_questions,
            resume_summary=resume_summary,
            knowledge_ctx=knowledge_ctx,
            style=style,
            tone=tone,
            domain_focus=domain_focus,
            candidate_name=candidate_name,
        )

        raw_response = self.client.generate(
            prompt,
            max_new_tokens=min(200 + num_questions * 180, 2048),
            temperature=0.4,   # lower = more deterministic JSON
        )
        questions = self._parse_questions(raw_response, num_questions)

        # If we still don't have enough questions, pad with intelligent fallbacks
        if len(questions) < num_questions:
            questions = self._pad_with_fallbacks(
                questions, num_questions, job_role, domain, difficulty, question_type
            )

        return questions

    # ─── Prompt ──────────────────────────────────────────────────
    def _build_prompt(self, **kw) -> str:
        skills_str = ", ".join(kw["skills"]) if kw["skills"] else "general programming"
        name_part  = f"Candidate name: {kw['candidate_name']}\n" if kw["candidate_name"] else ""
        resume_part = (
            f"\nCANDIDATE RESUME SUMMARY:\n{kw['resume_summary'][:600]}\n"
            if kw["resume_summary"] else ""
        )
        knowledge_part = (
            f"\nRELEVANT KNOWLEDGE:\n{kw['knowledge_ctx'][:1000]}\n"
            if kw["knowledge_ctx"] else ""
        )
        n = kw["num_questions"]

        # Build explicit numbered placeholders so Granite knows exactly how many to produce
        placeholders = "\n".join(
            f'  {{"id": {i}, "question": "...", "type": "{kw["question_type"]}", '
            f'"difficulty": "{kw["difficulty"]}", "topic": "...", '
            f'"hints": "...", "expected_answer_outline": "..."}}'
            + ("," if i < n else "")
            for i in range(1, n + 1)
        )

        return f"""You are an expert {kw['domain']} interviewer. Style: {kw['style']}. Tone: {kw['tone']}.
{name_part}{resume_part}{knowledge_part}
TASK: Generate EXACTLY {n} interview questions for a {kw['job_role']} candidate.

Candidate profile:
- Skills: {skills_str}
- Experience: {kw['experience_years']} years
- Difficulty: {kw['difficulty']}
- Domain: {kw['domain_focus']}
- Question type: {kw['question_type']}

Rules:
1. You MUST output EXACTLY {n} questions — no more, no less.
2. Output ONLY a raw JSON array. No markdown, no code fences, no explanation text.
3. Each question must be unique and relevant to the candidate profile.
4. Mix conceptual, scenario-based, and practical questions.
5. For technical: cover algorithms, design, debugging, system concepts.
6. For behavioral: use STAR-method situations.
7. For HR: cover motivation, culture fit, career goals.

JSON array (fill in all {n} items):
[
{placeholders}
]"""

    # ─── Parser ───────────────────────────────────────────────────
    def _parse_questions(self, raw: str, expected_count: int) -> list[dict]:
        """Robustly extract the JSON array from model output."""

        # 1. Strip code fences
        text = re.sub(r"```(?:json)?|```", "", raw).strip()

        # 2. Try to find the outermost JSON array using bracket counting
        json_str = self._extract_outermost_array(text)

        if json_str:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    return self._validate_questions(parsed, expected_count)
            except json.JSONDecodeError:
                # Try to repair common Granite issues: trailing commas, unquoted keys
                repaired = self._repair_json(json_str)
                try:
                    parsed = json.loads(repaired)
                    if isinstance(parsed, list):
                        return self._validate_questions(parsed, expected_count)
                except json.JSONDecodeError as e:
                    logger.warning("JSON repair also failed: %s", e)

        # 3. Fallback: extract individual objects from the text
        return self._extract_objects_fallback(text, expected_count)

    def _extract_outermost_array(self, text: str) -> str | None:
        """Find the full JSON array by counting brackets from the first '['."""
        start = text.find("[")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None  # no balanced array found

    def _repair_json(self, text: str) -> str:
        """Fix common LLM JSON issues."""
        # Remove trailing commas before ] or }
        text = re.sub(r",\s*([}\]])", r"\1", text)
        # Replace single quotes with double quotes (naively)
        text = re.sub(r"'([^']*)'", r'"\1"', text)
        return text

    def _validate_questions(self, raw_list: list, expected_count: int) -> list[dict]:
        """Ensure each question object has all required fields."""
        validated = []
        for i, q in enumerate(raw_list, 1):
            if not isinstance(q, dict):
                continue
            # Accept if it has a question field (even spelled differently)
            text = q.get("question") or q.get("Question") or q.get("text") or ""
            if not text or len(str(text)) < 10:
                continue
            validated.append({
                "id":    q.get("id", i),
                "question": str(text),
                "type":  q.get("type", "mixed"),
                "difficulty": q.get("difficulty", "medium"),
                "topic": q.get("topic", "General"),
                "hints": q.get("hints", ""),
                "expected_answer_outline": q.get("expected_answer_outline", ""),
            })
        return validated[:expected_count]

    def _extract_objects_fallback(self, text: str, expected_count: int) -> list[dict]:
        """Extract individual JSON objects and plain numbered lines as a last resort."""
        questions = []

        # Try to find individual {...} objects
        for m in re.finditer(r"\{[^{}]+\}", text, re.DOTALL):
            try:
                obj = json.loads(self._repair_json(m.group()))
                text_val = obj.get("question") or obj.get("text") or ""
                if len(str(text_val)) > 10:
                    questions.append({
                        "id":    len(questions) + 1,
                        "question": str(text_val),
                        "type":  obj.get("type", "mixed"),
                        "difficulty": obj.get("difficulty", "medium"),
                        "topic": obj.get("topic", "General"),
                        "hints": "",
                        "expected_answer_outline": "",
                    })
            except json.JSONDecodeError:
                pass
            if len(questions) >= expected_count:
                break

        if questions:
            return questions

        # Final fallback: parse numbered/bulleted lines
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Match lines like "1." "1)" "- " "Q1:" or just long sentences
            cleaned = re.sub(r"^[\d\.\-\)\s:Qq]+", "", line).strip()
            if len(cleaned) > 20 and "?" in cleaned:
                questions.append({
                    "id":    len(questions) + 1,
                    "question": cleaned,
                    "type":  "mixed",
                    "difficulty": "medium",
                    "topic": "General",
                    "hints": "",
                    "expected_answer_outline": "",
                })
            if len(questions) >= expected_count:
                break

        return questions

    def _pad_with_fallbacks(
        self,
        existing: list[dict],
        target: int,
        job_role: str,
        domain: str,
        difficulty: str,
        question_type: str,
    ) -> list[dict]:
        """Add domain-specific fallback questions to reach the target count."""
        fallbacks = {
            "technical": [
                f"Walk me through how you would design a scalable REST API for a {job_role} project.",
                f"Explain a performance bottleneck you've encountered and how you resolved it.",
                f"Describe the difference between SQL and NoSQL databases and when to use each.",
                f"How do you approach debugging a complex production issue under time pressure?",
                f"What design patterns have you applied in real projects, and why?",
                f"Explain the concept of microservices and their trade-offs.",
                f"How do you ensure code quality and maintainability in your projects?",
                f"Describe your experience with cloud services and deployment pipelines.",
                f"How do you handle concurrency and thread safety in your applications?",
                f"What testing strategies do you use and why?",
            ],
            "behavioral": [
                "Tell me about a challenging project you led and what you learned from it.",
                "Describe a time you disagreed with a team member and how you resolved it.",
                "Give an example of when you had to learn a new technology quickly.",
                "Tell me about a time you failed and what you did about it.",
                "Describe how you prioritize tasks when everything seems urgent.",
                "Tell me about a time you went above and beyond for a project.",
                "How do you handle working with difficult stakeholders?",
                "Describe a situation where you had to make a decision with limited information.",
                "Tell me about your most successful collaboration experience.",
                "How do you stay updated with industry trends and new technologies?",
            ],
            "hr": [
                f"Why are you interested in the {job_role} position?",
                "Where do you see yourself professionally in 5 years?",
                "What are your greatest professional strengths?",
                "Describe your ideal work environment.",
                "How do you handle work-life balance during high-pressure periods?",
                "What motivates you most in your day-to-day work?",
                "Why are you looking to leave your current role?",
                "What do you know about our company and why do you want to join us?",
                "How would your previous colleagues describe your work style?",
                "What salary range are you expecting for this role?",
            ],
            "mixed": [
                f"What made you choose a career in {domain}?",
                f"How do you approach learning new tools and frameworks in {domain}?",
                f"Describe the most complex {domain} problem you have solved.",
                "How do you balance technical debt with feature delivery?",
                "Tell me about a time your technical decision positively impacted the business.",
                "What metrics do you use to measure the success of your work?",
                "How do you handle a situation where requirements change mid-project?",
                "What is your approach to code review and giving constructive feedback?",
                "Describe your experience mentoring junior developers.",
                "How do you ensure your solutions are accessible and inclusive?",
            ],
        }
        pool = fallbacks.get(question_type, fallbacks["mixed"])
        used_texts = {q["question"].lower()[:40] for q in existing}
        extra_id = len(existing) + 1

        for fb in pool:
            if len(existing) >= target:
                break
            if fb.lower()[:40] not in used_texts:
                existing.append({
                    "id":    extra_id,
                    "question": fb,
                    "type":  question_type,
                    "difficulty": difficulty,
                    "topic": "General",
                    "hints": "",
                    "expected_answer_outline": "",
                })
                extra_id += 1

        return existing
