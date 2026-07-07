/**
 * interview.js — Interview Trainer Agent
 * Handles setup, resume upload, question flow, answer evaluation,
 * live scoring, and the persistent help-chat (doubt clearing) panel.
 * IBM watsonx.ai + IBM Granite
 */

/* ─── State ──────────────────────────────────────────────────── */
const state = {
  interviewId: null,
  questions: [],
  currentQIndex: 0,
  answeredSet: new Set(),
  evaluations: [],
  liveScores: { overall: [], technical: [], communication: [] },
  resumeText: '',
  candidateName: '',
  isSubmitting: false,  // guard against double-submit
};

const $ = id => document.getElementById(id);

/* ─── Resume Upload ──────────────────────────────────────────── */
const uploadZone = $('uploadZone');
const resumeFile = $('resumeFile');

if (uploadZone) {
  uploadZone.addEventListener('dragover', e => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
  });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
  uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleResumeUpload(file);
  });
}

if (resumeFile) {
  resumeFile.addEventListener('change', e => {
    if (e.target.files[0]) handleResumeUpload(e.target.files[0]);
  });
}

async function handleResumeUpload(file) {
  const statusEl = $('uploadStatus');
  if (statusEl) statusEl.textContent = `Uploading ${file.name}…`;
  if (uploadZone) uploadZone.classList.add('dragover');

  const formData = new FormData();
  formData.append('resume', file);

  try {
    const res  = await fetch('/api/upload-resume', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');

    state.resumeText = data.preview || '';
    if (uploadZone) {
      uploadZone.innerHTML = `
        <i class="bi bi-file-check fs-3 text-success"></i>
        <p class="mb-0 small mt-1 fw-semibold text-success">${escapeHtml(file.name)}</p>
        <p style="font-size:11px" class="text-muted">${data.text_length} chars extracted · ${data.rag_chunks_added} chunks indexed</p>
      `;
      uploadZone.classList.remove('dragover');
      uploadZone.classList.add('uploaded');
    }
    showToast(`✅ Resume indexed — ${data.rag_chunks_added} knowledge chunks added`, 'success');
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Upload failed — try again';
    if (uploadZone) uploadZone.classList.remove('dragover');
    showToast(err.message, 'error');
  }
}

/* ─── Start Interview ────────────────────────────────────────── */
async function startInterview() {
  const candidateName = ($('candidateName')?.value || '').trim();
  const jobRole       = ($('jobRole')?.value || 'Software Engineer').trim();
  const domain        = $('domainSelect')?.value || 'Software Engineering';
  const skills        = ($('skillsInput')?.value || '').split(',').map(s => s.trim()).filter(Boolean);
  const experience    = parseInt($('experienceYears')?.value) || 2;
  const difficulty    = document.querySelector('input[name="difficulty"]:checked')?.value || 'medium';
  const questionType  = $('questionType')?.value || 'mixed';
  const numQuestions  = parseInt($('questionCount')?.value) || 5;

  state.candidateName = candidateName;

  const startBtn = $('startBtn');
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating Questions…';
  }
  showTypingInHeader(true);

  try {
    const data = await apiFetch('/api/start-interview', {
      method: 'POST',
      body: {
        domain,
        job_role: jobRole,
        skills,
        experience_years: experience,
        difficulty,
        question_type: questionType,
        num_questions: numQuestions,
        resume_text: state.resumeText,
        candidate_name: candidateName,
      },
    });

    state.interviewId = data.interview_id;
    state.questions   = data.questions || [];
    state.currentQIndex = 0;
    state.answeredSet   = new Set();
    state.evaluations   = [];

    if (!state.questions.length) {
      throw new Error('No questions were generated. Please try again.');
    }

    // Session badge
    const badge = $('sessionBadge');
    if (badge) {
      badge.textContent = candidateName
        ? `${candidateName} · ${state.interviewId}`
        : `Session: ${state.interviewId}`;
      badge.classList.remove('d-none');
    }

    // Switch panels
    $('setupPanel')?.classList.add('d-none');
    $('progressPanel')?.classList.remove('d-none');
    if (data.tips?.length) {
      renderTips(data.tips);
      $('tipsPanel')?.classList.remove('d-none');
    }

    // Switch to chat view
    $('welcomeScreen')?.classList.add('d-none');
    const ci = $('chatInterface');
    if (ci) { ci.classList.remove('d-none'); ci.style.display = 'flex'; }

    // Update progress nav
    updateProgress();

    // Greet + ask first question
    const greeting = candidateName ? `Hi ${escapeHtml(candidateName)}! ` : 'Hi! ';
    appendMessage('ai',
      `${greeting}I'm your AI interview coach. I've prepared <strong>${state.questions.length}</strong> ` +
      `<em>${questionType}</em> questions for your <strong>${escapeHtml(jobRole)}</strong> interview in ` +
      `<strong>${escapeHtml(domain)}</strong>. Take your time and answer thoroughly. Good luck! 🎯`,
      true
    );
    await delay(700);
    askQuestion(0);

  } catch (err) {
    showToast('Failed to start interview: ' + err.message, 'error');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerHTML = '<i class="bi bi-play-fill me-2"></i>Start Interview';
    }
  } finally {
    showTypingInHeader(false);
  }
}

