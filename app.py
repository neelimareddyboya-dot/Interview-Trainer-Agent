"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              AI-POWERED INTERVIEW TRAINER AGENT                              ║
║              Built with IBM watsonx.ai + IBM Granite Models                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  AGENT_INSTRUCTIONS — Customize agent behavior below                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash
)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from watsonx_client import WatsonxClient
from rag_pipeline import RAGPipeline
from agents import (
    InterviewKnowledgeAgent,
    QuestionGenerationAgent,
    AnswerEvaluationAgent,
    CareerGuidanceAgent,
)

# ════════════════════════════════════════════════════════════════════════════
#  AGENT_INSTRUCTIONS
#  ─────────────────────────────────────────────────────────────────────────
#  Edit these settings to fully customize the Interview Trainer Agent.
#  All values are passed down to every agent and control generation behavior.
# ════════════════════════════════════════════════════════════════════════════
AGENT_INSTRUCTIONS = {
    # ── Model ─────────────────────────────────────────────────────────────
    # Available on current plan: "meta-llama/llama-3-3-70b-instruct" (recommended)
    #                             "ibm/granite-8b-code-instruct"
    #                             "ibm/granite-guardian-3-8b"
    "model_id": "meta-llama/llama-3-3-70b-instruct",

    # ── Interview Style ────────────────────────────────────────────────────
    # Controls how questions are framed and the interview flow.
    # Options: "conversational" | "formal" | "socratic" | "stress_test" | "friendly"
    "interview_style": "conversational",

    # ── Difficulty Level ───────────────────────────────────────────────────
    # Default difficulty (users can override per session).
    # Options: "easy" | "medium" | "hard" | "adaptive"
    "default_difficulty": "medium",

    # ── Feedback Format ────────────────────────────────────────────────────
    # How detailed and structured the feedback should be.
    # Options: "brief" | "detailed" | "coaching" | "concise_bullets"
    "feedback_format": "detailed",

    # ── Communication Tone ─────────────────────────────────────────────────
    # The tone used in all agent responses.
    # Options: "professional" | "encouraging" | "direct" | "socratic" | "mentor"
    "communication_tone": "encouraging",

    # ── Evaluation Criteria ────────────────────────────────────────────────
    # Criteria considered during answer scoring (comma-separated concepts).
    "evaluation_criteria": (
        "technical accuracy, depth and completeness, "
        "clarity of communication, use of examples, problem-solving approach"
    ),

    # ── Domain Specialization ─────────────────────────────────────────────
    # Primary domain focus when domain is not specified by the user.
    # Options: "Software Engineering" | "Data Science" | "AI/ML" |
    #          "Web Development" | "DevOps" | "Cybersecurity" | "Product Management"
    "domain_specialization": "Software Engineering",

    # ── Question Distribution ─────────────────────────────────────────────
    # Default number of questions per interview session.
    "default_question_count": 5,
    # Default question type mix.
    # Options: "technical" | "behavioral" | "hr" | "mixed"
    "default_question_type": "mixed",

    # ── RAG Settings ─────────────────────────────────────────────────────
    # Number of knowledge chunks retrieved per query.
    "rag_top_k": 5,
    # Knowledge base directory path.
    "knowledge_base_dir": "knowledge_base",

    # ── Scoring Weights ────────────────────────────────────────────────────
    # Relative importance of each evaluation dimension (must sum to 1.0).
    "score_weights": {
        "technical_accuracy": 0.35,
        "depth_completeness": 0.25,
        "clarity_communication": 0.20,
        "practical_examples": 0.15,
        "problem_solving": 0.05,
    },

    # ── Career Guidance Depth ─────────────────────────────────────────────
    # How detailed the career guidance recommendations should be.
    # Options: "overview" | "standard" | "deep_dive"
    "guidance_depth": "standard",

    # ── Interview Persona ─────────────────────────────────────────────────
    # Agent persona / interviewer name shown in the UI.
    "agent_name": "Alex",
    "agent_title": "AI Interview Coach",

    # ── Supported Domains ─────────────────────────────────────────────────
    # List of domains available in the UI for the user to select.
    "supported_domains": [
        "Software Engineering",
        "Data Science",
        "AI/ML Engineering",
        "Web Development",
        "DevOps & Cloud",
        "Cybersecurity",
        "Product Management",
        "Mobile Development",
        "Database Engineering",
        "QA & Testing",
    ],
}
# ════════════════════════════════════════════════════════════════════════════
#  END OF AGENT_INSTRUCTIONS
# ════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────────
#  Environment & Logging
# ─────────────────────────────────────────────────────────────────────────────
# override=True ensures .env values always win over any stale system env variables.
load_dotenv(override=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Flask Application Setup
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", 24))
)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_SIZE_MB", 10)) * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "static/uploads")

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
Path("data").mkdir(exist_ok=True)

