"use strict";

// 上半身版とまりぐるぐるビューア:
//  - マウス追従: カーソル位置から 5x5 の向きフレームを選択
//  - まばたき: ランダム間隔で目閉じフレームに一瞬切り替え
//  - リップシンク: マイク音量 (またはデモ) で口の開きを 3 段階に切り替え

const ROWS = 5, COLS = 5;
const MOUTHS = ["closed", "half", "open"];

const params = new URLSearchParams(location.search);
const jobId = params.get("job");
const statusEl = document.getElementById("status");
const avatar = document.getElementById("avatar");

if (!jobId) {
  statusEl.textContent = "?job=<ジョブID> を指定してください";
  throw new Error("no job id");
}

function frameUrl(eyes, mouth, r, c) {
  return `/output/${jobId}/frames/eyes_${eyes}_mouth_${mouth}/r${r}c${c}.png`;
}

// 全150フレームをプリロード
const cache = new Map();
let loaded = 0, total = 0;
for (const eyes of ["open", "closed"]) {
  for (const mouth of MOUTHS) {
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        total++;
        const img = new Image();
        img.src = frameUrl(eyes, mouth, r, c);
        img.onload = () => {
          loaded++;
          statusEl.textContent = `読み込み中... ${loaded}/${total}`;
          if (loaded === total) statusEl.textContent = "マウスを動かすと目で追いかけます";
        };
        img.onerror = () => { loaded++; };
        cache.set(`${eyes}_${mouth}_${r}_${c}`, img);
      }
    }
  }
}

// --- 状態 ---
let col = 2, row = 2;          // 向き（中央 = 正面）
let eyesClosed = false;        // まばたき
let mouthLevel = 0;            // 0=closed 1=half 2=open

function render() {
  const eyes = eyesClosed ? "closed" : "open";
  const mouth = MOUTHS[mouthLevel];
  const img = cache.get(`${eyes}_${mouth}_${row}_${col}`);
  if (img && img.complete && img.naturalWidth > 0) {
    avatar.src = img.src;
  }
}

// --- マウス追従 ---
function updateDirection(x, y) {
  const rect = avatar.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  // 画面半分の距離で端まで振り切る
  const nx = Math.max(-1, Math.min(1, (x - cx) / (window.innerWidth / 2)));
  const ny = Math.max(-1, Math.min(1, (y - cy) / (window.innerHeight / 2)));
  col = Math.round((nx + 1) / 2 * (COLS - 1));
  row = Math.round((ny + 1) / 2 * (ROWS - 1));
  render();
}
window.addEventListener("mousemove", (e) => updateDirection(e.clientX, e.clientY));
window.addEventListener("touchmove", (e) => {
  const t = e.touches[0];
  if (t) updateDirection(t.clientX, t.clientY);
}, { passive: true });

// --- まばたき ---
function scheduleBlink() {
  setTimeout(() => {
    eyesClosed = true;
    render();
    setTimeout(() => {
      eyesClosed = false;
      render();
      scheduleBlink();
    }, 130);
  }, 1800 + Math.random() * 4000);
}
scheduleBlink();

// --- リップシンク（マイク） ---
const micBtn = document.getElementById("micBtn");
const demoBtn = document.getElementById("demoBtn");
let audioCtx = null, analyser = null, micActive = false, demoActive = false, demoTimer = null;

micBtn.addEventListener("click", async () => {
  if (micActive) {
    micActive = false;
    micBtn.classList.remove("active");
    mouthLevel = 0;
    render();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
    micActive = true;
    stopDemo();
    micBtn.classList.add("active");
    tickMic();
  } catch (err) {
    statusEl.textContent = "マイクを使用できませんでした: " + err.message;
  }
});

function tickMic() {
  if (!micActive) return;
  const buf = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(buf);
  let sum = 0;
  for (const v of buf) {
    const d = (v - 128) / 128;
    sum += d * d;
  }
  const rms = Math.sqrt(sum / buf.length);
  const level = rms > 0.12 ? 2 : rms > 0.04 ? 1 : 0;
  if (level !== mouthLevel) {
    mouthLevel = level;
    render();
  }
  requestAnimationFrame(tickMic);
}

// --- おしゃべりデモ ---
function stopDemo() {
  demoActive = false;
  demoBtn.classList.remove("active");
  if (demoTimer) clearTimeout(demoTimer);
  demoTimer = null;
}

demoBtn.addEventListener("click", () => {
  if (demoActive) {
    stopDemo();
    mouthLevel = 0;
    render();
    return;
  }
  micActive = false;
  micBtn.classList.remove("active");
  demoActive = true;
  demoBtn.classList.add("active");
  (function talk() {
    if (!demoActive) return;
    mouthLevel = Math.floor(Math.random() * 3);
    render();
    demoTimer = setTimeout(talk, 90 + Math.random() * 140);
  })();
});

render();
