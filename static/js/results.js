/**
 * results.js — Results page animations and score ring rendering
 * Interview Trainer Agent · IBM watsonx.ai
 */

document.addEventListener('DOMContentLoaded', () => {
  animateScoreRing();
  animateProgressBars();
  triggerConfetti();
});

/* ─── Score Ring Animation ───────────────────────────────────── */
function animateScoreRing() {
  const ring = document.getElementById('scoreRingProgress');
  const numEl = document.getElementById('finalScoreNum');
  if (!ring || !numEl) return;

  const score = parseInt(numEl.textContent) || 0;
  const circumference = 326.7;
  const offset = circumference - (score / 100) * circumference;

  // Animate over 1.5s
  ring.style.transition = 'stroke-dashoffset 1.5s ease, stroke 0.5s ease';
  ring.style.stroke = scoreColorHex(score);
  setTimeout(() => {
    ring.style.strokeDashoffset = offset;
  }, 100);

  // Count up number
  let current = 0;
  const step = Math.ceil(score / 60);
  const timer = setInterval(() => {
    current = Math.min(current + step, score);
    numEl.textContent = current;
    if (current >= score) clearInterval(timer);
  }, 25);
}

/* ─── Progress Bars ──────────────────────────────────────────── */
function animateProgressBars() {
  document.querySelectorAll('.score-progress-bar').forEach(bar => {
    const target = bar.getAttribute('data-score') || bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => {
      bar.style.transition = 'width 1.2s ease';
      bar.style.width = typeof target === 'string' && target.includes('%') ? target : `${target}%`;
      const score = parseInt(target);
      bar.style.background = scoreColorHex(score);
    }, 200);
  });
}

/* ─── Confetti (CSS only, no external libs) ──────────────────── */
function triggerConfetti() {
  const score = parseInt(document.getElementById('finalScoreNum')?.textContent) || 0;
  if (score < 70) return; // Only celebrate good scores

  const area = document.getElementById('confettiArea');
  if (!area) return;

  const colors = ['#3b82d4', '#7c5cd8', '#16a34a', '#ca8a04', '#ea580c'];
  for (let i = 0; i < 30; i++) {
    const dot = document.createElement('div');
    const size = Math.random() * 8 + 4;
    const color = colors[Math.floor(Math.random() * colors.length)];
    const left = Math.random() * 100;
    const delay = Math.random() * 1.5;
    const duration = Math.random() * 2 + 2;

    dot.style.cssText = `
      position:absolute;
      width:${size}px;height:${size}px;
      background:${color};
      border-radius:${Math.random() > 0.5 ? '50%' : '2px'};
      left:${left}%;top:0;
      animation:confettiFall ${duration}s ${delay}s ease-out forwards;
      opacity:0.9;
    `;
    area.appendChild(dot);
  }

  if (!document.getElementById('confettiStyle')) {
    const style = document.createElement('style');
    style.id = 'confettiStyle';
    style.textContent = `
      #confettiArea { position:absolute;width:100%;height:100%;overflow:hidden;pointer-events:none;top:0;left:0; }
      @keyframes confettiFall {
        0%   { transform:translateY(-20px) rotate(0deg); opacity:0.9; }
        100% { transform:translateY(200px) rotate(720deg); opacity:0; }
      }
    `;
    document.head.appendChild(style);
  }
}

/* ─── Helper ─────────────────────────────────────────────────── */
function scoreColorHex(score) {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#ca8a04';
  return '#dc2626';
}