/* ─── Ask a Question ─────────────────────────────────────────── */
function askQuestion(index) {
  if (index >= state.questions.length) {
    appendMessage('system', '🎉 All questions answered! Click "Finish & Get Results" for your full report.');
    const fb = $('finishBtn');
    if (fb) fb.disabled = false;
    disableInput();
    return;
  }

  const q = state.questions[index];
  state.currentQIndex = index;
  updateProgress();

  const typeColors = { technical: 'primary', behavioral: 'success', hr: 'info', mixed: 'secondary' };
  const typeColor  = typeColors[q.type] || 'secondary';
  const topicBadge = q.topic && q.topic !== 'General' ? `<span class="badge bg-light text-dark border ms-1">${escapeHtml(q.topic)}</span>` : '';

  const qHtml = `
    <div class="question-card p-0">
      <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
        <span class="badge bg-${typeColor}">${escapeHtml(q.type || 'question')}</span>
        <span class="badge bg-light text-dark border">${escapeHtml(q.difficulty || 'medium')}</span>
        ${topicBadge}
        <span class="ms-auto small text-muted fw-semibold">Q${index + 1} of ${state.questions.length}</span>
      </div>
      <p class="mb-0 fw-medium" style="line-height:1.55">${escapeHtml(q.question)}</p>
    </div>
  `;
  appendMessage('ai', qHtml, true);

  // Enable input
  enableInput();
  const ta = $('userAnswer');
  if (ta) { ta.value = ''; ta.focus(); }
  updateWordCount();

  const badge = $('currentQBadge');
  if (badge) badge.textContent = `Q${index + 1}/${state.questions.length}`;
}

/* ─── Submit Answer ──────────────────────────────────────────── */
async function submitAnswer() {
  if (state.isSubmitting) return;
  const answer = ($('userAnswer')?.value || '').trim();
  if (!answer) { showToast('Please type your answer first', 'warning'); return; }
  if (!state.interviewId || state.currentQIndex >= state.questions.length) return;

  state.isSubmitting = true;
  const q = state.questions[state.currentQIndex];

  appendMessage('user', answer);
  disableInput();
  updateWordCount();
  showTypingInHeader(true);

  try {
    const data = await apiFetch('/api/submit-answer', {
      method: 'POST',
      body: {
        interview_id: state.interviewId,
        question_id: q.id,
        answer,
      },
    });

    const ev = data.evaluation;
    state.evaluations.push(ev);
    state.answeredSet.add(state.currentQIndex);

    // Update right panel evaluation
    renderEvaluation(ev);

    // Auto-switch to Feedback tab to show scores
    const feedbackTab = document.getElementById('feedback-tab');
    if (feedbackTab) {
      const bsTab = new bootstrap.Tab(feedbackTab);
      bsTab.show();
    }

    // Brief score chip in chat
    appendMessage('ai', buildScoreChip(ev), true);

    // Update sidebar scores
    updateLiveScores(ev);
    updateProgress();

    // Move to next question
    await delay(1400);
    const nextIndex = state.currentQIndex + 1;
    if (nextIndex < state.questions.length) {
      appendMessage('system', `Moving to question ${nextIndex + 1} of ${state.questions.length}…`);
      await delay(500);
      askQuestion(nextIndex);
    } else {
      appendMessage('system', '🎉 All questions answered! Click "Finish & Get Results" for your full report.');
      const fb = $('finishBtn');
      if (fb) fb.disabled = false;
      disableInput();
    }

  } catch (err) {
    showToast('Evaluation error: ' + err.message, 'error');
    enableInput();
  } finally {
    showTypingInHeader(false);
    state.isSubmitting = false;
  }
}

