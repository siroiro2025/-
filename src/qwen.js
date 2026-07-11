"use strict";

// ローカル Qwen-Image-Edit (2511) サーバー用クライアント。
// tools/qwen_server.py が公開する簡易 HTTP API を叩く。
//   POST /edit  { prompt, images: [base64...] } -> { mimeType, data(base64) }

async function generateImage({ prompt, images = [] }) {
  const base = (process.env.QWEN_SERVER_URL || "http://localhost:8000").replace(/\/+$/, "");

  const res = await fetch(`${base}/edit`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      prompt,
      images: images.map((img) => img.data),
      width: 1024,
      height: 1024,
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Qwen ローカルサーバーエラー (${res.status}): ${body.slice(0, 500)}`);
  }

  const data = await res.json();
  if (!data.data) {
    throw new Error("Qwen ローカルサーバーが画像を返しませんでした");
  }
  return {
    buffer: Buffer.from(data.data, "base64"),
    mimeType: data.mimeType || "image/png",
  };
}

module.exports = { generateImage };
