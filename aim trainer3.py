"""
🎯 AIM TRAINER - Streamlit (chạy được trên PC và điện thoại)
Giống Aim Lab "Gridshot": nhiều mục tiêu cùng lúc, bắn trúng là mọc mục tiêu mới.

Cài đặt & chạy:
    pip install streamlit
    streamlit run aim_trainer.py

Chơi trên điện thoại (cùng Wi-Fi với máy tính):
    streamlit run aim_trainer.py --server.address 0.0.0.0
    -> mở http://<IP-máy-tính>:8501 trên điện thoại
Hoặc đưa lên Streamlit Community Cloud để mở bằng link ở mọi nơi.

Lưu ý: Streamlit chạy phía server nên game được viết bằng HTML5 Canvas + JavaScript
và nhúng qua st.components.v1.html -> phản hồi tức thì, không bị trễ.
"""

import json

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Aim Trainer",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Thu gọn khoảng trống để game rộng hơn trên điện thoại
st.markdown(
    """
    <style>
      .block-container {padding: 0.8rem 0.6rem 1rem 0.6rem; max-width: 1000px;}
      header[data-testid="stHeader"] {height: 0;}
      footer {visibility: hidden;}
      h1 {font-size: 1.6rem !important; margin-bottom: 0.2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

MODES = {
    "Gridshot (3 mục tiêu)": dict(
        key="gridshot", targets=3, size=1.0, life=0,
        desc="3 mục tiêu cùng lúc. Bắn trúng là mọc cái mới. Luyện tốc độ + độ chính xác.",
    ),
    "Sixshot (6 mục tiêu nhỏ)": dict(
        key="sixshot", targets=6, size=0.7, life=0,
        desc="6 mục tiêu nhỏ hơn. Luyện chuyển hướng nhanh và kiểm soát chính xác.",
    ),
    "Reflex (mục tiêu biến mất)": dict(
        key="reflex", targets=2, size=0.9, life=1400,
        desc="Mục tiêu tự biến mất sau 1.4 giây. Luyện phản xạ.",
    ),
}

st.title("🎯 Aim Trainer")

with st.sidebar:
    st.header("⚙️ Cài đặt")
    mode_name = st.selectbox("Chế độ", list(MODES.keys()))
    duration = st.slider("Thời gian (giây)", 20, 120, 60, step=10)
    size_scale = st.slider("Cỡ mục tiêu", 0.5, 1.6, 1.0, step=0.1)
    sound = st.toggle("Âm thanh", value=True)
    height = st.slider("Chiều cao khung game (px)", 420, 900, 640, step=20)
    st.caption("Điện thoại: nên để 560–680 px, xoay ngang nếu muốn khung rộng hơn.")

mode = MODES[mode_name]
config = {
    "mode": mode["key"],
    "modeName": mode_name,
    "desc": mode["desc"],
    "targets": mode["targets"],
    "size": mode["size"] * size_scale,
    "life": mode["life"],
    "duration": duration,
    "sound": sound,
}

GAME_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<style>
  html, body {margin:0; padding:0; height:100%; background:#14161c; overflow:hidden;
              font-family:-apple-system, "Segoe UI", Roboto, Arial, sans-serif; color:#fff;
              -webkit-user-select:none; user-select:none; -webkit-touch-callout:none;}
  #wrap {position:relative; width:100%; height:100%;}
  canvas {display:block; touch-action:none; cursor:crosshair;}
  #overlay {position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            background:rgba(10,12,16,.82); text-align:center; padding:16px; box-sizing:border-box;}
  #card {max-width:420px; width:100%;}
  h2 {margin:0 0 6px; font-size:26px;}
  p  {margin:6px 0 14px; color:#b8bfcc; font-size:15px; line-height:1.4;}
  button {background:#ffd400; color:#111; border:0; border-radius:12px; padding:14px 28px;
          font-size:18px; font-weight:700; cursor:pointer; touch-action:manipulation;}
  button:active {transform:scale(.97);}
  .stats {display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:12px 0 16px;}
  .stat {background:#222733; border-radius:10px; padding:10px;}
  .stat b {display:block; font-size:22px; color:#ffd400;}
  .stat span {font-size:12px; color:#9aa3b5;}
  .new {color:#4ade80; font-weight:700; margin-bottom:4px;}
</style>
</head>
<body>
<div id="wrap">
  <canvas id="c"></canvas>
  <div id="overlay"><div id="card"></div></div>
</div>

<script>
const CFG = __CONFIG__;
const cv  = document.getElementById('c');
const ctx = cv.getContext('2d');
const overlay = document.getElementById('overlay');
const card = document.getElementById('card');

let W, H, DPR, HUD_H = 56;
let grid = {cols: 6, rows: 4, cell: 80, x0: 0, y0: 0};
let state = 'menu';            // menu | countdown | play | result
let targets = [], fx = [];
let t0 = 0, cdStart = 0;
let score = 0, hits = 0, clicks = 0, expired = 0, reactSum = 0;
let lastMiss = null;
let aim = {x: 0, y: 0}, recoil = 0, flashT = 0;

/* ---------- Âm thanh ---------- */
let actx = null;
function beep(freq, dur, vol) {
  if (!CFG.sound) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(), g = actx.createGain();
    o.frequency.value = freq; o.type = 'square';
    g.gain.value = vol; g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime + dur);
    o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + dur);
  } catch (e) {}
}

/* ---------- Bố cục ---------- */
function resize() {
  DPR = window.devicePixelRatio || 1;
  W = window.innerWidth; H = window.innerHeight;
  cv.width = W * DPR; cv.height = H * DPR;
  cv.style.width = W + 'px'; cv.style.height = H + 'px';
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  HUD_H = W < 480 ? 50 : 60;
  const portrait = H > W * 1.1;
  grid.cols = portrait ? 4 : 6;
  grid.rows = portrait ? 6 : 4;
  const pw = W - 16, ph = H - HUD_H - 16;
  grid.cell = Math.min(pw / grid.cols, ph / grid.rows);
  grid.x0 = (W - grid.cell * grid.cols) / 2;
  grid.y0 = HUD_H + (ph + 16 - grid.cell * grid.rows) / 2;
  targets = [];                      // bố cục đổi -> sinh lại mục tiêu
  if (state === 'play') fillTargets();
}
window.addEventListener('resize', resize);

function baseRadius() { return grid.cell * 0.30 * CFG.size; }

/* ---------- Mục tiêu ---------- */
function spawn() {
  const used = new Set(targets.map(t => t.cell));
  const free = [];
  for (let i = 0; i < grid.cols * grid.rows; i++) if (!used.has(i)) free.push(i);
  if (!free.length) return;
  const c = free[Math.floor(Math.random() * free.length)];
  const col = c % grid.cols, row = Math.floor(c / grid.cols);
  targets.push({
    cell: c,
    x: grid.x0 + (col + 0.5) * grid.cell,
    y: grid.y0 + (row + 0.5) * grid.cell,
    r: baseRadius(),
    born: performance.now(),
  });
}
function fillTargets() { while (targets.length < CFG.targets) spawn(); }

/* ---------- Điều khiển game ---------- */
function showMenu() {
  state = 'menu'; targets = [];
  const hs = getHS();
  card.innerHTML =
    '<h2>🎯 ' + CFG.modeName + '</h2>' +
    '<p>' + CFG.desc + '</p>' +
    '<p>⏱ ' + CFG.duration + ' giây' + (hs ? ' &nbsp;·&nbsp; 🏆 Kỷ lục: <b>' + hs + '</b>' : '') + '</p>' +
    '<button id="go">BẮT ĐẦU</button>' +
    '<p style="font-size:13px">PC: click chuột · Điện thoại: chạm vào mục tiêu</p>';
  overlay.style.display = 'flex';
  document.getElementById('go').onclick = startCountdown;
}

function startCountdown() {
  beep(500, .08, .05);
  overlay.style.display = 'none';
  score = hits = clicks = expired = reactSum = 0; fx = []; targets = []; lastMiss = null;
  state = 'countdown'; cdStart = performance.now();
}

function startPlay() {
  state = 'play'; t0 = performance.now(); fillTargets();
}

function getHS() {
  try { return parseInt(localStorage.getItem('aim_hs_' + CFG.mode) || '0'); } catch (e) { return 0; }
}
function setHS(v) {
  try { localStorage.setItem('aim_hs_' + CFG.mode, String(v)); } catch (e) {}
}

function endGame() {
  state = 'result'; targets = [];
  const acc = clicks ? Math.round(100 * hits / clicks) : 0;
  const hps = (hits / CFG.duration).toFixed(2);
  const avg = hits ? Math.round(reactSum / hits) : 0;
  const prev = getHS();
  const isNew = score > prev;
  if (isNew) setHS(score);
  beep(880, .25, .06);
  card.innerHTML =
    '<h2>Kết quả</h2>' +
    (isNew ? '<div class="new">🏆 Kỷ lục mới!</div>' : '<p>Kỷ lục: ' + prev + '</p>') +
    '<div class="stats">' +
      '<div class="stat"><b>' + score + '</b><span>ĐIỂM</span></div>' +
      '<div class="stat"><b>' + acc + '%</b><span>ĐỘ CHÍNH XÁC</span></div>' +
      '<div class="stat"><b>' + hps + '</b><span>BẮN TRÚNG / GIÂY</span></div>' +
      '<div class="stat"><b>' + avg + ' ms</b><span>THỜI GIAN BẮN TB</span></div>' +
    '</div>' +
    '<p style="margin-top:-4px">Trúng ' + hits + ' · Trượt ' + (clicks - hits) +
      (CFG.life ? ' · Hết hạn ' + expired : '') + '</p>' +
    '<button id="again">CHƠI LẠI</button>';
  overlay.style.display = 'flex';
  document.getElementById('again').onclick = startCountdown;
}

/* ---------- Bắn ---------- */
cv.addEventListener('pointermove', e => {
  const r = cv.getBoundingClientRect();
  aim.x = e.clientX - r.left; aim.y = e.clientY - r.top;
});

function shoot(px, py, touch) {
  if (state !== 'play') return;
  aim.x = px; aim.y = py;
  recoil = 1; flashT = performance.now();
  clicks++;
  const slop = touch ? 8 : 0;            // chạm tay được "du di" thêm cho dễ
  let hit = -1, best = 1e9;
  for (let i = 0; i < targets.length; i++) {
    const t = targets[i];
    const d = Math.hypot(px - t.x, py - t.y);
    if (d <= t.r + slop && d < best) { best = d; hit = i; }
  }
  if (hit >= 0) {
    const t = targets[hit];
    const rt = performance.now() - t.born;
    // 500 điểm cơ bản + tối đa 500 điểm thưởng tốc độ (giảm dần trong 1.5s)
    const bonus = Math.max(0, 500 * (1 - rt / 1500));
    const centre = 1 - Math.min(1, best / t.r);        // bắn gần tâm được thêm
    score += Math.round(500 + bonus + 100 * centre);
    hits++; reactSum += rt;
    fx.push({x: t.x, y: t.y, r: t.r, t: performance.now(), type: 'hit'});
    targets.splice(hit, 1);
    spawn();
    beep(740 + Math.random() * 60, .06, .05);
  } else {
    fx.push({x: px, y: py, r: 12, t: performance.now(), type: 'miss'});
    beep(160, .08, .04);
  }
}
cv.addEventListener('pointerdown', e => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  shoot(e.clientX - r.left, e.clientY - r.top, e.pointerType !== 'mouse');
});
// Chỉ chặn cuộn/zoom trên vùng game (canvas), KHÔNG chặn nút bấm
['touchstart', 'touchmove'].forEach(ev =>
  cv.addEventListener(ev, e => e.preventDefault(), {passive: false}));

/* ---------- Vẽ ---------- */
function drawBackground() {
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#3a3f4a'); g.addColorStop(0.62, '#4a505c'); g.addColorStop(0.62, '#2b2f38'); g.addColorStop(1, '#3d424d');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}

function drawHUD(remaining) {
  const acc = clicks ? Math.round(100 * hits / clicks) : 100;
  const items = [['POINTS', score], ['TIME', fmt(remaining)], ['ACCURACY', acc + '%']];
  const pad = 8, gap = 8, bw = (W - pad * 2 - gap * 2) / 3, bh = HUD_H - 12;
  items.forEach((it, i) => {
    const x = pad + i * (bw + gap), y = 6;
    ctx.fillStyle = 'rgba(15,18,24,.78)'; ctx.fillRect(x, y, bw, bh);
    ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.strokeRect(x + .5, y + .5, bw - 1, bh - 1);
    ctx.fillStyle = '#9aa3b5'; ctx.font = '600 10px sans-serif'; ctx.textAlign = 'left';
    ctx.fillText(it[0], x + 8, y + 15);
    ctx.fillStyle = '#fff'; ctx.font = '700 ' + (W < 480 ? 17 : 20) + 'px sans-serif';
    ctx.fillText(String(it[1]), x + 8, y + bh - 9);
  });
}
function fmt(s) {
  s = Math.max(0, Math.ceil(s));
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}

function drawTarget(t, scale, alpha) {
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.beginPath(); ctx.arc(t.x, t.y, t.r * scale, 0, Math.PI * 2);
  ctx.fillStyle = '#0b0b0d'; ctx.fill();
  ctx.lineWidth = Math.max(2, t.r * 0.08); ctx.strokeStyle = '#f2e600'; ctx.stroke();
  ctx.beginPath(); ctx.arc(t.x - t.r * .3, t.y - t.r * .3, t.r * .18 * scale, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,255,255,.12)'; ctx.fill();
  ctx.restore();
}

/* ---------- Cây súng (đỏ, nằm dưới màn hình, xoay theo chuột/ngón tay) ---------- */
function drawGun(now) {
  const s = Math.min(W, H) * 0.30;
  const bx = W * 0.62, by = H + s * 0.15;
  let ang = Math.atan2(aim.x - bx, by - aim.y);
  ang = Math.max(-0.55, Math.min(0.55, ang));
  recoil *= 0.82;
  ctx.save();
  ctx.translate(bx, by); ctx.rotate(ang); ctx.translate(0, recoil * s * 0.12);
  // thân súng (slide)
  const g = ctx.createLinearGradient(-s * 0.15, 0, s * 0.15, 0);
  g.addColorStop(0, '#8a1020'); g.addColorStop(0.45, '#ff3b4a'); g.addColorStop(1, '#6a0a18');
  ctx.fillStyle = g;
  ctx.fillRect(-s * 0.15, -s * 1.05, s * 0.30, s * 0.72);
  // nòng + đầu ngắm
  ctx.fillStyle = '#2a0a10'; ctx.fillRect(-s * 0.07, -s * 1.09, s * 0.14, s * 0.06);
  ctx.fillStyle = '#ffd1d6'; ctx.fillRect(-s * 0.025, -s * 1.14, s * 0.05, s * 0.06);
  // rãnh trượt
  ctx.fillStyle = 'rgba(0,0,0,.35)';
  for (let i = 0; i < 4; i++) ctx.fillRect(-s * 0.15, -s * (0.50 + i * 0.05), s * 0.30, s * 0.012);
  // báng súng
  const g2 = ctx.createLinearGradient(-s * 0.13, 0, s * 0.13, 0);
  g2.addColorStop(0, '#3b0d6a'); g2.addColorStop(1, '#7a2dbd');
  ctx.fillStyle = g2;
  ctx.fillRect(-s * 0.12, -s * 0.33, s * 0.24, s * 0.55);
  ctx.restore();
  // tia lửa đầu nòng
  const fa = 1 - (now - flashT) / 70;
  if (fa > 0) {
    const mx = bx + Math.sin(ang) * s * 1.1, my = by - Math.cos(ang) * s * 1.1 + recoil * s * 0.12;
    ctx.save(); ctx.globalAlpha = fa;
    ctx.fillStyle = '#ffe066'; ctx.beginPath(); ctx.arc(mx, my, s * 0.09, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(mx, my, s * 0.04, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
}

function loop(now) {
  drawBackground();
  // vạch kẻ nền cho có cảm giác không gian
  ctx.strokeStyle = 'rgba(255,255,255,.04)'; ctx.lineWidth = 1;
  for (let i = 0; i <= grid.cols; i++) { const x = grid.x0 + i * grid.cell; ctx.beginPath(); ctx.moveTo(x, grid.y0); ctx.lineTo(x, grid.y0 + grid.rows * grid.cell); ctx.stroke(); }
  for (let j = 0; j <= grid.rows; j++) { const y = grid.y0 + j * grid.cell; ctx.beginPath(); ctx.moveTo(grid.x0, y); ctx.lineTo(grid.x0 + grid.cols * grid.cell, y); ctx.stroke(); }

  let remaining = CFG.duration;
  if (state === 'countdown') {
    const n = 3 - Math.floor((now - cdStart) / 700);
    if (n <= 0) startPlay();
    else {
      ctx.fillStyle = '#fff'; ctx.font = '800 ' + Math.min(W, H) * 0.25 + 'px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(n), W / 2, H / 2); ctx.textBaseline = 'alphabetic';
    }
  }
  if (state === 'play') {
    remaining = CFG.duration - (now - t0) / 1000;
    if (remaining <= 0) { drawHUD(0); endGame(); }
    else {
      if (CFG.life) {
        for (let i = targets.length - 1; i >= 0; i--) {
          if (now - targets[i].born > CFG.life) { targets.splice(i, 1); expired++; }
        }
        fillTargets();
      }
      targets.forEach(t => {
        const age = now - t.born;
        const sc = Math.min(1, age / 90);                       // hiệu ứng mọc ra
        let a = 1;
        if (CFG.life) a = age > CFG.life - 350 ? 0.35 + 0.65 * Math.abs(Math.sin(age / 60)) : 1;
        drawTarget(t, 0.3 + 0.7 * sc, a);
      });
    }
  }
  // hiệu ứng nổ / trượt
  fx = fx.filter(f => now - f.t < 260);
  fx.forEach(f => {
    const k = (now - f.t) / 260;
    ctx.save(); ctx.globalAlpha = 1 - k; ctx.lineWidth = 3;
    if (f.type === 'hit') {
      ctx.strokeStyle = '#4ade80'; ctx.beginPath(); ctx.arc(f.x, f.y, f.r * (1 + k * 0.9), 0, Math.PI * 2); ctx.stroke();
    } else {
      ctx.strokeStyle = '#f87171'; ctx.beginPath();
      ctx.moveTo(f.x - 8, f.y - 8); ctx.lineTo(f.x + 8, f.y + 8);
      ctx.moveTo(f.x + 8, f.y - 8); ctx.lineTo(f.x - 8, f.y + 8); ctx.stroke();
    }
    ctx.restore();
  });
  drawGun(now);
  if (state === 'play' || state === 'countdown') drawHUD(remaining);
  requestAnimationFrame(loop);
}

resize();
aim.x = W / 2; aim.y = H / 2;
showMenu();
requestAnimationFrame(loop);
</script>
</body>
</html>
"""

components.html(
    GAME_HTML.replace("__CONFIG__", json.dumps(config)),
    height=height,
    scrolling=False,
)

with st.expander("📖 Hướng dẫn & mẹo luyện tập"):
    st.markdown(
        """
**Cách chơi**
- Bấm **BẮT ĐẦU**, đếm ngược 3-2-1 rồi bắn trúng các vòng tròn đen viền vàng.
- PC: dùng chuột click. Điện thoại: chạm vào mục tiêu.
- Điểm = 500 cơ bản + thưởng theo tốc độ + thưởng bắn gần tâm.
- Điểm kỷ lục được lưu ngay trên trình duyệt của bạn (theo từng chế độ).

**Mẹo luyện**
1. Đừng nhìn vào chuột/ngón tay, hãy nhìn mục tiêu tiếp theo trước khi bắn mục tiêu hiện tại.
2. Ưu tiên **độ chính xác 95%+** trước, tốc độ sẽ tăng dần.
3. Luyện 10–15 phút mỗi ngày hiệu quả hơn luyện dồn 2 tiếng.
4. Khi đã quen, giảm **cỡ mục tiêu** trong phần Cài đặt (mũi tên ở góc trên bên trái).
"""
    )