CORS(app)

# ─────────────────────────────────────────────────────────────────────────────
#  Initialise IBM watsonx.ai, RAG and Multi-Agent System
# ─────────────────────────────────────────────────────────────────────────────
IBM_API_KEY = os.getenv("IBM_API_KEY", "")
IBM_PROJECT_ID = os.getenv("IBM_PROJECT_ID", "")
IBM_WATSONX_URL = os.getenv("IBM_WATSONX_URL", "")

# ── Startup diagnostic: confirm which credentials were loaded (values are masked) ──
def _mask(value: str, show: int = 6) -> str:
    """Show only the first `show` characters; mask the rest."""
    return value[:show] + "***" if len(value) > show else ("(empty)" if not value else value)

logger.info("IBM_API_KEY      loaded: %s", _mask(IBM_API_KEY))
logger.info("IBM_PROJECT_ID   loaded: %s", _mask(IBM_PROJECT_ID))
logger.info("IBM_WATSONX_URL  loaded: %s", IBM_WATSONX_URL or "(empty)")
if not IBM_API_KEY or not IBM_PROJECT_ID or not IBM_WATSONX_URL:
    logger.warning(
        "One or more IBM credentials are missing — watsonx.ai calls will fail. "
        "Check your .env file and ensure load_dotenv(override=True) is applied."
    )

watsonx = WatsonxClient(
    api_key=IBM_API_KEY,
    project_id=IBM_PROJECT_ID,
    base_url=IBM_WATSONX_URL,
    model_id=AGENT_INSTRUCTIONS["model_id"],
)

rag = RAGPipeline(knowledge_base_dir=AGENT_INSTRUCTIONS["knowledge_base_dir"])

knowledge_agent = InterviewKnowledgeAgent(watsonx, rag, AGENT_INSTRUCTIONS)
question_agent = QuestionGenerationAgent(watsonx, knowledge_agent, AGENT_INSTRUCTIONS)
evaluation_agent = AnswerEvaluationAgent(watsonx, knowledge_agent, AGENT_INSTRUCTIONS)
guidance_agent = CareerGuidanceAgent(watsonx, knowledge_agent, AGENT_INSTRUCTIONS)

