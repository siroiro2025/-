"use strict";

const fs = require("fs");
const path = require("path");
const { imageBlock, orchestratorJSON, workerJSON } = require("./claude");
const { generateImage, backendLabel } = require("./imagegen");
const { sliceSheet } = require("./slicer");

const GRID_ROWS = 5;
const GRID_COLS = 5;

// 6表情ステート（目2種 × 口3種）。最初のステートが基準シートになり、
// 以降のシートは基準シートを参照画像として渡して一貫性を保つ。
const STATES = [
  { id: "eyes_open_mouth_closed", label: "目開き・口閉じ（基準）", eyes: "open", mouth: "closed" },
  { id: "eyes_open_mouth_half", label: "目開き・口半開き", eyes: "open", mouth: "half-open" },
  { id: "eyes_open_mouth_open", label: "目開き・口開き", eyes: "open", mouth: "wide open" },
  { id: "eyes_closed_mouth_closed", label: "目閉じ・口閉じ", eyes: "closed", mouth: "closed" },
  { id: "eyes_closed_mouth_half", label: "目閉じ・口半開き", eyes: "closed", mouth: "half-open" },
  { id: "eyes_closed_mouth_open", label: "目閉じ・口開き", eyes: "closed", mouth: "wide open" },
];

const GRID_SPEC = `The image must be a single ${GRID_ROWS}x${GRID_COLS} sprite sheet grid (${GRID_ROWS} rows, ${GRID_COLS} columns, 25 equal cells, no gaps, no borders, flat plain background).
Each cell shows the SAME character from the waist up (upper body clearly visible: head, shoulders, chest, arms), same pose and framing in every cell, centered.
Only the direction the character is facing/looking changes per cell:
- Columns control horizontal gaze: column 1 = far left, column 2 = slightly left, column 3 = straight at viewer, column 4 = slightly right, column 5 = far right.
- Rows control vertical gaze: row 1 = looking up, row 2 = slightly up, row 3 = level, row 4 = slightly down, row 5 = looking down.
The center cell (row 3, column 3) faces the viewer directly. The head and eyes turn toward each direction naturally; the body may rotate slightly.`;

function stateSpec(state) {
  return `In EVERY cell the character's eyes are ${state.eyes} and the mouth is ${state.mouth}. This must be identical across all 25 cells.`;
}

// --- Fable 5: キャラクター分析と基準プロンプト設計 -------------------------

const ANALYZE_SCHEMA = {
  type: "object",
  properties: {
    character_description: {
      type: "string",
      description: "Concise English description of the character's identity, hair, eyes, outfit, colors, and art style",
    },
    style_notes: {
      type: "string",
      description: "English notes on the art style to preserve (line weight, shading, palette)",
    },
    base_sheet_prompt: {
      type: "string",
      description: "Complete English image-generation prompt for the base sprite sheet",
    },
  },
  required: ["character_description", "style_notes", "base_sheet_prompt"],
  additionalProperties: false,
};

async function analyzeCharacter(imgData, mimeType) {
  return orchestratorJSON({
    system:
      "You are the orchestrator of an avatar sprite-sheet generation pipeline. You analyze a single character illustration and design precise prompts for an image-generation model.",
    content: [
      imageBlock(imgData, mimeType),
      {
        type: "text",
        text: `Analyze this character illustration. Then write a complete image-generation prompt ("base_sheet_prompt") that reproduces this exact character as a sprite sheet.

The prompt MUST incorporate all of the following grid requirements verbatim or equivalently:

${GRID_SPEC}

${stateSpec(STATES[0])}

The prompt must describe the character faithfully (from the illustration) so the image model can reproduce them without seeing the original. Keep the art style identical to the illustration.`,
      },
    ],
    schema: ANALYZE_SCHEMA,
  });
}

// --- Fable 5: QC不合格時のプロンプト修正 -----------------------------------

const REVISE_SCHEMA = {
  type: "object",
  properties: {
    revised_prompt: { type: "string", description: "Improved English image-generation prompt" },
  },
  required: ["revised_prompt"],
  additionalProperties: false,
};

async function revisePrompt(previousPrompt, state, problems) {
  const { revised_prompt } = await orchestratorJSON({
    system:
      "You are the orchestrator of an avatar sprite-sheet generation pipeline. A quality check failed; rewrite the image-generation prompt to fix the reported problems while keeping all grid and character requirements.",
    content: [
      {
        type: "text",
        text: `Previous prompt:
---
${previousPrompt}
---

Required state: eyes ${state.eyes}, mouth ${state.mouth}.

Quality-check problems reported:
${problems.map((p) => `- ${p}`).join("\n")}

Rewrite the prompt to fix these problems. Keep the ${GRID_ROWS}x${GRID_COLS} grid spec and character description intact; strengthen the instructions that failed.`,
      },
    ],
    schema: REVISE_SCHEMA,
    maxTokens: 4000,
  });
  return revised_prompt;
}

// --- Haiku 4.5: 生成シートの検品（QC） --------------------------------------