/* ─── Finish Interview ───────────────────────────────────────── */
async function finishInterview() {
  if (!state.interviewId) return;
  const fb = $('finishBtn');
  if (fb) { fb.disabled = true; fb.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating Report…'; }
  showLoading('Generating your full performance report and career guidance…');

  try {
    const data = await apiFetch('/api/finish-interview', {
      method: 'POST',
      body: { interview_id: state.interviewId },
    });
    removeLoading();
    showToast('Interview complete! Redirecting to your results…', 'success', 2000);
    await delay(2000);
    window.location.href = `/results/${state.interviewId}`;
  } catch (err) {
    removeLoading();
    showToast('Error finishing interview: ' + err.message, 'error');
    if (fb) { fb.disabled = false; fb.innerHTML = '<i class="bi bi-check-circle me-2"></i>Finish & Get Results'; }
  }
}

/* ─── Help / Doubt Chat Panel ────────────────────────────────── */
async function sendHelpChat() {
  const input = $('helpChatInput');
  const msg   = (input?.value || '').trim();
  if (!msg) return;

  appendHelpMsg('user', msg);
  if (input) input.value = '';

  // Show thinking indicator
  const thinkId = 'think-' + Date.now();
  const thinkDiv = document.createElement('div');
  thinkDiv.id = thinkId;
  thinkDiv.className = 'help-chat-msg thinking';
  thinkDiv.innerHTML = '<span class="spinner-border spinner-border-sm me-1" style="width:12px;height:12px"></span> Thinking…';
  const area = $('helpChatMessages');
  if (area) { area.appendChild(thinkDiv); area.scrollTop = area.scrollHeight; }

  try {
    const data = await apiFetch('/api/chat', {
      method: 'POST',
      body: { message: msg, interview_id: state.interviewId || '' },
    });
    document.getElementById(thinkId)?.remove();
    appendHelpMsg('ai', data.response || 'Sorry, I could not generate a response. Please try again.');
  } catch (err) {
    document.getElementById(thinkId)?.remove();
    appendHelpMsg('ai', 'Error: ' + err.message);
  }
}

function appendHelpMsg(type, text) {
  const area = $('helpChatMessages');
  if (!area) return;
  const div = document.createElement('div');
  div.className = `help-chat-msg ${type}`;
  if (type === 'ai') {
    div.innerHTML = `<small class="text-muted d-block mb-1" style="font-size:0.7rem">Alex</small><p class="mb-0">${escapeHtml(text)}</p>`;
  } else {
    div.textContent = text;
  }
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}

// Allow Enter key (without Shift) to send help chat
const helpInput = $('helpChatInput');
if (helpInput) {
  helpInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendHelpChat();
    }
  });
}

/* ─── UI Helpers ─────────────────────────────────────────────── */
function appendMessage(type, html, isHtml = false) {
  const area = $('messagesArea');
  if (!area) return;
  const div = document.createElement('div');
  div.className = `chat-msg ${type}`;
  if (isHtml) div.innerHTML = html;
  else        div.textContent = html;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}

function enableInput() {
  const ta  = $('userAnswer');
  const btn = $('sendBtn');
  if (ta)  { ta.disabled = false; }
  if (btn) { btn.disabled = false; }
}

function disableInput() {
  const ta  = $('userAnswer');
  const btn = $('sendBtn');
  if (ta)  ta.disabled = true;
  if (btn) btn.disabled = true;
}

function buildScoreChip(ev) {
  const color = scoreColor(ev.overall_score);
  const followUp = ev.follow_up_question
    ? `<div class="small mt-2" style="color:var(--text-muted)"><i class="bi bi-arrow-right-circle me-1"></i><em>${escapeHtml(ev.follow_up_question)}</em></div>`
    : '';
  return `
    <div style="font-size:0.88rem">
      <div class="d-flex align-items-center gap-2 mb-1">
        <span style="font-size:1.1rem;font-weight:700;color:${color}">${ev.overall_score}/100</span>
        <span class="badge bg-light text-dark border">Grade: ${ev.grade || 'C'}</span>
        <span class="badge" style="background:${color}20;color:${color};border:1px solid ${color}40">${ev.recommendation || ''}</span>
      </div>
      <p class="mb-0 small">${ev.detailed_feedback ? escapeHtml(ev.detailed_feedback.substring(0, 200)) + '…' : 'See Feedback tab for details.'}</p>
      ${followUp}
    </div>
  `;
}

