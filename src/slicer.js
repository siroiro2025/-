"use strict";

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

// スプライトシート（グリッド画像）を等分割してフレーム画像として保存する。
// tomari-guruguru の tools/slice_character_sheets.py に相当する処理。
async function sliceSheet(buffer, outDir, rows = 5, cols = 5) {
  fs.mkdirSync(outDir, { recursive: true });
  const meta = await sharp(buffer).metadata();
  const { width, height } = meta;
  const files = [];

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const left = Math.round((c * width) / cols);
      const top = Math.round((r * height) / rows);
      const cellW = Math.round(((c + 1) * width) / cols) - left;
      const cellH = Math.round(((r + 1) * height) / rows) - top;
      const file = path.join(outDir, `r${r}c${c}.png`);
      await sharp(buffer)
        .extract({ left, top, width: cellW, height: cellH })
        .png()
        .toFile(file);
      files.push(file);
    }
  }
  return files;
}

module.exports = { sliceSheet };
