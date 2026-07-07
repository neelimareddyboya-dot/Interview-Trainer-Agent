/**
 * app.js — Shared utilities: theme toggle, toast notifications, helpers
 * Interview Trainer Agent · IBM watsonx.ai
 */

/* ─── Theme Toggle ───────────────────────────────────────────── */
(function initTheme() {
  const saved = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById('themeBtn');
  if (!btn) return;
  btn.innerHTML = theme === 'dark'
    ? '<i class="bi bi-sun"></i>'
    : '<i class="bi bi-moon-stars"></i>';
}

/* ─── Toast Notifications ────────────────────────────────────── */
function showToast(message, type = 'info', duration = 3500) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    Object.assign(container.style, {
      position: 'fixed', bottom: '20px', right: '20px',
      zIndex: '9999', display: 'flex', flexDirection: 'column', gap: '8px',
    });
    document.body.appendChild(container);
  }

  const colors = { info: '#3b82d4', success: '#16a34a', warning: '#ca8a04', error: '#dc2626' };
  const icons  = { info: 'bi-info-circle', success: 'bi-check-circle', warning: 'bi-exclamation-triangle', error: 'bi-x-circle' };

  const toast = document.createElement('div');
  toast.style.cssText = `
    background: var(--card-bg, #fff); border: 1px solid var(--border, #e5e7eb);
    border-left: 4px solid ${colors[type]}; border-radius: 10px;
    padding: 12px 16px; min-width: 260px; max-width: 360px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    display: flex; align-items: center; gap: 10px;
    animation: toastIn 0.3s ease; font-size: 0.88rem; color: var(--text, #1f2328);
  `;
  toast.innerHTML = `
    <i class="bi ${icons[type]}" style="color:${colors[type]};font-size:1rem;flex-shrink:0"></i>
    <span>${message}</span>
  `;

  const style = document.createElement('style');
  style.textContent = `
    @keyframes toastIn { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
    @keyframes toastOut { from{opacity:1;transform:translateX(0)} to{opacity:0;transform:translateX(20px)} }
  `;
  if (!document.getElementById('toastStyle')) {
    style.id = 'toastStyle';
    document.head.appendChild(style);
  }

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/* ─── Loading Spinner ────────────────────────────────────────── */
function showLoading(message = 'Processing…') {
  removeLoading();
  const overlay = document.createElement('div');
  overlay.id = 'loadingOverlay';
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:9998;
    display:flex;align-items:center;justify-content:center;
  `;
  overlay.innerHTML = `
    <div style="background:var(--card-bg,#fff);border-radius:12px;padding:28px 36px;
                text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.2);">
      <div class="spinner-border text-primary mb-3" style="width:3rem;height:3rem"></div>
      <p style="margin:0;color:var(--text,#1f2328);font-size:0.9rem">${message}</p>
      <small style="color:var(--text-muted,#57606a)">Powered by IBM watsonx.ai</small>
    </div>
  `;
  document.body.appendChild(overlay);
}

function removeLoading() {
  const el = document.getElementById('loadingOverlay');
  if (el) el.remove();
}

/* ─── Score color helper ─────────────────────────────────────── */
function scoreColor(score) {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  return '#dc2626';
}

/* ─── Format date ─────────────────────────────────────────────── */
function formatDate(isoString) {
  if (!isoString) return '—';
  try {
    return new Date(isoString).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return isoString; }
}

/* ─── Grade badge ────────────────────────────────────────────── */
function gradeBadge(grade) {
  const map = {
    'A+': 'success', 'A': 'success', 'B': 'primary',
    'C': 'warning', 'D': 'danger', 'F': 'danger',
  };
  const cls = map[grade] || 'secondary';
  return `<span class="badge bg-${cls}">${grade || '—'}</span>`;
}

/* ─── API Fetch Wrapper ──────────────────────────────────────── */
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const config = { ...defaults, ...options };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }
  const res = await fetch(url, config);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

/* ─── Check health on page load (non-blocking) ───────────────── */
document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/health')
    .then(r => r.json())
    .then(data => {
      if (data.watsonx && data.watsonx.status === 'error') {
        showToast('⚠️ IBM watsonx.ai connection issue. Check API credentials.', 'warning', 6000);
      }
    })
    .catch(() => {}); // silent fail
});