# ─────────────────────────────────────────────────────────────────────────────
#  In-memory session store (replace with Redis/DB for production)
# ─────────────────────────────────────────────────────────────────────────────
INTERVIEW_STORE: dict[str, dict] = {}
HISTORY_STORE: list[dict] = []


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_resume(filepath: str) -> str:
    """Extract text from uploaded resume file."""
    ext = filepath.rsplit(".", 1)[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            import PyPDF2
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = " ".join(
                    page.extract_text() or "" for page in reader.pages
                )
        elif ext in ("docx", "doc"):
            from docx import Document
            doc = Document(filepath)
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
    except Exception as e:
        logger.error("Resume parsing error: %s", e)
    return text.strip()


def build_session_summary(interview_id: str) -> dict:
    """Summarise a completed interview session."""
    session_data = INTERVIEW_STORE.get(interview_id, {})
    evaluations = session_data.get("evaluations", [])
    score = evaluation_agent.calculate_session_score(evaluations)
    return {
        "interview_id": interview_id,
        "domain": session_data.get("domain", ""),
        "job_role": session_data.get("job_role", ""),
        "question_count": len(evaluations),
        "score": score,
        "completed_at": datetime.now().isoformat(),
        "questions_answered": len(evaluations),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Routes — Pages
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template(
        "index.html",
        agent_name=AGENT_INSTRUCTIONS["agent_name"],
        agent_title=AGENT_INSTRUCTIONS["agent_title"],
        domains=AGENT_INSTRUCTIONS["supported_domains"],
    )


@app.route("/dashboard")
def dashboard():
    history = HISTORY_STORE[-20:][::-1]  # latest 20, newest first
    return render_template(
        "dashboard.html",
        history=history,
        agent_name=AGENT_INSTRUCTIONS["agent_name"],
        domains=AGENT_INSTRUCTIONS["supported_domains"],
    )


@app.route("/interview")
def interview():
    return render_template(
        "interview.html",
        agent_name=AGENT_INSTRUCTIONS["agent_name"],
        agent_title=AGENT_INSTRUCTIONS["agent_title"],
        domains=AGENT_INSTRUCTIONS["supported_domains"],
        default_difficulty=AGENT_INSTRUCTIONS["default_difficulty"],
        default_question_count=AGENT_INSTRUCTIONS["default_question_count"],
    )


@app.route("/results/<interview_id>")
def results(interview_id):
    if interview_id not in INTERVIEW_STORE:
        flash("Session not found.", "warning")
        return redirect(url_for("dashboard"))
    session_data = INTERVIEW_STORE[interview_id]
    score = evaluation_agent.calculate_session_score(session_data.get("evaluations", []))
    return render_template(
        "results.html",
        interview_id=interview_id,
        session_data=session_data,
        score=score,
        agent_name=AGENT_INSTRUCTIONS["agent_name"],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Routes — API
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def api_health():
    watsonx_status = watsonx.health_check()
    return jsonify({
        "status": "ok",
        "rag_chunks": len(rag.chunks),
        "watsonx": watsonx_status,
        "model": AGENT_INSTRUCTIONS["model_id"],
        "agent_name": AGENT_INSTRUCTIONS["agent_name"],
    })


@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    """Upload and parse a resume file, add content to RAG index."""
    if "resume" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["resume"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Allowed: PDF, DOCX, TXT"}), 400

    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    resume_text = parse_resume(filepath)
    if not resume_text:
        return jsonify({"error": "Could not extract text from resume"}), 422

    # Index resume content in RAG for personalised retrieval
    chunks_added = rag.add_document(resume_text, source="user_resume")
    session["resume_text"] = resume_text[:3000]  # keep first 3k chars in session
    session["resume_filename"] = file.filename

    return jsonify({
        "success": True,
        "filename": file.filename,
        "text_length": len(resume_text),
        "rag_chunks_added": chunks_added,
        "preview": resume_text[:300] + "..." if len(resume_text) > 300 else resume_text,
    })


@app.route("/api/start-interview", methods=["POST"])
def start_interview():
    """Initialise a new interview session and generate first questions."""
    try:
        data = request.get_json(force=True) or {}
        domain = data.get("domain", AGENT_INSTRUCTIONS["domain_specialization"])
        job_role = data.get("job_role", "Software Engineer")
        skills = data.get("skills", [])
        experience = int(data.get("experience_years", 2))
        difficulty = data.get("difficulty", AGENT_INSTRUCTIONS["default_difficulty"])
        question_type = data.get("question_type", AGENT_INSTRUCTIONS["default_question_type"])
        num_questions = int(data.get("num_questions", AGENT_INSTRUCTIONS["default_question_count"]))
        resume_text = data.get("resume_text", session.get("resume_text", ""))
        candidate_name = data.get("candidate_name", "").strip()

        interview_id = str(uuid.uuid4())[:8]

        questions = question_agent.generate_questions(
            domain=domain,
            job_role=job_role,
            skills=skills,
            experience_years=experience,
            question_type=question_type,
            difficulty=difficulty,
            num_questions=num_questions,
            resume_summary=resume_text,
            candidate_name=candidate_name,
        )

        # Guarantee we always have at least one question even if generation failed
        if not questions:
            questions = [{
                "id": 1,
                "question": f"Tell me about your experience as a {job_role} and the most impactful project you have worked on.",
                "type": question_type,
                "difficulty": difficulty,
                "topic": "General Experience",
                "hints": "",
                "expected_answer_outline": "Candidate should describe a specific project with measurable impact.",
            }]

        interview_tips = guidance_agent.get_interview_tips(domain, question_type)

        INTERVIEW_STORE[interview_id] = {
            "domain": domain,
            "job_role": job_role,
            "skills": skills,
            "experience_years": experience,
            "difficulty": difficulty,
            "question_type": question_type,
            "questions": questions,
            "evaluations": [],
            "current_index": 0,
            "started_at": datetime.now().isoformat(),
            "resume_text": resume_text,
            "tips": interview_tips,
            "candidate_name": candidate_name,
        }

        greeting = f"Hi {candidate_name}! " if candidate_name else "Hi! "
        return jsonify({
            "interview_id": interview_id,
            "questions": questions,
            "total_questions": len(questions),
            "tips": interview_tips,
            "candidate_name": candidate_name,
            "agent_intro": (
                f"{greeting}I'm {AGENT_INSTRUCTIONS['agent_name']}, your AI interview coach. "
                f"I've prepared {len(questions)} {question_type} questions for your "
                f"{job_role} interview in {domain}. Take your time and answer as thoroughly "
                f"as you can. Good luck! 🎯"
            ),
        })
    except Exception as e:
        logger.exception("start_interview error")
        return jsonify({"error": f"Failed to start interview: {str(e)}"}), 500


@app.route("/api/submit-answer", methods=["POST"])
def submit_answer():
    """Evaluate a user's answer and return AI feedback."""
    try:
        data = request.get_json(force=True) or {}
        interview_id = data.get("interview_id")
        question_id = int(data.get("question_id", 0))
        user_answer = data.get("answer", "").strip()

        if not interview_id or interview_id not in INTERVIEW_STORE:
            return jsonify({"error": "Invalid interview session"}), 404
        if not user_answer:
            return jsonify({"error": "Answer cannot be empty"}), 400

        session_data = INTERVIEW_STORE[interview_id]
        questions = session_data["questions"]
        question_obj = next((q for q in questions if q.get("id") == question_id), None)
        if not question_obj:
            # Fallback: match by position index
            question_obj = questions[question_id - 1] if 0 < question_id <= len(questions) else None
        if not question_obj:
            return jsonify({"error": "Question not found"}), 404

        evaluation = evaluation_agent.evaluate_answer(
            question=question_obj["question"],
            user_answer=user_answer,
            expected_outline=question_obj.get("expected_answer_outline", ""),
            domain=session_data["domain"],
            difficulty=session_data["difficulty"],
            question_type=question_obj.get("type", "mixed"),
        )

        evaluation["question_id"] = question_id
        session_data["evaluations"].append(evaluation)
        session_data["current_index"] = question_id

        return jsonify({
            "evaluation": evaluation,
            "questions_answered": len(session_data["evaluations"]),
            "total_questions": len(questions),
        })
    except Exception as e:
        logger.exception("submit_answer error")
        return jsonify({"error": f"Failed to evaluate answer: {str(e)}"}), 500


@app.route("/api/finish-interview", methods=["POST"])
def finish_interview():
    """Finalise interview and generate comprehensive career guidance."""
    try:
        data = request.get_json(force=True) or {}
        interview_id = data.get("interview_id")

        if not interview_id or interview_id not in INTERVIEW_STORE:
            return jsonify({"error": "Invalid interview session"}), 404

        session_data = INTERVIEW_STORE[interview_id]
        score = evaluation_agent.calculate_session_score(session_data.get("evaluations", []))
        weak_areas = score.get("top_improvements", [])

        guidance = guidance_agent.generate_career_advice(
            domain=session_data["domain"],
            job_role=session_data["job_role"],
            skills=session_data.get("skills", []),
            experience_years=session_data.get("experience_years", 2),
            session_score=score,
            weak_areas=weak_areas,
        )

        # Save to history
        history_entry = {
            "interview_id": interview_id,
            "domain": session_data["domain"],
            "job_role": session_data["job_role"],
            "score": score,
            "guidance": guidance,
            "questions_answered": len(session_data.get("evaluations", [])),
            "completed_at": datetime.now().isoformat(),
            "difficulty": session_data.get("difficulty", "medium"),
        }
        HISTORY_STORE.append(history_entry)
        session_data["guidance"] = guidance
        session_data["final_score"] = score

        return jsonify({
            "interview_id": interview_id,
            "score": score,
            "guidance": guidance,
            "history_saved": True,
        })
    except Exception as e:
        logger.exception("finish_interview error")
        return jsonify({"error": f"Failed to finish interview: {str(e)}"}), 500


@app.route("/api/get-session/<interview_id>")
def get_session(interview_id):
    """Retrieve full session data for the results page."""
    if interview_id not in INTERVIEW_STORE:
        return jsonify({"error": "Session not found"}), 404
    data = INTERVIEW_STORE[interview_id]
    return jsonify({
        "interview_id": interview_id,
        "domain": data.get("domain"),
        "job_role": data.get("job_role"),
        "questions": data.get("questions", []),
        "evaluations": data.get("evaluations", []),
        "final_score": data.get("final_score", {}),
        "guidance": data.get("guidance", {}),
        "started_at": data.get("started_at"),
    })


@app.route("/api/history")
def get_history():
    """Return last 20 interview sessions."""
    return jsonify({"history": HISTORY_STORE[-20:][::-1]})


@app.route("/api/analyze-skills", methods=["POST"])
def analyze_skills():
    """Perform skill gap analysis for a role."""
    data = request.get_json(force=True)
    domain = data.get("domain", "Software Engineering")
    job_role = data.get("job_role", "Software Engineer")
    skills = data.get("skills", [])
    jd = data.get("job_description", "")

    analysis = guidance_agent.analyze_skill_gaps(domain, job_role, skills, jd)
    return jsonify({"analysis": analysis})


@app.route("/api/chat", methods=["POST"])
def chat():
    """General-purpose chat endpoint for follow-up questions."""
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    interview_id = data.get("interview_id", "")
    context = ""

    if interview_id and interview_id in INTERVIEW_STORE:
        sd = INTERVIEW_STORE[interview_id]
        context = (
            f"Context: interviewing for {sd.get('job_role')} in "
            f"{sd.get('domain')} domain, difficulty: {sd.get('difficulty')}."
        )

    knowledge_ctx = knowledge_agent.retrieve_domain_knowledge(message, domain="general", top_k=3)
    tone = AGENT_INSTRUCTIONS["communication_tone"]

    prompt = f"""You are {AGENT_INSTRUCTIONS['agent_name']}, an expert AI interview coach with an {tone} tone.
{context}

Knowledge context:
{knowledge_ctx[:800]}

User question: {message}

Provide a helpful, accurate, and concise response. Be specific and actionable."""

    response = watsonx.generate(prompt, max_new_tokens=512, temperature=0.6)
    return jsonify({
        "response": response or "I'm here to help! Could you rephrase your question?",
        "agent": AGENT_INSTRUCTIONS["agent_name"],
    })


@app.route("/api/domains")
def get_domains():
    return jsonify({"domains": AGENT_INSTRUCTIONS["supported_domains"]})


# ─────────────────────────────────────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────────────────────────────────────
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": f"File too large. Max {os.getenv('MAX_UPLOAD_SIZE_MB', 10)} MB."}), 413


@app.errorhandler(404)
def not_found(e):
    return render_template("index.html", agent_name=AGENT_INSTRUCTIONS["agent_name"],
                           domains=AGENT_INSTRUCTIONS["supported_domains"]), 404


@app.errorhandler(500)
def server_error(e):
    logger.exception("Internal server error")
    return jsonify({"error": "Internal server error. Please try again."}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    logger.info(
        "Starting Interview Trainer Agent on port %d (debug=%s)", port, debug
    )
    logger.info(
        "Model: %s | Style: %s | Tone: %s",
        AGENT_INSTRUCTIONS["model_id"],
        AGENT_INSTRUCTIONS["interview_style"],
        AGENT_INSTRUCTIONS["communication_tone"],
    )
    app.run(host="0.0.0.0", port=port, debug=debug)
