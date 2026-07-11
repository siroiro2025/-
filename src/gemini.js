"use strict";

// Google Gemini 画像生成 API（Nano Banana）を REST で叩く薄いラッパー。
// Claude は画像生成ができないため、スプライトシートの描画のみここに委譲する。

const DEFAULT_MODEL = "gemini-2.5-flash-image";

async function generateImage({ prompt, images = [] }) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error("GEMINI_API_KEY が設定されていません（.env を確認してください）");
  }
  const model = process.env.GEMINI_IMAGE_MODEL || DEFAULT_MODEL;

  const parts = [
    ...images.map((img) => ({
      inlineData: { mimeType: img.mimeType, data: img.data },
    })),
    { text: prompt },
  ];

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
    {
      method: "POST",
      headers: {
        "x-goog-api-key": apiKey,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        contents: [{ parts }],
        generationConfig: {
          imageConfig: { aspectRatio: "1:1" },
        },
      }),
    }
  );

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Gemini API エラー (${res.status}): ${body.slice(0, 500)}`);
  }

  const data = await res.json();
  const candidateParts = data?.candidates?.[0]?.content?.parts ?? [];
  const imagePart = candidateParts.find((p) => p.inlineData?.data);
  if (!imagePart) {
    const textPart = candidateParts.find((p) => p.text)?.text ?? "";
    throw new Error(
      `Gemini が画像を返しませんでした。応答: ${textPart.slice(0, 300) || "(空)"}`
    );
  }

  return {
    buffer: Buffer.from(imagePart.inlineData.data, "base64"),
    mimeType: imagePart.inlineData.mimeType || "image/png",
  };
}

module.exports = { generateImage, DEFAULT_MODEL };