function renderEvaluation(ev) {
  $('feedbackPlaceholder')?.classList.add('d-none');
  const panel = $('evaluationPanel');
  if (!panel) return;
  panel.classList.remove('d-none');

  const color = scoreColor(ev.overall_score);
  const scoreCircle = $('evalScoreCircle');
  if (scoreCircle) scoreCircle.style.background = `linear-gradient(135deg, ${color}, ${color}88)`;
  if ($('evalScoreNum'))      $('evalScoreNum').textContent      = ev.overall_score;
  if ($('evalGrade'))         $('evalGrade').textContent         = `Grade: ${ev.grade || 'C'}`;
  if ($('evalRecommendation'))$('evalRecommendation').textContent= ev.recommendation || '';

  // Dimension bars
  const dims = $('dimensionScores');
  if (dims) {
    const dimData = [
      ['Technical Accuracy',   ev.technical_accuracy],
      ['Depth & Completeness', ev.depth_completeness],
      ['Clarity',              ev.clarity_communication],
      ['Examples',             ev.practical_examples],
      ['Problem Solving',      ev.problem_solving],
    ];
    dims.innerHTML = dimData.map(([label, score]) => {
      const s = score || 0;
      return `
        <div class="dim-row">
          <span class="dim-label">${label}</span>
          <div class="dim-bar"><div class="dim-fill" style="width:${s}%;background:${scoreColor(s)}"></div></div>
          <span class="dim-score" style="color:${scoreColor(s)}">${s}</span>
        </div>
      `;
    }).join('');
  }

  const ulS = $('evalStrengths');
  if (ulS) ulS.innerHTML = (ev.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('') || '<li class="text-muted">None noted</li>';

  const ulI = $('evalImprovements');
  if (ulI) ulI.innerHTML = (ev.improvements || []).map(i => `<li>${escapeHtml(i)}</li>`).join('') || '<li class="text-muted">None noted</li>';

  if ($('evalIdealAnswer')) $('evalIdealAnswer').textContent = ev.ideal_answer_summary || '';
}

function updateProgress() {
  const total    = state.questions.length;
  const answered = state.answeredSet.size;
  const pt  = $('progressText');
  const pb  = $('progressBar');
  if (pt) pt.textContent = `${answered} / ${total}`;
  if (pb) pb.style.width = total ? `${(answered / total) * 100}%` : '0%';

  const nav = $('questionNav');
  if (!nav) return;
  nav.innerHTML = state.questions.map((q, i) => {
    const isCurrent  = i === state.currentQIndex;
    const isAnswered = state.answeredSet.has(i);
    return `
      <div class="q-nav-item ${isCurrent ? 'current' : ''} ${isAnswered ? 'answered' : ''}">
        <div class="q-nav-dot"></div>
        <span class="text-truncate small flex-grow-1">Q${i + 1}: ${escapeHtml(q.topic || 'Question')}</span>
        ${isAnswered ? '<i class="bi bi-check-circle" style="font-size:0.8rem;flex-shrink:0"></i>' : ''}
      </div>
    `;
  }).join('');
}

function updateLiveScores(ev) {
  state.liveScores.overall.push(ev.overall_score || 0);
  state.liveScores.technical.push(ev.technical_accuracy || 0);
  state.liveScores.communication.push(ev.clarity_communication || 0);

  const avg = arr => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
  const o = avg(state.liveScores.overall);
  const t = avg(state.liveScores.technical);
  const c = avg(state.liveScores.communication);

  const lo = $('liveOverall'); if (lo) { lo.textContent = o; lo.style.color = scoreColor(o); }
  const lt = $('liveTech');    if (lt) { lt.textContent = t; lt.style.color = scoreColor(t); }
  const lc = $('liveComm');   if (lc) { lc.textContent = c; lc.style.color = scoreColor(c); }
}

function renderTips(tips) {
  const list = $('tipsList');
  if (!list) return;
  list.innerHTML = tips.map(t => `<li>${escapeHtml(t)}</li>`).join('');
}

function showTypingInHeader(show) {
  const ind = $('typingIndicator');
  if (ind) ind.classList.toggle('d-none', !show);
}

function updateWordCount() {
  const ta = $('userAnswer');
  const wc = $('answerWordCount');
  if (!ta || !wc) return;
  const words = ta.value.trim().split(/\s+/).filter(Boolean).length;
  wc.textContent = `${words} word${words !== 1 ? 's' : ''}`;
}

/* ─── Keyboard Shortcuts ─────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key === 'Enter') {
    const btn = $('sendBtn');
    if (btn && !btn.disabled && !state.isSubmitting) submitAnswer();
  }
});

const mainTA = $('userAnswer');
if (mainTA) mainTA.addEventListener('input', updateWordCount);

/* ─── Inline styles for question card ───────────────────────── */
const qStyle = document.createElement('style');
qStyle.textContent = `
  .question-card { padding: 2px 0; }
`;
document.head.appendChild(qStyle);

/* ─── Utilities ──────────────────────────────────────────────── */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }
