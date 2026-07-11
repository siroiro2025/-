"use strict";

require("dotenv").config();

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const express = require("express");
const multer = require("multer");
const { runPipeline } = require("./src/pipeline");

const PORT = parseInt(process.env.PORT || "3000", 10);
const UPLOAD_DIR = path.join(__dirname, "uploads");
const OUTPUT_ROOT = path.join(__dirname, "output");
fs.mkdirSync(UPLOAD_DIR, { recursive: true });
fs.mkdirSync(OUTPUT_ROOT, { recursive: true });

const upload = multer({
  dest: UPLOAD_DIR,
  limits: { fileSize: 15 * 1024 * 1024 },
});

const jobs = new Map();

const app = express();
app.use(express.static(path.join(__dirname, "public")));
app.use("/output", express.static(OUTPUT_ROOT));

app.post("/api/generate", upload.single("image"), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "画像ファイルを添付してください" });
  }
  const allowed = ["image/png", "image/jpeg", "image/webp"];
  if (!allowed.includes(req.file.mimetype)) {
    fs.unlink(req.file.path, () => {});
    return res.status(400).json({ error: "PNG / JPEG / WebP の画像を指定してください" });
  }

  const jobId = crypto.randomBytes(8).toString("hex");
  const job = { id: jobId, status: "running", steps: [], error: null, result: null };
  jobs.set(jobId, job);

  runPipeline({
    filePath: req.file.path,
    mimeType: req.file.mimetype,
    jobId,
    job,
    outputRoot: OUTPUT_ROOT,
  })
    .then(() => {
      job.status = "done";
    })
    .catch((err) => {
      job.status = "error";
      job.error = err.message || String(err);
      console.error(`[job ${jobId}]`, err);
    })
    .finally(() => {
      fs.unlink(req.file.path, () => {});
    });

  res.json({ jobId });
});

app.get("/api/job/:id", (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: "job not found" });
  res.json(job);
});

app.listen(PORT, () => {
  console.log(`tomari-auto: http://localhost:${PORT}`);
});