const QC_SCHEMA = {
  type: "object",
  properties: {
    pass: { type: "boolean" },
    problems: {
      type: "array",
      items: { type: "string" },
      description: "Concrete problems found (English). Empty if pass.",
    },
  },
  required: ["pass", "problems"],
  additionalProperties: false,
};

async function qcSheet(sheetBase64, sheetMime, originalData, originalMime, state) {
  return workerJSON({
    system:
      "You are a strict quality checker for avatar sprite sheets. Compare the generated sheet against the original character illustration and the requirements. Report concrete problems.",
    content: [
      { type: "text", text: "Original character illustration:" },
      imageBlock(originalData, originalMime),
      { type: "text", text: "Generated sprite sheet to check:" },
      imageBlock(sheetBase64, sheetMime),
      {
        type: "text",
        text: `Check ALL of the following:
1. The sheet is a clean ${GRID_ROWS}x${GRID_COLS} grid of 25 cells of equal size (no merged cells, no extra rows/columns, no text or labels).
2. Every cell shows the SAME character as the original illustration (hair, outfit, colors, art style match).
3. The character's upper body (head to waist, including shoulders and chest) is visible in every cell — not just a face close-up.
4. In every cell the eyes are ${state.eyes} and the mouth is ${state.mouth}.
5. The facing/gaze direction varies across cells (left-to-right across columns, up-to-down across rows) and the center cell faces the viewer.

Set pass=true only if all checks are satisfied. Otherwise pass=false with specific problems.`,
      },
    ],
    schema: QC_SCHEMA,
  });
}

// --- パイプライン本体 --------------------------------------------------------

function pushStep(job, label) {
  const step = { label, status: "running", detail: "", startedAt: Date.now() };
  job.steps.push(step);
  return step;
}

async function runPipeline({ filePath, mimeType, jobId, job, outputRoot }) {
  const maxAttempts = Math.max(1, parseInt(process.env.MAX_ATTEMPTS || "2", 10));
  const originalData = fs.readFileSync(filePath).toString("base64");
  const outRoot = path.join(outputRoot, jobId);
  fs.mkdirSync(path.join(outRoot, "sheets"), { recursive: true });

  // 1. Fable 5 によるキャラクター分析 & プロンプト設計
  let step = pushStep(job, "キャラクター分析（Claude Fable 5）");
  const plan = await analyzeCharacter(originalData, mimeType);
  step.status = "done";
  step.detail = plan.character_description.slice(0, 200);

  const original = { mimeType, data: originalData };
  let baseSheet = null; // 一貫性維持のため基準シートを後続の参照に使う

  for (const state of STATES) {
    step = pushStep(job, `シート生成: ${state.label}`);

    let prompt;
    if (!baseSheet) {
      prompt = plan.base_sheet_prompt;
    } else {
      prompt = `You are given two reference images: (1) the original character illustration, (2) a completed ${GRID_ROWS}x${GRID_COLS} sprite sheet of that character.
Reproduce the sprite sheet EXACTLY — same grid layout, same character, same poses, same per-cell facing directions, same style — changing ONLY the facial expression in every cell:
${stateSpec(state)}
Character: ${plan.character_description}
Style: ${plan.style_notes}`;
    }

    let accepted = null;
    let lastQC = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      step.detail = `生成 ${attempt}/${maxAttempts} 回目（${backendLabel()}）...`;
      const refs = baseSheet ? [original, baseSheet] : [original];
      const sheet = await generateImage({ prompt, images: refs });

      step.detail = `検品中（Haiku 4.5）...`;
      const sheetB64 = sheet.buffer.toString("base64");
      lastQC = await qcSheet(sheetB64, sheet.mimeType, originalData, mimeType, state);

      if (lastQC.pass) {
        accepted = sheet;
        break;
      }
      if (attempt < maxAttempts) {
        step.detail = `検品NG → プロンプト修正（Fable 5）: ${lastQC.problems.join(" / ").slice(0, 150)}`;
        prompt = await revisePrompt(prompt, state, lastQC.problems);
      } else {
        // リトライ上限。最後の生成結果を警告付きで採用する
        accepted = sheet;
      }
    }

    const sheetPath = path.join(outRoot, "sheets", `${state.id}.png`);
    fs.writeFileSync(sheetPath, accepted.buffer);
    await sliceSheet(accepted.buffer, path.join(outRoot, "frames", state.id), GRID_ROWS, GRID_COLS);

    if (!baseSheet) {
      baseSheet = { mimeType: accepted.mimeType, data: accepted.buffer.toString("base64") };
    }

    step.status = lastQC && lastQC.pass ? "done" : "warn";
    step.detail = lastQC && lastQC.pass
      ? "検品OK"
      : `検品NGのまま採用: ${(lastQC?.problems || []).join(" / ").slice(0, 200)}`;
  }

  job.result = {
    viewerUrl: `/viewer.html?job=${jobId}`,
    sheets: STATES.map((s) => `/output/${jobId}/sheets/${s.id}.png`),
    grid: { rows: GRID_ROWS, cols: GRID_COLS },
    states: STATES.map((s) => s.id),
  };
}

module.exports = { runPipeline, STATES, GRID_ROWS, GRID_COLS };
