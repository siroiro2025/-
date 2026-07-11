"use strict";

const Anthropic = require("@anthropic-ai/sdk");

// オーケストレーター: 最上位モデル。分析・プロンプト設計・リトライ判断など少数の重要な呼び出しのみ担当
const ORCHESTRATOR_MODEL = "claude-fable-5";
// ワーカー: 最安モデル。シートごとの検品（QC）など回数の多い呼び出しを担当
const WORKER_MODEL = "claude-haiku-4-5";

let _client = null;
function client() {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error("ANTHROPIC_API_KEY が設定されていません（.env を確認してください）");
  }
  if (!_client) _client = new Anthropic();
  return _client;
}

function imageBlock(base64Data, mimeType) {
  return {
    type: "image",
    source: { type: "base64", media_type: mimeType, data: base64Data },
  };
}

function extractJSON(response) {
  if (response.stop_reason === "refusal") {
    throw new Error("モデルがリクエストを拒否しました (refusal)");
  }
  const text = response.content.find((b) => b.type === "text")?.text ?? "";
  return JSON.parse(text);
}

// Fable 5 呼び出し。安全分類器による decline に備え、サーバー側フォールバック
// (Opus 4.8) をデフォルトで有効化している。
async function orchestratorJSON({ system, content, schema, maxTokens = 8000 }) {
  const response = await client().beta.messages.create({
    model: ORCHESTRATOR_MODEL,
    max_tokens: maxTokens,
    betas: ["server-side-fallback-2026-06-01"],
    fallbacks: [{ model: "claude-opus-4-8" }],
    system,
    output_config: { format: { type: "json_schema", schema } },
    messages: [{ role: "user", content }],
  });
  return extractJSON(response);
}

// Haiku 4.5 呼び出し（コスト最適化のためのワーカー）
async function workerJSON({ system, content, schema, maxTokens = 2000 }) {
  const response = await client().messages.create({
    model: WORKER_MODEL,
    max_tokens: maxTokens,
    system,
    output_config: { format: { type: "json_schema", schema } },
    messages: [{ role: "user", content }],
  });
  return extractJSON(response);
}

module.exports = {
  ORCHESTRATOR_MODEL,
  WORKER_MODEL,
  imageBlock,
  orchestratorJSON,
  workerJSON,
};
