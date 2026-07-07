# 🎯 AI-Powered Interview Trainer Agent

[![IBM watsonx.ai](https://img.shields.io/badge/IBM-watsonx.ai-0062ff?logo=ibm)](https://www.ibm.com/watsonx)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)](https://flask.palletsprojects.com)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952b3?logo=bootstrap)](https://getbootstrap.com)

An enterprise-grade AI-powered interview coaching platform built with **IBM watsonx.ai** and **IBM Granite models**. Features a multi-agent architecture, Retrieval-Augmented Generation (RAG), real-time scoring, and comprehensive career guidance.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Flask Web Application                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │               AGENT_INSTRUCTIONS                  │  │
│  │    (Model · Style · Tone · Difficulty · Domains)  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Knowledge   │  │  Question    │  │  Evaluation  │  │
│  │    Agent     │  │    Agent     │  │    Agent     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│  ┌──────▼─────────────────▼─────────────────▼───────┐  │
│  │              Career Guidance Agent                │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │     RAG Pipeline (FAISS + Sentence Transformers)  │  │
│  │   knowledge_base/ → chunks → embeddings → index  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           IBM watsonx.ai Client                   │  │
│  │        (IAM Auth + Granite Models)                │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Multi-Agent System

| Agent | Role |
|-------|------|
| **Interview Knowledge Agent** | Retrieves domain-specific interview knowledge from RAG |
| **Question Generation Agent** | Creates personalized questions based on resume + role |
| **Answer Evaluation Agent** | Scores answers across 5 dimensions, provides feedback |
| **Career Guidance Agent** | Analyzes gaps, builds learning roadmap, recommends resources |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <repo-url>
cd interview-trainer-agent
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your IBM Cloud credentials:

```env
IBM_API_KEY=your_ibm_cloud_api_key
IBM_PROJECT_ID=your_watsonx_project_id
IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com
FLASK_SECRET_KEY=your-random-secret-key
```

#### Getting IBM Credentials:
1. Sign up at [cloud.ibm.com](https://cloud.ibm.com)
2. Create an IBM watsonx.ai service instance
3. Go to **Manage → Access → API Keys** → Create API key
4. In watsonx.ai, create a project and copy the **Project ID** from project settings

### 4. Run the Application

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## ⚙️ Customizing Agent Behavior (AGENT_INSTRUCTIONS)

The `AGENT_INSTRUCTIONS` dict in `app.py` is your central control panel:

```python
AGENT_INSTRUCTIONS = {
    # IBM Granite model to use
    "model_id": "ibm/granite-13b-chat-v2",

    # Interview style: "conversational" | "formal" | "stress_test" | "socratic"
    "interview_style": "conversational",

    # Default difficulty: "easy" | "medium" | "hard" | "adaptive"
    "default_difficulty": "medium",

    # Feedback detail: "brief" | "detailed" | "coaching" | "concise_bullets"
    "feedback_format": "detailed",

    # Agent tone: "professional" | "encouraging" | "direct" | "mentor"
    "communication_tone": "encouraging",

    # Primary domain when user doesn't specify
    "domain_specialization": "Software Engineering",

    # Scoring weight distribution (must sum to 1.0)
    "score_weights": {
        "technical_accuracy": 0.35,
        "depth_completeness": 0.25,
        "clarity_communication": 0.20,
        "practical_examples": 0.15,
        "problem_solving": 0.05,
    },

    # Agent persona shown in UI
    "agent_name": "Alex",
    "agent_title": "AI Interview Coach",
}
```

---

## 📚 Knowledge Base

The RAG pipeline indexes text files from the `knowledge_base/` directory:

| File | Coverage |
|------|----------|
| `software_engineering.txt` | DSA, System Design, OOP, SOLID, Design Patterns |
| `data_science_ml.txt` | ML algorithms, evaluation metrics, MLOps |
| `ai_ml_advanced.txt` | LLMs, Transformers, RAG, Prompt Engineering |
| `web_development.txt` | Frontend, Backend, React, Node.js, Security |
| `career_guidance.txt` | Career paths, resume tips, negotiation |
| `hr_behavioral.txt` | STAR method, behavioral questions, culture fit |

### Adding Custom Knowledge

1. Create a `.txt` file in `knowledge_base/`
2. Delete `data/rag_index.pkl` to force re-indexing
3. Restart the application

---

## 🔌 API Reference

### Start Interview
```
POST /api/start-interview
{
  "domain": "Software Engineering",
  "job_role": "Senior Backend Engineer",
  "skills": ["Python", "PostgreSQL", "Docker"],
  "experience_years": 5,
  "difficulty": "hard",
  "question_type": "mixed",
  "num_questions": 5
}
```

### Submit Answer
```
POST /api/submit-answer
{
  "interview_id": "abc12345",
  "question_id": 1,
  "answer": "Your answer text here..."
}
```

### Finish Interview
```
POST /api/finish-interview
{ "interview_id": "abc12345" }
```

### Upload Resume
```
POST /api/upload-resume
Content-Type: multipart/form-data
resume: <file>
```

### Get History
```
GET /api/history
```

---

## 🐳 Docker Deployment

### Build & Run

```bash
docker build -t interview-trainer .
docker run -p 5000:5000 --env-file .env interview-trainer
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
```

---

## ☁️ Deploy to IBM Cloud Code Engine

### Prerequisites
- IBM Cloud CLI: [cloud.ibm.com/docs/cli](https://cloud.ibm.com/docs/cli)
- Container Registry access

### Steps

```bash
# 1. Login to IBM Cloud
ibmcloud login --sso

# 2. Target Code Engine project
ibmcloud ce project create --name interview-trainer-project
ibmcloud ce project select --name interview-trainer-project

# 3. Create secret for environment variables
ibmcloud ce secret create \
  --name interview-trainer-secrets \
  --from-env-file .env

# 4. Deploy the application
ibmcloud ce application create \
  --name interview-trainer \
  --image us.icr.io/your-namespace/interview-trainer:latest \
  --env-from-secret interview-trainer-secrets \
  --port 5000 \
  --cpu 1 \
  --memory 4G \
  --min-scale 1 \
  --max-scale 5

# 5. Get the URL
ibmcloud ce application get --name interview-trainer --output url
```

---

## ☁️ Deploy to IBM Cloud Foundry

```bash
# manifest.yml
---
applications:
- name: interview-trainer-agent
  memory: 2G
  instances: 1
  buildpack: python_buildpack
  command: gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app
  env:
    IBM_API_KEY: ((IBM_API_KEY))
    IBM_PROJECT_ID: ((IBM_PROJECT_ID))
    IBM_WATSONX_URL: https://us-south.ml.cloud.ibm.com
    FLASK_SECRET_KEY: ((FLASK_SECRET_KEY))

# Deploy:
ibmcloud cf push
```

---

## 🗂️ Project Structure

```
interview-trainer-agent/
├── app.py                    # Main Flask app + AGENT_INSTRUCTIONS
├── watsonx_client.py         # IBM watsonx.ai REST client
├── rag_pipeline.py           # FAISS-based RAG implementation
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── __init__.py
│   ├── knowledge_agent.py    # Interview Knowledge Agent
│   ├── question_agent.py     # Question Generation Agent
│   ├── evaluation_agent.py   # Answer Evaluation Agent
│   └── guidance_agent.py     # Career Guidance Agent
│
├── knowledge_base/
│   ├── software_engineering.txt
│   ├── data_science_ml.txt
│   ├── ai_ml_advanced.txt
│   ├── web_development.txt
│   ├── career_guidance.txt
│   └── hr_behavioral.txt
│
├── templates/
│   ├── index.html            # Landing page
│   ├── interview.html        # Interview session page
│   ├── results.html          # Results & guidance page
│   └── dashboard.html        # Performance dashboard
│
├── static/
│   ├── css/style.css         # Complete stylesheet (light + dark mode)
│   ├── js/app.js             # Shared utilities, theme, toasts
│   ├── js/interview.js       # Interview session logic
│   ├── js/results.js         # Results animations
│   ├── js/dashboard.js       # Dashboard charts & data
│   └── uploads/              # Resume uploads
│
└── data/
    ├── rag_index.pkl         # RAG vector index cache (auto-generated)
    └── rag_index.pkl.faiss   # FAISS index file (auto-generated)
```

---

## 🔒 Security Notes

- **Never commit `.env`** to version control
- Use environment variables or IBM Secrets Manager in production
- The `FLASK_SECRET_KEY` should be a long random string
- Resume uploads are stored locally; consider IBM Cloud Object Storage for production
- Rate-limit the API endpoints before public deployment

---

## 🤖 Supported IBM Granite Models

| Model ID | Best For |
|----------|----------|
| `ibm/granite-13b-chat-v2` | General interview coaching (default) |
| `ibm/granite-13b-instruct-v2` | Structured instructions and evaluations |
| `ibm/granite-34b-code-instruct` | Technical/coding interview questions |
| `ibm/granite-20b-multilingual` | Non-English interviews |

Change in `AGENT_INSTRUCTIONS["model_id"]` in `app.py`.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

Built with ❤️ using **IBM watsonx.ai** and **IBM Granite** models.
