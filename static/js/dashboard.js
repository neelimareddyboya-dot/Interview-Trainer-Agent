/**
 * dashboard.js — Dashboard data loading and chart rendering
 * Interview Trainer Agent · IBM watsonx.ai
 */

document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
});

async function loadDashboard() {
  try {
    const data = await apiFetch('/api/history');
    renderDashboard(data.history || []);
  } catch (err) {
    showToast('Failed to load dashboard: ' + err.message, 'error');
  }
}

async function refreshDashboard() {
  const btn = document.querySelector('[onclick="refreshDashboard()"]');
  if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading…';
  await loadDashboard();
  if (btn) btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
  showToast('Dashboard refreshed', 'success', 2000);
}

function renderDashboard(history) {
  updateSummaryStats(history);
  renderHistoryTable(history);
  renderProgressChart(history);
  renderSkillBreakdown(history);
  renderStrengthsAndImprovements(history);
  renderGuidancePreview(history);
}

/* ─── Summary Stats ──────────────────────────────────────────── */
function updateSummaryStats(history) {
  const total = history.length;
  const scores = history.map(h => h.score?.overall || 0).filter(s => s > 0);
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const best = scores.length ? Math.max(...scores) : 0;
  const totalQA = history.reduce((acc, h) => acc + (h.questions_answered || 0), 0);

  setInner('statTotalSessions', total || '0');
  setInner('statAvgScore', avg ? `${avg}` : '—');
  setInner('statBestScore', best ? `${best}` : '—');
  setInner('statTotalQuestions', totalQA || '0');
}

/* ─── History Table ──────────────────────────────────────────── */
function renderHistoryTable(history) {
  const tbody = document.getElementById('historyTableBody');
  if (!tbody) return;

  if (!history.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">No sessions yet. <a href="/interview">Start your first interview →</a></td></tr>';
    return;
  }

  tbody.innerHTML = history.map(h => {
    const score = h.score?.overall || 0;
    const grade = h.score?.grade || '—';
    const date = formatDate(h.completed_at);
    const scoreStyle = `color:${scoreColorHex(score)};font-weight:700`;
    const diffBadge = difficultyBadge(h.difficulty);
    return `
      <tr>
        <td><code class="small">${h.interview_id}</code></td>
        <td>${escHtml(h.job_role || '—')}</td>
        <td><span class="badge bg-light text-dark border">${escHtml(h.domain || '—')}</span></td>
        <td><span style="${scoreStyle}">${score}</span>/100</td>
        <td>${gradeBadge(grade)}</td>
        <td>${h.questions_answered || 0}</td>
        <td>${diffBadge}</td>
        <td class="small text-muted">${date}</td>
        <td><a href="/results/${h.interview_id}" class="btn btn-xs btn-outline-primary" style="font-size:0.75rem;padding:3px 10px">View</a></td>
      </tr>
    `;
  }).join('');
}

/* ─── Progress Chart (SVG) ───────────────────────────────────── */
function renderProgressChart(history) {
  const chartLine  = document.getElementById('chartLine');
  const chartFill  = document.getElementById('chartFill');
  const chartDots  = document.getElementById('chartDots');
  const chartEmpty = document.getElementById('chartEmpty');
  if (!chartLine) return;

  const recent = history.slice(0, 10).reverse();
  if (!recent.length) { if (chartEmpty) chartEmpty.style.display = 'block'; return; }
  if (chartEmpty) chartEmpty.style.display = 'none';

  const scores = recent.map(h => h.score?.overall || 0);
  const n = scores.length;
  const W = 540, H = 160; // usable width/height inside the SVG
  const xOffset = 40, yOffset = 20;

  const toX = i => xOffset + (i / Math.max(n - 1, 1)) * W;
  const toY = s => yOffset + H - (s / 100) * H;

  let linePath = '';
  let fillPath = '';
  let dotsHtml  = '';

  scores.forEach((s, i) => {
    const x = toX(i), y = toY(s);
    linePath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    if (i === 0) fillPath = `M ${x} ${H + yOffset}`;
    fillPath += ` L ${x} ${y}`;
    if (i === scores.length - 1) fillPath += ` L ${x} ${H + yOffset} Z`;

    const color = scoreColorHex(s);
    dotsHtml += `
      <circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="var(--bg,#fff)" stroke-width="2"/>
      <text x="${x}" y="${y - 9}" fill="${color}" font-size="10" text-anchor="middle" font-weight="600">${s}</text>
    `;
  });

  chartLine.setAttribute('d', linePath);
  chartFill.setAttribute('d', fillPath);
  chartDots.innerHTML = dotsHtml;

  // X-axis labels (session numbers)
  scores.forEach((_, i) => {
    const x = toX(i);
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x);
    label.setAttribute('y', H + yOffset + 16);
    label.setAttribute('fill', '#57606a');
    label.setAttribute('font-size', '10');
    label.setAttribute('text-anchor', 'middle');
    label.textContent = `S${i + 1}`;
    chartDots.appendChild(label);
  });
}

