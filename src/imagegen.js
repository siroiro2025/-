"use strict";

// 画像生成バックエンドのディスパッチャ。
//   IMAGE_BACKEND=qwen   → ローカル Qwen-Image-Edit 2511 (tools/qwen_server.py)
//   IMAGE_BACKEND=gemini → Gemini API
//   未指定               → QWEN_SERVER_URL があれば qwen、なければ gemini

const gemini = require("./gemini");
const qwen = require("./qwen");

function backendName() {
  const b = (process.env.IMAGE_BACKEND || "").toLowerCase();
  if (b === "qwen") return "qwen";
  if (b === "gemini") return "gemini";
  return process.env.QWEN_SERVER_URL ? "qwen" : "gemini";
}

function backendLabel() {
  return backendName() === "qwen" ? "Qwen-Image ローカル" : "Gemini";
}

async function generateImage(args) {
  return (backendName() === "qwen" ? qwen : gemini).generateImage(args);
}

module.exports = { generateImage, backendName, backendLabel };