/* ─── Skill Breakdown ────────────────────────────────────────── */
function renderSkillBreakdown(history) {
  const container = document.getElementById('skillBreakdown');
  if (!container || !history.length) return;

  // Average latest 5 sessions
  const recent = history.slice(0, 5);
  const dims = ['technical_accuracy', 'depth_completeness', 'clarity_communication', 'practical_examples', 'problem_solving'];
  const labels = ['Technical', 'Depth', 'Clarity', 'Examples', 'Problem Solving'];

  const avgs = dims.map(d => {
    const vals = recent.map(h => h.score?.breakdown?.[d] || 0).filter(v => v > 0);
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0;
  });

  container.innerHTML = avgs.map((avg, i) => `
    <div class="mb-3">
      <div class="d-flex justify-content-between small mb-1">
        <span>${labels[i]}</span>
        <span class="fw-bold" style="color:${scoreColorHex(avg)}">${avg}</span>
      </div>
      <div class="progress" style="height:8px">
        <div class="progress-bar" style="width:${avg}%;background:${scoreColorHex(avg)};transition:width 1.2s ease"></div>
      </div>
    </div>
  `).join('');
}

/* ─── Strengths & Improvements ───────────────────────────────── */
function renderStrengthsAndImprovements(history) {
  const allStrengths = history.flatMap(h => h.score?.top_strengths || []);
  const allImprovements = history.flatMap(h => h.score?.top_improvements || []);

  const topStrengths = [...new Set(allStrengths)].slice(0, 5);
  const topImprovements = [...new Set(allImprovements)].slice(0, 5);

  const sEl = document.getElementById('globalStrengths');
  const iEl = document.getElementById('globalImprovements');

  if (sEl && topStrengths.length) {
    sEl.innerHTML = topStrengths.map(s => `<li>${escHtml(s)}</li>`).join('');
  }
  if (iEl && topImprovements.length) {
    iEl.innerHTML = topImprovements.map(i => `<li>${escHtml(i)}</li>`).join('');
  }
}

/* ─── Guidance Preview ───────────────────────────────────────── */
function renderGuidancePreview(history) {
  const container = document.getElementById('guidancePreview');
  if (!container || !history.length) return;

  const latest = history[0];
  const g = latest?.guidance;
  if (!g) return;

  container.innerHTML = `
    <div class="row g-3">
      ${g.motivational_message ? `
        <div class="col-12">
          <div class="motivational-banner">${escHtml(g.motivational_message)}</div>
        </div>
      ` : ''}
      ${g.readiness_score !== undefined ? `
        <div class="col-md-3 text-center">
          <div style="font-size:2rem;font-weight:800;color:${scoreColorHex(g.readiness_score)}">${g.readiness_score}</div>
          <div class="small text-muted">Readiness Score</div>
          <div class="small fw-semibold">${g.readiness_label || ''}</div>
        </div>
      ` : ''}
      ${g.quick_wins?.length ? `
        <div class="col-md-4">
          <h6 class="small fw-semibold"><i class="bi bi-lightning me-1 text-warning"></i>Quick Wins</h6>
          <ul class="resource-list">${g.quick_wins.map(w => `<li>${escHtml(w)}</li>`).join('')}</ul>
        </div>
      ` : ''}
      ${g.long_term_goals?.length ? `
        <div class="col-md-5">
          <h6 class="small fw-semibold"><i class="bi bi-flag me-1 text-primary"></i>Long-Term Goals</h6>
          <ul class="resource-list">${g.long_term_goals.map(goal => `<li>${escHtml(goal)}</li>`).join('')}</ul>
        </div>
      ` : ''}
    </div>
    <div class="mt-3 text-end">
      <a href="/results/${latest.interview_id}" class="btn btn-sm btn-outline-primary">
        <i class="bi bi-arrow-right me-1"></i>View Full Report
      </a>
    </div>
  `;
}

/* ─── Helpers ────────────────────────────────────────────────── */
function setInner(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function scoreColorHex(score) {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  return '#dc2626';
}

function difficultyBadge(diff) {
  const map = { easy: 'success', medium: 'warning', hard: 'danger' };
  const cls = map[diff] || 'secondary';
  return `<span class="badge bg-${cls} text-${cls === 'warning' ? 'dark' : 'white'}">${diff || '—'}</span>`;
}
